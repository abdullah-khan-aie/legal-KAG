# ruff: noqa
# to the server-free neo4j_search_api/neo4j_graph_api, and the display-only metadata
# strings translated from Chinese to English. The build_* config logic is unchanged.)
from typing import Dict

from kag.common.conf import KAGConstants
from kag.common.registry import Registrable


class KAGIndexManager(Registrable):
    def __init__(self, llm_config: Dict, vectorize_model_config: Dict):
        self.extractor_config = self.build_extractor_config(llm_config, vectorize_model_config)
        self.retriever_config = self.build_retriever_config(llm_config, vectorize_model_config)

    @property
    def name(self):
        return "KAG Index Manager"

    @property
    def description(self) -> str:
        return ""

    @property
    def schema(self) -> str:
        return ""

    @property
    def as_default(self) -> bool:
        return False

    def get_meta(self):
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
            "config": {
                "extractor": self.extractor_config,
                "retriever": self.retriever_config,
            },
            "index_cost": self.index_cost,
            "retrieval_method": self.retrieval_method,
            "applicable_scenarios": self.applicable_scenarios,
            "as_default": self.as_default,
        }

    @property
    def applicable_scenarios(self) -> str:
        return ""

    @property
    def index_cost(self) -> str:
        return ""

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds atomic questions and retrieves them; generally used to fetch "
            "chunks related to an atomic question."
        )

    def build_extractor_config(self, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        return []

    def build_retriever_config(self, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        return []


@KAGIndexManager.register("atomic_query_index")
class AtomicIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Atomic-query-based index manager"

    @property
    def description(self) -> str:
        return (
            "Builds an index by extracting independent, answerable atomic queries "
            "(AtomicQuery) from documents. It decomposes complex questions and "
            "supplies precise context by retrieving the text chunks (Chunk) most "
            "relevant to those atomic questions; especially suited to fine-grained "
            "question answering."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector
AtomicQuery (atomic question): IndexType
  properties:
    title: Text
      index: TextAndVector
  relations:
    sourceChunk (linked text block): Chunk
    similar (similar question): AtomicQuery
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 121535 tokens
        2. Time: 109.5 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: Factual Q&A, FAQ, and other cases where a simple
        question can be matched precisely to find the answer.

        **Retrieval flow**:
        1. `rewrite(sub_query)`: rewrite the user question into a more canonical form.
        2. `recall_atomic_question(...)`: recall similar atomic questions via semantic or text matching on the rewritten question.
        3. `get_qa_associate_chunks(...)`: from the recalled atomic questions, find their linked text chunks as the final answer source.

        **Code example**:
        `chunks = get_qa_associate_chunks(recall_atomic_question(rewrite(sub_query)))`
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds atomic questions and retrieves them; generally used to fetch "
            "chunks related to an atomic question."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "atomic_query_extractor",
                "llm": llm_config,
                "prompt": {"type": "atomic_query_extract"},
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "atomic_query_chunk_retriever",
                "vectorize_model": vectorize_model_config,
                "score_threshold": 0.7,
                "llm_client": llm_config,
                "query_rewrite_prompt": {"type": "atomic_query_rewrite_prompt"},
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "graph_api": {
                    "type": "neo4j_graph_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
            {
                "type": "vector_chunk_retriever",
                "score_threshold": 0.7,
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
            {
                "type": "text_chunk_retriever",
                # Target the dedicated single-field chunk index (Chunk.content) rather
                # than the broad _default_text_index, whose per-term x per-field fanout
                # trips Lucene's 1024 maxClauseCount. Must match
                # neo4j_graph_store.CHUNK_TEXT_INDEX_NAME.
                "index_name": "_chunk_text_index",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]


@KAGIndexManager.register("chunk_index")
class ChunkIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Chunk-based index manager"

    @property
    def description(self) -> str:
        return (
            "Splits documents directly into text chunks (Chunk) and builds vector "
            "and text indexes over them. A direct, efficient approach (Naive RAG), "
            "suited to semantic or keyword retrieval across a whole document to "
            "quickly locate relevant passages."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 0 tokens
        2. Time: 1.5 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: General, open-ended document Q&A, when the question
        has no particular structure and the answer must be found in large amounts of
        unstructured text.

        **Retrieval flow**:
        1. `rewrite(sub_query)`: rewrite the user question.
        2. `recall_chunks(...)`: run vector or keyword search directly over all text chunks to recall the most relevant ones.

        **Code example**:
        `chunks = recall_chunks(rewrite(sub_query))`
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds a chunk index and retrieves chunks; generally used to fetch "
            "chunks related to a chunk."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "naive_rag_extractor",
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "vector_chunk_retriever",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
            {
                "type": "text_chunk_retriever",
                # Target the dedicated single-field chunk index (Chunk.content) rather
                # than the broad _default_text_index, whose per-term x per-field fanout
                # trips Lucene's 1024 maxClauseCount. Must match
                # neo4j_graph_store.CHUNK_TEXT_INDEX_NAME.
                "index_name": "_chunk_text_index",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]


@KAGIndexManager.register("table_index")
class TableIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Table-based index manager"

    @property
    def description(self) -> str:
        return (
            "Identifies and extracts tabular data from documents and indexes their "
            "content and context (surrounding text). It can precisely retrieve tables "
            "and use the relationship between a table and its surrounding text to "
            "recall related chunks; well suited to documents rich in structured "
            "tabular data."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector
Table (table): IndexType
    properties:
        content: Text
          index: TextAndVector
        beforeText (preceding text): Text
          index: TextAndVector
        afterText (following text): Text
          index: TextAndVector
    relations:
        sourceChunk (linked): Chunk
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 0 tokens
        2. Time: 1.5 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: When the question concerns data in a table, e.g.
        "What is the price of product XX?", or when the answer must cite table content.

        **Retrieval flow**:
        1. `rewrite(sub_query)`: rewrite the user question.
        2. `recall_table(...)`: search and recall the most relevant tables based on the question.
        3. `get_table_associate_chunks(...)`: find the chunks linked to the recalled tables to provide richer context.

        **Code example**:
        `chunks = get_table_associate_chunks(recall_table(rewrite(sub_query)))`
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds a table index and retrieves tables; generally used to fetch "
            "chunks related to a table."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "table_extractor",
                "llm": llm_config,
                "table_context_prompt": {"type": "table_context"},
                "table_row_col_summary_prompt": {"type": "table_row_col_summary"},
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "table_retriever",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "graph_api": {
                    "type": "neo4j_graph_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]


@KAGIndexManager.register("summary_index")
class SummaryIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Summary-based index manager"

    @property
    def description(self) -> str:
        return (
            "Uses an LLM to generate multi-level summaries (Summary) of text chunks "
            "(Chunk) and builds an index over them. Retrieving summaries lets you "
            "quickly grasp the core of large sections and, via the link between "
            "summaries and original chunks, recall detailed information; suited to "
            "scenarios needing an overview and progressive drill-down."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector
Summary (text summary): IndexType
     properties:
        content: Text
          index: TextAndVector
     relations:
        sourceChunk (linked): Chunk
        childOf (child summary): Summary
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 88701 tokens
        2. Time: 85.2 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: When you need to summarize long documents, or to
        drill from macro to micro through information layer by layer.

        **Retrieval flow**:
        1. `rewrite(sub_query)`: rewrite the user question.
        2. `recall_summary(...)`: search and recall the most relevant summaries based on the question.
        3. `get_summary_associate_chunks(...)`: via the recalled summaries, find their original chunks to provide detail.

        **Code example**:
        `chunks = get_summary_associate_chunks(recall_summary(rewrite(sub_query)))`
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Retrieves LLM-generated summaries; generally used to fetch chunks "
            "related to a summary."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "summary_extractor",
                "llm_module": llm_config,
                "chunk_summary_prompt": {"type": "default_chunk_summary"},
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "summary_chunk_retriever",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "graph_api": {
                    "type": "neo4j_graph_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "score_threshold": 0.8,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]


@KAGIndexManager.register("outline_index")
class OutlineIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Outline-based index manager"

    @property
    def description(self) -> str:
        return (
            "Builds an outline (Outline) index by parsing the document's structure "
            "(e.g. heading levels). This preserves the document hierarchy, letting "
            "users quickly locate specific sections by retrieving section headings "
            "and recall the chunks linked to that outline node."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector
Outline (heading outline): IndexType
     properties:
        content: Text
          index: TextAndVector
     relations:
        sourceChunk (linked): Chunk
        childOf (child heading): Outline
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 0 tokens
        2. Time: 9.4 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: Q&A over structured documents, especially when the
        question relates to a specific section or heading.

        **Retrieval flow**:
        1. `rewrite(sub_query)`: rewrite the user question.
        2. `recall_outline(...)`: search and recall the most relevant outline headings, optionally expanding along the outline hierarchy.
        3. `get_outline_associate_chunks(...)`: from the recalled outline, find the corresponding chunks.

        **Code example**:
        `chunks = get_outline_associate_chunks(recall_outline(rewrite(sub_query)))`
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds an outline of the text and retrieves it; generally used to fetch "
            "chunks related to an outline."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "outline_extractor",
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "outline_chunk_retriever",
                "vectorize_model": vectorize_model_config,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "graph_api": {
                    "type": "neo4j_graph_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "top_k": 10,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]


@KAGIndexManager.register("kag_hybrid_index")
class KAGHybridIndexManager(KAGIndexManager):
    @property
    def name(self):
        return "Hybrid chunk-and-graph index manager"

    @property
    def description(self) -> str:
        return (
            "A hybrid approach combining the strengths of a knowledge graph (KG) and "
            "text chunks (Chunk). It first extracts entities and relations from text "
            "to build a graph, then links chunks to graph nodes. At retrieval time it "
            "uses both the graph's structured query ability (CS/FR retriever) and "
            "text vector retrieval for more precise, reasoning-capable retrieval; "
            "especially suited to complex question answering."
        )

    @property
    def schema(self) -> str:
        return """
Chunk (text block): IndexType
     properties:
        content: Text
          index: TextAndVector

KnowledgeUnit (knowledge unit): IndexType
     properties:
        structedContent (structured text): Text
          index: TextAndVector
        ontology: Text
        desc (description): Text
            index: TextAndVector
        relatedQuery (related question): AtomicQuery
        extendedKnowledge (extended knowledge): Text
        content: Text
            index: TextAndVector
        knowledgeType (knowledge type): Text

AtomicQuery (atomic question): IndexType
  properties:
    title: Text
      index: TextAndVector
  relations:
    sourceChunk (linked text block): Chunk
    similar (similar question): AtomicQuery
    relatedTo (related): KnowledgeUnit
        """

    @property
    def index_cost(self) -> str:
        msg = """
        Index build cost:

        1. Extraction model usage: 7B, 4634332 tokens
        2. Time: 1425 s
        3. Document size: 100k characters
        """
        return msg

    @property
    def applicable_scenarios(self) -> str:
        return """
        **Applicable scenarios**: Complex questions requiring deep reasoning and
        relational analysis. It understands the question's structure and performs
        joint queries across the knowledge graph and text chunks, handling
        cross-domain knowledge or multi-hop reasoning.

        **Retrieval flow (multi-path, parallel)**:
        - **Path 1 (FR)**: `kg_fr_retriever(query)` -> free-text retrieval, recalling relevant chunks.
        - **Path 2 (CS)**: `kg_cs_retriever(logic_form)` -> precise graph retrieval based on the question's logical structure.
        - **Path 3 (RC)**: `vector_chunk_retriever(query)` -> pure vector retrieval as a supplementary recall.

        Results from all paths are fused to provide the most comprehensive basis for an answer.
        """

    @property
    def retrieval_method(self) -> str:
        return (
            "Builds links between chunks and the graph, enabling graph and chunk "
            "retrieval; generally used to fetch chunks related to the graph."
        )

    @classmethod
    def build_extractor_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "knowledge_unit_extractor",
                "ner_prompt": "knowledge_unit_ner",
                "triple_prompt": "knowledge_unit_triple",
                "kn_prompt": "knowledge_unit",
                "llm": llm_config,
                "kag_qa_task_config_key": kb_task_project_id,
            }
        ]

    @classmethod
    def build_retriever_config(cls, llm_config: Dict, vectorize_model_config: Dict, **kwargs):
        kb_task_project_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        return [
            {
                "type": "kg_cs_default",
                "path_select": {
                    "type": "exact_one_hop_select",
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "graph_api": {
                        "type": "neo4j_graph_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "entity_linking": {
                    "type": "entity_linking",
                    "recognition_threshold": 0.9,
                    "exclude_types": ["Chunk"],
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "graph_api": {
                        "type": "neo4j_graph_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "std_schema": {
                    "type": "default_std_schema",
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "llm": llm_config,
                "kag_qa_task_config_key": kb_task_project_id,
            },
            {
                "type": "kg_fr_knowledge_unit",
                "top_k": 20,
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "graph_api": {
                    "type": "neo4j_graph_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "path_select": {
                    "type": "fuzzy_one_hop_select",
                    "llm_client": llm_config,
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "graph_api": {
                        "type": "neo4j_graph_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "ppr_chunk_retriever_tool": {
                    "type": "ppr_chunk_retriever",
                    "llm_client": llm_config,
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "graph_api": {
                        "type": "neo4j_graph_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                    "ner": {
                        "type": "ner",
                        "kag_qa_task_config_key": kb_task_project_id,
                        "ner_prompt": {
                            "type": "default_question_ner",
                            "kag_qa_task_config_key": kb_task_project_id,
                        },
                        "std_prompt": {"type": "default_std"},
                        "llm_module": llm_config,
                    },
                },
                "entity_linking": {
                    "type": "entity_linking",
                    "recognition_threshold": 0.8,
                    "exclude_types": ["Chunk"],
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "graph_api": {
                        "type": "neo4j_graph_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "std_schema": {
                    "type": "default_std_schema",
                    "vectorize_model": vectorize_model_config,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "llm": llm_config,
                "kag_qa_task_config_key": kb_task_project_id,
            },
            {
                "type": "rc_default",
                "search_api": {
                    "type": "neo4j_search_api",
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "vector_chunk_retriever": {
                    "type": "vector_chunk_retriever",
                    "vectorize_model": vectorize_model_config,
                    "score_threshold": 0.65,
                    "search_api": {
                        "type": "neo4j_search_api",
                        "kag_qa_task_config_key": kb_task_project_id,
                    },
                    "kag_qa_task_config_key": kb_task_project_id,
                },
                "vectorize_model": vectorize_model_config,
                "top_k": 20,
                "kag_qa_task_config_key": kb_task_project_id,
            },
        ]
