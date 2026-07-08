import logging

from kag.common.parser.logic_node_parser import (
    ParseLogicForm,
    parse_logic_form_with_str,
)
from kag.interface import (
    ExecutorABC,
    LLMClient,
    PromptABC,
    RetrieverABC,
    RetrieverOutput,
    RetrieverOutputMerger,
    Task,
)
from kag.interface.solver.reporter_abc import ReporterABC
from kag.solver.executor.retriever.kag_hybrid_retrieval_executor import (
    KAGHybridRetrievalExecutor,
)
from kag.solver.prompt.kag_model.kag_subquestion_think_prompt import ThinkDecision

logger = logging.getLogger()


@ExecutorABC.register("kag_model_hybrid_retrieval_executor")
class KAGModelHybridRetrievalExecutor(KAGHybridRetrievalExecutor):
    def __init__(
        self,
        retrievers: list[RetrieverABC],
        merger: RetrieverOutputMerger,
        kag_sub_question_think_prompt: PromptABC,
        llm_module: LLMClient,
        **kwargs,
    ):
        super().__init__(retrievers=retrievers, merger=merger, llm_module=llm_module, **kwargs)
        self.kag_sub_question_think_prompt = kag_sub_question_think_prompt
        self.logic_node_parser = ParseLogicForm(schema=None, schema_retrieval=None)
        self.top_k = kwargs.get("top_k", 3)

    def do_main(self, task_query, tag_id, task, context, **kwargs):
        task_query = task.arguments["query"]
        logic_node = task.arguments.get("logic_form_node", None)
        flow_query = task_query
        for k, v in context.kwargs.get("step_answer", {}).items():
            if k in flow_query:
                flow_query = task_query.replace(k, v)
        logger.info(f"{task_query} rewrite query:{flow_query}")
        task.arguments["rewrite_query"] = flow_query

        step_id = task.name.lower().replace("step", "")

        messages = context.kwargs.get("messages", [])
        prompt_key = (
            f"Step{step_id}: {flow_query}\nAction{step_id}: {logic_node.to_logical_form_str()}"
        )
        messages.append(
            {
                "role": "user",
                "content": self.kag_sub_question_think_prompt.build_prompt(
                    {"question": prompt_key}
                ),
            }
        )

        reporter: ReporterABC | None = kwargs.get("reporter", None)
        retriever_output = RetrieverOutput(retriever_method=self.schema().get("name", ""))

        num_turns = 0
        while num_turns < 10:
            num_turns += 1
            cur_turn_tag_name = f"begin_sub_kag_think_{task_query}_{num_turns}"
            # Structured decision instead of the fine-tuned model's <search>/<answer>
            # text protocol: the model must choose search vs answer and fill the
            # matching field, so any model drives the loop deterministically.
            decision = self.llm_module.structured_output(ThinkDecision, messages=messages)
            self.report_content(
                reporter,
                tag_id,
                cur_turn_tag_name,
                decision.reasoning or "",
                "FINISH",
                step=task.name,
            )
            # Carry the turn forward as plain text (never the raw toolUse block, so
            # no tool-result turn is required by Converse).
            messages.append({"role": "assistant", "content": self._render_decision(decision)})

            if decision.action == "answer":
                predict = decision.answer or decision.reasoning
                step_answer = context.kwargs.get("step_answer", {})
                step_answer[f"#{step_id}"] = predict
                context.kwargs["step_answer"] = step_answer
                retriever_output.summary = predict
                if retriever_output.graphs and len(retriever_output.graphs[0].get_all_spo()):
                    context.variables_graph.merge_kg_graph(retriever_output.graphs[0])
                break

            # action == "search": retrieve from the KG using the model's query.
            search = decision.search_query or task_query
            try:
                sub_queries, logic_forms = parse_logic_form_with_str(search)
                logic_forms = self.logic_node_parser.parse_logic_form_set(
                    logic_forms, sub_queries, task_query
                )
                if not logic_forms:
                    logic_node.sub_query = search
                    logic_forms = [logic_node]
            except Exception as e:
                logger.warning(f"kag model think can not extra lf from {search} {e}")
                logic_node.sub_query = search
                logic_forms = [logic_node]

            try:
                target_query = logic_forms[0].sub_query
                cur_task = Task(
                    id=task.id,
                    name=task.name,
                    executor=task.executor,
                    parents=task.parents,
                    children=task.children,
                    arguments={"query": target_query, "logic_form_node": logic_forms[0]},
                )
                retriever_output = self.do_retrieval(
                    task_query=target_query,
                    tag_id=cur_turn_tag_name,
                    task=cur_task,
                    context=context,
                    **kwargs,
                )

                recall_information_list = []
                if retriever_output.graphs and len(retriever_output.graphs[0].get_all_spo()):
                    spos = [str(spo) for spo in retriever_output.graphs[0].get_all_spo()]
                    recall_information_list.append(";".join(spos))
                for chunk in retriever_output.chunks[: self.top_k]:
                    recall_information_list.append(chunk.content)
                recall_str = "<references>" + "\n\n".join(recall_information_list) + "</references>"
                messages.append({"role": "user", "content": recall_str})
            except Exception as e:
                logger.error(f"kag flow exception! {e} search={search}", exc_info=True)
                self.report_content(
                    reporter,
                    cur_turn_tag_name,
                    f"failed_kag_retriever_{task_query}_{num_turns}",
                    f"{e}",
                    "INIT",
                    step=task.name,
                )

        context.kwargs["messages"] = messages
        return retriever_output

    @staticmethod
    def _render_decision(decision) -> str:
        """Render a ThinkDecision back to plain text for the conversation history."""
        if decision.action == "search":
            return f"{decision.reasoning}\nSearch: {decision.search_query or ''}"
        return f"{decision.reasoning}\nAnswer: {decision.answer or ''}"

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
