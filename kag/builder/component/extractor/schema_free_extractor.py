import asyncio
import copy
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output, processing_phrases, to_camel_case
from kag.interface import ExternalGraphLoaderABC, ExtractorABC, LLMClient, PromptABC
from kag.schema.client import (
    BASIC_TYPES,
    CHUNK_TYPE,
    OTHER_TYPE,
    SchemaClient,
    SpgTypeEnum,
)

logger = logging.getLogger(__name__)


@ExtractorABC.register("schema_free")
@ExtractorABC.register("schema_free_extractor")
class SchemaFreeExtractor(ExtractorABC):
    """Extract schema-free knowledge graph subgraphs from text using an LLM.

    Attributes:
        llm: The large language model client used for text processing.
        schema: The schema client loaded for the project.
        ner_prompt: Prompt used for named entity recognition.
        std_prompt: Prompt used for entity standardization.
        triple_prompt: Prompt used for triple extraction.
        external_graph: External graph loader used for additional NER.
    """

    def __init__(
        self,
        llm: LLMClient,
        ner_prompt: PromptABC = None,
        std_prompt: PromptABC = None,
        triple_prompt: PromptABC = None,
        external_graph: ExternalGraphLoaderABC = None,
        **kwargs,
    ):
        """Initialize the extractor with the LLM and per-task prompts.

        Args:
            llm: The large language model client.
            ner_prompt: Prompt for named entity recognition; defaults to a built-in.
            std_prompt: Prompt for entity standardization; defaults to a built-in.
            triple_prompt: Prompt for triple extraction; defaults to a built-in.
            external_graph: External graph loader for additional NER.
        """
        super().__init__(**kwargs)
        self.llm = llm
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        type_names = [
            name for name, value in self.schema.items() if value.spg_type_enum != SpgTypeEnum.Index
        ]
        from kag.builder.prompt.ner import OpenIENERPrompt
        from kag.builder.prompt.std import (
            OpenIEEntitystandardizationdPrompt,
        )
        from kag.builder.prompt.triple import OpenIETriplePrompt

        self.ner_prompt = ner_prompt or OpenIENERPrompt(schema=type_names)
        self.std_prompt = std_prompt or OpenIEEntitystandardizationdPrompt()
        self.triple_prompt = triple_prompt or OpenIETriplePrompt()
        self.external_graph = external_graph

        from kag.builder.component.extractor.table_extractor import TableExtractor
        from kag.builder.prompt.table.table_context import TableContextPrompt
        from kag.builder.prompt.table.table_row_col_summary import (
            TableRowColSummaryPrompt,
        )

        self.table_extractor = TableExtractor(
            llm=self.llm,
            table_context_prompt=TableContextPrompt(),
            table_row_col_summary_prompt=TableRowColSummaryPrompt(),
        )

    @property
    def input_types(self) -> type[Input]:
        return Chunk

    @property
    def output_types(self) -> type[Output]:
        return SubGraph

    @staticmethod
    def output_indices() -> list[str]:
        return ["spo_graph_index", "chunk_index"]

    def _named_entity_recognition_llm(self, passage: str):
        ner_result = self.llm.invoke({"input": passage}, self.ner_prompt, with_except=False)
        return ner_result

    async def _anamed_entity_recognition_llm(self, passage: str):
        ner_result = await self.llm.ainvoke({"input": passage}, self.ner_prompt, with_except=False)
        return ner_result

    def _named_entity_recognition_process(self, passage, ner_result):
        if self.external_graph:
            extra_ner_result = self.external_graph.ner(passage)
        else:
            extra_ner_result = []
        output = []
        dedup = set()
        for item in extra_ner_result:
            name = item.name
            label = item.label
            spg_type = self.schema.get(label)
            if spg_type is None:
                label = "Others"
                item.label = label
            description = item.properties.get("desc", "")
            semantic_type = item.properties.get("semanticType", label)
            if name not in dedup:
                dedup.add(name)
                output.append(
                    {
                        "name": name,
                        "type": semantic_type,
                        "category": label,
                        "description": description,
                    }
                )
        for item in ner_result:
            name = item.get("name", None)
            if name and name not in dedup:
                dedup.add(name)
                output.append(item)
        return output

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def named_entity_recognition(self, passage: str):
        """Recognize named entities in a text passage.

        Args:
            passage: The text to run named entity recognition on.
        """
        ner_result = self._named_entity_recognition_llm(passage)
        return self._named_entity_recognition_process(passage, ner_result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def anamed_entity_recognition(self, passage: str):
        """Recognize named entities in a text passage.

        Args:
            passage: The text to run named entity recognition on.
        """
        ner_result = await self._anamed_entity_recognition_llm(passage)
        return self._named_entity_recognition_process(passage, ner_result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def named_entity_standardization(self, passage: str, entities: list[dict]):
        """Standardize recognized named entities.

        Args:
            passage: The source text passage.
            entities: The recognized entities to standardize.
        """
        return self.llm.invoke(
            {"input": passage, "named_entities": entities},
            self.std_prompt,
            with_except=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def anamed_entity_standardization(self, passage: str, entities: list[dict]):
        """Standardize recognized named entities.

        Args:
            passage: The source text passage.
            entities: The recognized entities to standardize.
        """
        return await self.llm.ainvoke(
            {"input": passage, "named_entities": entities},
            self.std_prompt,
            with_except=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def triples_extraction(self, passage: str, entities: list[dict]):
        """Extract subject-predicate-object triples from a text passage.

        Args:
            passage: The text to extract triples from.
            entities: Entities identified in the text.
        """
        return self.llm.invoke(
            {"input": passage, "entity_list": entities},
            self.triple_prompt,
            with_except=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def atriples_extraction(self, passage: str, entities: list[dict]):
        """Extract subject-predicate-object triples from a text passage.

        Args:
            passage: The text to extract triples from.
            entities: Entities identified in the text.
        """

        return await self.llm.ainvoke(
            {"input": passage, "entity_list": entities},
            self.triple_prompt,
            with_except=False,
        )

    def assemble_sub_graph_with_spg_records(self, entities: list[dict]):
        """Build a subgraph from SPG records, expanding object-typed properties into nodes.

        Args:
            entities: Entities to assemble into the subgraph.

        Returns:
            A tuple of (assembled subgraph, updated entities).
        """
        sub_graph = SubGraph([], [])
        for record in entities:
            s_name = record.get("name", "")
            s_label = record.get("category", "")
            properties = record.get("properties", {})
            tmp_properties = copy.deepcopy(properties)
            spg_type = self.schema.get(s_label)
            if spg_type is None:
                s_label = "Others"
                spg_type = self.schema.get(s_label)
            for prop_name, prop_value in properties.items():
                if prop_value == "NAN":
                    tmp_properties.pop(prop_name)
                    continue
                if prop_name in spg_type.properties:
                    from kag.schema.client import Property

                    prop: Property = spg_type.properties.get(prop_name)
                    o_label = prop.object_type_name_en
                    if o_label not in BASIC_TYPES:
                        if isinstance(prop_value, str):
                            prop_value = [prop_value]
                        for o_name in prop_value:
                            sub_graph.add_node(id=o_name, name=o_name, label=o_label)
                            sub_graph.add_edge(
                                s_id=s_name,
                                s_label=s_label,
                                p=prop_name,
                                o_id=o_name,
                                o_label=o_label,
                            )
                        tmp_properties.pop(prop_name)
            record["properties"] = tmp_properties
            sub_graph.add_node(id=s_name, name=s_name, label=s_label, properties=properties)
        return sub_graph, entities

    @staticmethod
    def assemble_sub_graph_with_triples(
        sub_graph: SubGraph, entities: list[dict], triples: list[list]
    ):
        """Add edges to the subgraph for each triple.

        Args:
            sub_graph: The subgraph to add edges to.
            entities: Entities used to look up category information.
            triples: Triples to add, each a [subject, predicate, object] list.

        Returns:
            The updated subgraph.
        """

        def get_category_and_name(entities_data, entity_name):
            for entity in entities_data:
                if processing_phrases(entity["name"]) == processing_phrases(entity_name):
                    return entity["category"], entity["name"]
            return None, None

        for tri in triples:
            if tri is None or len(tri) != 3:
                continue
            s_category, s_name = get_category_and_name(entities, tri[0])
            tri[0] = processing_phrases(tri[0])
            if tri[0] == "":
                continue
            if s_category is None:
                s_category = OTHER_TYPE
                s_name = tri[0]
                sub_graph.add_node(s_name, s_name, s_category)
            o_category, o_name = get_category_and_name(entities, tri[2])
            if o_name == "":
                continue
            if o_category is None:
                o_name = processing_phrases(tri[2])
                o_category = OTHER_TYPE
                sub_graph.add_node(o_name, o_name, o_category)
            edge_type = to_camel_case(tri[1])
            if edge_type:
                sub_graph.add_edge(s_name, s_category, edge_type, o_name, o_category)

        return sub_graph

    @staticmethod
    def assemble_sub_graph_with_chunk(sub_graph: SubGraph, chunk: Chunk):
        """Add the chunk as a node and link every existing node to it as its source.

        Args:
            sub_graph: The subgraph to add the chunk information to.
            chunk: The chunk providing the text and metadata.

        Returns:
            The updated subgraph.
        """
        for node in sub_graph.nodes:
            sub_graph.add_edge(node.id, node.label, "source", chunk.id, CHUNK_TYPE)
        sub_graph.add_node(
            chunk.id,
            chunk.name,
            CHUNK_TYPE,
            {
                "id": chunk.id,
                "name": chunk.name,
                "content": f"{chunk.name}\n{chunk.content}",
                **chunk.kwargs,
            },
        )
        sub_graph.id = chunk.id
        return sub_graph

    def assemble_sub_graph(
        self,
        sub_graph: SubGraph,
        chunk: Chunk,
        entities: list[dict],
        triples: list[list],
    ):
        """Integrate entities, triples, and the chunk into a single subgraph.

        Args:
            sub_graph: The subgraph to assemble into.
            chunk: The chunk the subgraph is about.
            entities: Entities identified in the chunk.
            triples: Triples representing relationships between entities.

        Returns:
            The assembled subgraph.
        """
        self.assemble_sub_graph_with_entities(sub_graph, entities)
        self.assemble_sub_graph_with_triples(sub_graph, entities, triples)
        self.assemble_sub_graph_with_chunk(sub_graph, chunk)
        return sub_graph

    @staticmethod
    def assemble_sub_graph_with_entities(sub_graph: SubGraph, entities: list[dict]):
        """Add entity nodes (and official-name nodes/edges) to the subgraph.

        Args:
            sub_graph: The subgraph to assemble into.
            entities: Entity information to add.
        """

        for ent in entities:
            name = processing_phrases(ent["name"])
            sub_graph.add_node(
                name,
                name,
                ent["category"],
                {
                    "desc": ent.get("description", ""),
                    "semanticType": ent.get("type", ""),
                    **ent.get("properties", {}),
                },
            )

            if "official_name" in ent:
                official_name = processing_phrases(ent["official_name"])
                if official_name != name:
                    sub_graph.add_node(
                        official_name,
                        official_name,
                        ent["category"],
                        {
                            "desc": ent.get("description", ""),
                            "semanticType": ent.get("type", ""),
                            **ent.get("properties", {}),
                        },
                    )
                    sub_graph.add_edge(
                        name,
                        ent["category"],
                        "OfficialName",
                        official_name,
                        ent["category"],
                    )

    def append_official_name(
        self, source_entities: list[dict], entities_with_official_name: list[dict]
    ):
        """Copy official names onto matching source entities in place.

        Args:
            source_entities: Entities to annotate.
            entities_with_official_name: Entities carrying official names.
        """
        try:
            tmp_dict = {}
            for tmp_entity in entities_with_official_name:
                if "name" in tmp_entity:
                    name = tmp_entity["name"]
                elif "entity" in tmp_entity:
                    name = tmp_entity["entity"]
                else:
                    continue
                category = tmp_entity["category"]
                if self.schema.get(category, None) is None:
                    category = "Others"
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
        except Exception as e:
            logger.warn(f"failed to process official name, info: {e}")

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """Extract entities and triples from the chunk into a subgraph.

        Args:
            input: The chunk to process.
        """
        print("Enter schema free extractor======================")
        logger.info("Enter schema free extractor======================")
        title = input.name
        passage = title + "\n" + input.content
        out = []
        entities = self.named_entity_recognition(passage)
        sub_graph, entities = self.assemble_sub_graph_with_spg_records(entities)
        filtered_entities = [
            {k: v for k, v in ent.items() if k in ["name", "category"]} for ent in entities
        ]
        triples = (self.triples_extraction(passage, filtered_entities),)
        std_entities = self.named_entity_standardization(passage, filtered_entities)
        self.append_official_name(entities, std_entities)
        self.assemble_sub_graph(sub_graph, input, entities, triples)
        out.append(sub_graph)
        print("Exit schema free extractor=================")
        logger.info("Exit schema free extractor=================")
        return out

    async def _ainvoke(self, input: Input, **kwargs) -> list[Output]:
        """Extract entities and triples from the chunk into a subgraph.

        Args:
            input: The chunk to process.
        """

        if self.table_extractor is not None and input.type == ChunkTypeEnum.Table:
            return self.table_extractor._invoke(input)

        title = input.name
        passage = title + "\n" + input.content
        out = []
        entities = await self.anamed_entity_recognition(passage)
        sub_graph, entities = self.assemble_sub_graph_with_spg_records(entities)
        filtered_entities = [
            {k: v for k, v in ent.items() if k in ["name", "category"]} for ent in entities
        ]
        triples, std_entities = await asyncio.gather(
            self.atriples_extraction(passage, filtered_entities),
            self.anamed_entity_standardization(passage, filtered_entities),
        )

        self.append_official_name(entities, std_entities)
        self.assemble_sub_graph(sub_graph, input, entities, triples)
        out.append(sub_graph)
        return out
