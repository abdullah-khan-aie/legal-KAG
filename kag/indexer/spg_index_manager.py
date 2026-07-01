"""Lodestone-specific index manager (no openspg-kag counterpart).

The reference builds its graph via ``kag_hybrid_index`` (knowledge_unit_extractor).
This project instead builds a typed, schema-constrained SPG graph via
``schema_constraint_extractor``. This manager slots that extractor into the same
``KAGIndexManager`` pattern, so the graph backbone is selected through
``index_list`` like every other index -- keeping ingestion uniform and
extensible as more extractors are added.

Its retriever list is intentionally empty: the SPG graph is structural (typed
entities/relations/events, used for entity linking), and chunk-oriented
retrieval comes from the summary / chunk / atomic-query indices. Enable
``kag_hybrid_index`` if graph-backed retrieval (kg_cs / kg_fr) is wanted.
"""

from kag.common.conf import KAGConstants
from kag.indexer.kag_index_manager import KAGIndexManager


@KAGIndexManager.register("spo_graph_index")
class SpoGraphIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Schema-constrained SPG graph index manager"

    @property
    def description(self) -> str:
        return (
            "Builds a typed knowledge graph (entities, relations, events) from "
            "chunks, constrained by the project schema. Provides the structural "
            "graph backbone and entity-linking targets; retrieval is served by "
            "the chunk-oriented indices."
        )

    @property
    def schema(self) -> str:
        return "Graph (schema-constrained entities / relations / events)"

    @property
    def retrieval_method(self) -> str:
        return ""

    @classmethod
    def build_extractor_config(
        cls, llm_config: dict, vectorize_model_config: dict, **kwargs
    ):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        schema_path = kwargs.get("schema_path")
        return [
            {
                "type": "schema_constraint_extractor",
                "llm": llm_config,
                "schema_path": schema_path,
                "ner_prompt": {"type": "spg_entity", "schema_path": schema_path},
                "relation_prompt": {"type": "spg_relation", "schema_path": schema_path},
                "event_prompt": {"type": "spg_event", "schema_path": schema_path},
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(
        cls, llm_config: dict, vectorize_model_config: dict, **kwargs
    ):
        return []
