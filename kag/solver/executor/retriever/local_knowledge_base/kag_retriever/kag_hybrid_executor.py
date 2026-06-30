import json
import logging
import time
import uuid
from typing import Any

from tenacity import retry, stop_after_attempt

from kag.common.conf import KAGConfigAccessor, KAGConstants
from kag.common.config import get_default_chat_llm_config
from kag.common.parser.logic_node_parser import GetSPONode
from kag.interface import Context, ExecutorABC, ExecutorResponse, LLMClient
from kag.interface.solver.base_model import LogicNode
from kag.interface.solver.model.one_hop_graph import (
    ChunkData,
    KgGraph,
    RetrievedData,
)
from kag.interface.solver.reporter_abc import ReporterABC
from kag.solver.executor.retriever.local_knowledge_base.kag_retriever.kag_component.kag_lf_rewriter import (
    KAGLFRewriter,
)
from kag.solver.executor.retriever.local_knowledge_base.kag_retriever.kag_flow import (
    KAGFlow,
)
from kag.solver.executor.retriever.local_knowledge_base.kag_retriever.utils import (
    get_history_qa,
)
from kag.solver.utils import init_prompt_with_fallback

logger = logging.getLogger()


def to_reference_list(prefix_id, retrieved_datas: list[RetrievedData]):
    refer_docs = []
    refer_id = 0
    for rd in retrieved_datas:
        if isinstance(rd, ChunkData):
            # Clean rd.content: strip outer quotes and unescape '\n' to real newlines
            raw_content = rd.content
            if (
                isinstance(raw_content, str)
                and raw_content.startswith('"')
                and raw_content.endswith('"')
            ):
                raw_content = raw_content[1:-1]
            clean_content = raw_content.replace("\\n", "\n")
            # Clean rd.title similarly
            raw_title = rd.title
            if isinstance(raw_title, str) and raw_title.startswith('"') and raw_title.endswith('"'):
                raw_title = raw_title[1:-1]
            clean_title = raw_title.replace("\\n", "\n")
            refer_doc = {
                "id": f"chunk:{prefix_id}_{refer_id}",
                "content": clean_content,
                "document_id": rd.chunk_id,
                "document_name": clean_title,
            }
            if hasattr(rd, "properties"):
                for k, v in rd.properties.items():
                    if k not in refer_doc:
                        refer_doc[k] = str(v)
            refer_docs.append(refer_doc)
            refer_id += 1

        if isinstance(rd, KgGraph):
            spo_set = list(set(rd.get_all_spo()))
            for spo in spo_set:
                refer_docs.append(
                    {
                        "id": f"chunk:{prefix_id}_{refer_id}",
                        "content": spo.to_show_id(),
                        "document_id": str(uuid.uuid5(uuid.NAMESPACE_URL, spo.to_show_id())),
                        "document_name": "graph data",
                    }
                )
                refer_id += 1
    return refer_docs


class KAGRetrievedResponse(ExecutorResponse):
    """Hold the data retrieved while answering a task.

    Bundles the original task description, per-sub-question results, graph data,
    retrieved chunks, and the generated summary.
    """

    def __init__(self):
        super().__init__()
        self.task_id = "0"
        self.sub_retrieved_set = []  # Collection of processed sub-question results
        self.retrieved_task = ""  # Original task description
        self.graph_data = None
        self.chunk_datas = []
        self.summary = ""

    def __str__(self):
        return self.to_string()

    __repr__ = __str__

    def get_chunk_list(self):
        res = []
        for c in self.chunk_datas:
            res.append(f"{c.content}")
        if len(res) == 0:
            return to_reference_list(self.task_id, [self.graph_data])
        return res

    def to_reference_list(self):
        """Build reference entries for the retrieved chunks and graph data.

        Each entry has the shape::

            {
                "id": "1-1",
                "content": "...",
                "document_id": "53052eb0f40b11ef817442010a8a0006",
                "document_name": "test.txt"
            }
        """
        return to_reference_list(
            self.task_id,
            self.chunk_datas + ([self.graph_data] if self.graph_data else []),
        )

    def to_string(self) -> str:
        """Serialize the response to a JSON string of task and results."""
        refer_docs = self.to_reference_list()
        for doc in refer_docs:
            doc.pop("document_id")
        if "i don't know" in self.summary.lower() or self.summary == "":
            response_str = {
                "retrieved_task": self.retrieved_task,
                "reference_docs": refer_docs,
            }
        else:
            response_str = {
                "retrieved_task": self.retrieved_task,
                "summary": self.summary,
            }

        return json.dumps(response_str, ensure_ascii=False)

    def to_dict(self):
        """Return the response as a serializable dictionary."""
        return {
            "retrieved_task": self.retrieved_task,
            "sub_question": [item.to_dict() for item in self.sub_retrieved_set],
            "graph_data": (
                [str(spo) for spo in self.graph_data.get_all_spo()] if self.graph_data else []
            ),
            "chunk_datas": [item.to_dict() for item in self.chunk_datas],
            "summary": self.summary,
        }


def initialize_response(task) -> KAGRetrievedResponse:
    """Create a response container initialized from the given task."""
    response = KAGRetrievedResponse()
    response.retrieved_task = str(task)
    response.task_id = task.id
    return response


def store_results(task, response: KAGRetrievedResponse):
    """Persist the retrieval response and its chunks onto the task."""
    task.update_memory("response", response)
    task.update_memory("chunks", response.chunk_datas)
    task.update_result(response)


@ExecutorABC.register("kag_hybrid_executor")
class KagHybridExecutor(ExecutorABC):
    """Hybrid knowledge graph retrieval executor combining multiple strategies.

    Combines entity linking, path selection, and text chunk retrieval using
    knowledge graph and LLM capabilities to answer complex queries.
    """

    def __init__(self, flow, lf_rewriter: KAGLFRewriter, llm_client: LLMClient = None, **kwargs):
        super().__init__(**kwargs)
        self.lf_rewriter: KAGLFRewriter = lf_rewriter
        self.flow_str = flow
        task_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        kag_config = KAGConfigAccessor.get_config(task_id)
        self.kag_project_config = kag_config.global_config
        self.solve_question_without_spo_prompt = init_prompt_with_fallback(
            "summary_question", self.kag_project_config.biz_scene
        )
        self.llm_client = llm_client or LLMClient.from_config(get_default_chat_llm_config())

        self.flow: KAGFlow = KAGFlow(flow_str=self.flow_str, llm_client=self.llm_client)

    @property
    def output_types(self):
        """Return the type produced by this executor's output."""
        return KAGRetrievedResponse

    @retry(stop=stop_after_attempt(3))
    def generate_answer(self, tag_id, question: str, docs: [], history_qa=[], **kwargs):
        """Generate an answer for a question from supporting documents.

        Args:
            tag_id: Reporting segment identifier for this step.
            question: The question to answer.
            docs: Documents supporting the answer.
            history_qa: Previous question-answer pairs for context.

        Returns:
            The generated answer, or ``"I don't know"`` when the model is unsure.
        """
        prompt = self.solve_question_without_spo_prompt
        params = {
            "question": question,
            "docs": [str(d) for d in docs],
            "history": "\n".join(history_qa),
        }

        llm_output = self.llm_client.invoke(
            params,
            prompt,
            with_json_parse=False,
            with_except=True,
            tag_name=f"kag_hybrid_retriever_summary_{question}",
            segment_name=tag_id,
            **kwargs,
        )
        logger.debug(f"sub_question:{question}\n sub_answer:{llm_output} prompt:\n{prompt}")
        if llm_output:
            return llm_output
        return "I don't know"

    def generate_summary(self, tag_id, query, chunks, history, **kwargs):
        history_qa = get_history_qa(history)
        if len(history) == 1 and len(history_qa) == 1:
            return history[0].get_fl_node_result().summary
        return self.generate_answer(
            tag_id=tag_id, question=query, docs=chunks, history_qa=history_qa, **kwargs
        )

    def invoke(self, query: str, task: Any, context: Context, **kwargs):
        reporter: ReporterABC | None = kwargs.get("reporter", None)
        task_query = task.arguments["query"]
        logic_node = task.arguments.get("logic_form_node", None)
        logger.info(f"{task_query} begin kag hybrid executor")
        logger.info(f"Initializing response container for task: {task_query}")
        start_time = time.time()
        kag_response = initialize_response(task)
        tag_id = f"{task_query}_begin_task"
        flow_query = logic_node.sub_query if logic_node else task_query

        try:
            logger.info(
                f"Response container initialized in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )

            logger.info(f"Converting query to logical form for task: {task_query}")
            start_time = time.time()
            self.report_content(
                reporter,
                "thinker",
                tag_id,
                f"{flow_query}\n",
                "INIT",
                step=task.name,
            )
            if not logic_node:
                logic_nodes = self._convert_to_logical_form(flow_query, task, reporter=reporter)
            else:
                logic_nodes = [logic_node]
            logger.info(
                f"Query converted to logical form in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )

            logger.info(f"Creating KAGFlow for task: {task_query}")
            start_time = time.time()

            logger.info(
                f"KAGFlow created in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )

            logger.info(f"Executing KAGFlow for task: {task_query}")
            start_time = time.time()
            graph_data, retrieved_datas = self.flow.execute(
                flow_id=task.id,
                nl_query=flow_query,
                lf_nodes=logic_nodes,
                executor_task=task,
                reporter=reporter,
                segment_name=tag_id,
                context_graph=context.variables_graph,
            )
            kag_response.graph_data = graph_data
            if graph_data:
                context.variables_graph.merge_kg_graph(graph_data)
            kag_response.chunk_datas = retrieved_datas
            logger.info(
                f"KAGFlow executed in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )
            self.report_content(
                reporter,
                "reference",
                f"{task_query}_kag_retriever_result",
                kag_response,
                "FINISH",
            )

            logger.info(f"Processing logic nodes for task: {task_query}")
            start_time = time.time()
            for lf_node in logic_nodes:
                kag_response.sub_retrieved_set.append(lf_node.get_fl_node_result())
            logger.info(
                f"Logic nodes processed in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )
            kag_response.summary = self.generate_summary(
                tag_id=tag_id,
                query=task_query,
                chunks=kag_response.get_chunk_list(),
                history=logic_nodes,
                **kwargs,
            )
            logger.info(f"Summary Question {task_query} : {kag_response.summary}")
            logger.info(f"Storing results for task: {task_query}")
            if logic_node and isinstance(logic_node, GetSPONode):
                context.variables_graph.add_answered_alias(
                    logic_node.s.alias_name.alias_name, kag_response.summary
                )
                context.variables_graph.add_answered_alias(
                    logic_node.p.alias_name.alias_name, kag_response.summary
                )
                context.variables_graph.add_answered_alias(
                    logic_node.o.alias_name.alias_name, kag_response.summary
                )

            start_time = time.time()
            store_results(task, kag_response)
            logger.info(
                f"Results stored in {time.time() - start_time:.2f} seconds for task: {task_query}"
            )
            logger.info(f"Completed storing results for task: {task_query}")
            self.report_content(
                reporter,
                "thinker",
                tag_id,
                "",
                "FINISH",
                step=task.name,
                overwrite=False,
            )
        except Exception as e:
            logger.warning(f"{self.schema().get('name')} executed failed {e}", exc_info=True)
            store_results(task, kag_response)
            self.report_content(
                reporter,
                "thinker",
                tag_id,
                f"{self.schema().get('name')} executed failed {e}",
                "ERROR",
                step=task.name,
                overwrite=False,
            )
            logger.info(f"Exception occurred for task: {task_query}, error: {e}")
            raise e

        logger.info(f"{task_query} end kag hybrid executor")

    def _convert_to_logical_form(self, query: str, task, reporter) -> list[LogicNode]:
        """Rewrite the query into logical nodes using the task's dependency context."""
        dep_tasks = task.parents
        context = []
        for dep_task in dep_tasks:
            if not dep_task.result:
                continue
            context.append(dep_task.result)
        return self.lf_rewriter.rewrite(query=query, context=context, reporter=reporter)

    def schema(self) -> dict:
        """Return the executor's function-calling schema.

        Returns:
            The schema describing this executor in OpenAI function-call format.
        """
        return {
            "name": "Retriever",
            "description": "Retrieve relevant knowledge from the local knowledge base.",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "User-provided query for retrieval.",
                    "optional": False,
                },
            },
        }
