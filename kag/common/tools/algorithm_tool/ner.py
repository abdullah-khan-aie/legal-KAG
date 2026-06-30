import logging

from tenacity import retry, stop_after_attempt

import kag.common.cache
from kag.common.conf import KAGConfigAccessor, KAGConstants
from kag.interface import LLMClient, PromptABC, ToolABC
from kag.interface.solver.base_model import SPOEntity
from kag.solver.utils import init_prompt_with_fallback

logger = logging.getLogger()
ner_tool_cache = kag.common.cache.LinkCache(maxsize=100, ttl=300)


@ToolABC.register("ner")
class Ner(ToolABC):
    def __init__(
        self,
        llm_module: LLMClient,
        ner_prompt: PromptABC = None,
        std_prompt: PromptABC = None,
        with_semantic=False,
        **kwargs,
    ):
        super().__init__()
        task_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        kag_config = KAGConfigAccessor.get_config(task_id)
        self.kag_project_config = kag_config.global_config
        self.ner_prompt = ner_prompt or init_prompt_with_fallback(
            "question_ner", self.kag_project_config.biz_scene
        )
        self.std_prompt = std_prompt or init_prompt_with_fallback(
            "std", self.kag_project_config.biz_scene
        )
        self.llm_module = llm_module
        self.with_semantic = with_semantic

    @retry(stop=stop_after_attempt(3), reraise=True)
    def named_entity_recognition(self, query: str):
        """Perform named entity recognition on the query.

        Invokes the configured LLM with the NER prompt to extract entities.

        Args:
            query: Text to analyze for named entities.

        Returns:
            The recognized entities as returned by the LLM client.
        """
        return self.llm_module.invoke({"input": query}, self.ner_prompt, with_json_parse=True)

    @retry(stop=stop_after_attempt(3), reraise=True)
    def named_entity_standardization(self, query: str, entities: list[dict]):
        """Standardize named entities to unify their representations.

        Invokes the LLM with the standardization prompt to map varying
        mentions of the same entity to a canonical form.

        Args:
            query: Query text containing the named entities.
            entities: Named entities to standardize.

        Returns:
            The standardized entity information as returned by the LLM client.
        """
        return self.llm_module.invoke(
            {"input": query, "named_entities": entities},
            self.std_prompt,
            with_json_parse=True,
        )

    @staticmethod
    def append_official_name(source_entities: list[dict], entities_with_official_name: list[dict]):
        """Copy official names onto matching source entities in-place.

        Args:
            source_entities: Entities to be annotated with official names.
            entities_with_official_name: Entities carrying the official names,
                matched by category and name.
        """
        tmp_dict = {}
        for tmp_entity in entities_with_official_name:
            name = tmp_entity["name"]
            category = tmp_entity["category"]
            official_name = tmp_entity["official_name"]
            key = f"{category}{name}"
            tmp_dict[key] = official_name

        for tmp_entity in source_entities:
            name = tmp_entity["name"]
            category = tmp_entity["category"]
            key = f"{category}{name}"
            if key in tmp_dict:
                official_name = tmp_dict[key]
                tmp_entity["official_name"] = official_name

    def _parse_ner_list(self, query):
        ner_list = []
        try:
            ner_list = ner_tool_cache.get(query)
            if ner_list:
                return ner_list
            ner_list = self.named_entity_recognition(query)
            if self.with_semantic:
                std_ner_list = self.named_entity_standardization(query, ner_list)
                self.append_official_name(ner_list, std_ner_list)
            ner_tool_cache.put(query, ner_list)
        except Exception as e:
            if not ner_list:
                ner_list = []
            logger.warning(f"_parse_ner_list {query} failed {e}", exc_info=True)
        return ner_list

    def invoke(self, query, **kwargs) -> list[SPOEntity]:
        res = []
        ner_list = self._parse_ner_list(query)
        for item in ner_list:
            entity = item.get("name", "")
            category = item.get("category", "")
            official_name = item.get("official_name", entity)
            if not entity or not official_name:
                continue
            if category.lower() in ["works", "person", "other"]:
                res.append(SPOEntity(entity_name=entity, un_std_entity_type=category))
            else:
                res.append(SPOEntity(entity_name=official_name, un_std_entity_type=category))
        return res

    def schema(self):
        return {
            "name": "ner",
            "description": "Identify named entities in the input text",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text to analyze for named entities",
                    }
                },
                "required": ["query"],
            },
        }
