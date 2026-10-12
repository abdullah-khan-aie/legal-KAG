from kag.common.conf import KAGConfigAccessor, KAGConstants
from kag.common.config import get_default_chat_llm_config
from kag.interface import LLMClient, PromptABC, ToolABC
from kag.solver.utils import init_prompt_with_fallback


@ToolABC.register("self_cognition")
class SelfCognExecutor(ToolABC):
    def __init__(
        self,
        llm_module: LLMClient = None,
        self_cognition_prompt: PromptABC = None,
        **kwargs,
    ):
        super().__init__()
        task_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        kag_config = KAGConfigAccessor.get_config(task_id)
        self.kag_project_config = kag_config.global_config
        self.llm_module = llm_module or LLMClient.from_config(get_default_chat_llm_config())
        self.self_cognition_prompt = self_cognition_prompt or init_prompt_with_fallback(
            "self_cognition", self.kag_project_config.biz_scene
        )

        # What the assistant says when asked what it is.
        self.docs_zh = [
            "我是一个基于知识图谱的问答助手，擅长逻辑推理与多跳检索，可以协助你分析文档并回答相关问题。",
        ]
        self.docs_en = [
            "I am a knowledge graph question answering assistant. I specialise in "
            "logical reasoning and multi-hop retrieval over your documents, and can "
            "help you analyse them and answer questions about their contents."
        ]

    @property
    def category(self):
        return "SelfCognition"

    def invoke(self, query: str, **kwargs):
        return self.llm_module.invoke(
            {"question": query}, self.self_cognition_prompt, with_json_parse=False
        )

    def get_docs(self):
        if self.kag_project_config.language == "zh":
            return self.docs_zh
        else:
            return self.docs_en

    def schema(self):
        return {
            "name": "SelfCognition",
            "description": "Performs query-to-query operations and is solely used to indicate that the task has been completed.",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "User-provided query for retrieval.",
                    "optional": False,
                },
            },
        }
