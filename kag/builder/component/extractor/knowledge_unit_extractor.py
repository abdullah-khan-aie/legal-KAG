import asyncio
import copy
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output, generate_hash_id, processing_phrases, to_camel_case
from kag.interface import ExternalGraphLoaderABC, ExtractorABC, LLMClient, PromptABC
from kag.schema.client import (  # noqa: F401
    BASIC_TYPES,
    CHUNK_TYPE,
    OTHER_TYPE,
    SchemaClient,
    SpgTypeEnum,
)

logger = logging.getLogger(__name__)


@ExtractorABC.register("knowledge_unit_extractor")
class KnowledgeUnitSchemaFreeExtractor(ExtractorABC):
    """Extract knowledge-unit subgraphs from text using an LLM.

    Attributes:
        llm: The large language model client used for text processing.
        schema: The schema client loaded for the project.
        ner_prompt: Prompt used for named entity recognition.
        kn_prompt: Prompt used for knowledge-unit extraction.
        triple_prompt: Prompt used for triple extraction.
        external_graph: External graph loader used for additional NER.
    """

    def __init__(
        self,
        llm: LLMClient,
        ner_prompt: PromptABC = None,
        kn_prompt: PromptABC = None,
        triple_prompt: PromptABC = None,
        external_graph: ExternalGraphLoaderABC = None,
        **kwargs,
    ):
        """Initialize the extractor with the LLM and per-task prompts.

        Args:
            llm: The large language model client.
            ner_prompt: Prompt for named entity recognition.
            kn_prompt: Prompt for knowledge-unit extraction.
            triple_prompt: Prompt for triple extraction.
            external_graph: External graph loader for additional NER.
        """
        super().__init__()
        self.llm = llm
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        self.ner_prompt = ner_prompt
        self.kn_prompt = kn_prompt
        self.triple_prompt = triple_prompt
        self.external_graph = external_graph

        self.SCHEMA_DICT = {
            "Geographic Location": "GeoLocation",
            "Location": "GeoLocation",
            "Science and Technology": "ScienceAndTechnology",
            "Culture and Entertainment": "CulturalAndEntertainment",
            "Policy and Regulation": "PolicyAndRegulation",
            "Science": "ScienceAndTechnology",
            "Culture": "CulturalAndEntertainment",
            "Policy": "PolicyAndRegulation",
            "Technology": "ScienceAndTechnology",
            "Entertainment": "CulturalAndEntertainment",
            "Regulation": "PolicyAndRegulation",
        }

    def get_stand_schema(self, type_name):
        return self.SCHEMA_DICT.get(type_name, type_name)

    @property
    def input_types(self) -> type[Input]:
        return Chunk

    @property
    def output_types(self) -> type[Output]:
        return SubGraph

    def _named_entity_recognition_llm(self, passage: str):
        ner_result = self.llm.invoke(
            {"input": passage},
            self.ner_prompt,
            with_except=False,
            with_json_parse=False,
        )
        return ner_result

    async def _anamed_entity_recognition_llm(self, passage: str):
        ner_result = await self.llm.ainvoke(
            {"input": passage},
            self.ner_prompt,
            with_except=False,
            with_json_parse=False,
        )
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
            label = self.get_stand_schema(label)
            spg_type = self.schema.get(label)
            if spg_type is None:
                label = "Others"
                spg_type = self.schema.get(label)
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
        ner_parse_rst = self._named_entity_recognition_process(passage, ner_result)
        if not ner_parse_rst:
            raise
        return ner_parse_rst

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
    def knowledge_unit_extra(self, passage: str, entities: list[dict]):
        """Extract knowledge units from the passage given its named entities.

        Args:
            passage: The source text passage.
            entities: The recognized named entities.
        """
        return self.llm.invoke(
            {"input": passage, "named_entities": entities},
            self.kn_prompt,
            with_except=False,
            with_json_parse=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def aknowledge_unit_extra(self, passage: str, entities: list[dict]):
        """Extract knowledge units from the passage given its named entities.

        Args:
            passage: The source text passage.
            entities: The recognized named entities.
        """
        return self.llm.invoke(
            {"input": passage, "named_entities": entities},
            self.kn_prompt,
            with_except=False,
            with_json_parse=False,
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
            with_json_parse=False,
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
            with_json_parse=False,
        )

    def assemble_sub_graph_with_spg_properties(
        self, sub_graph: SubGraph, s_id, s_name, s_label, record
    ):
        properties = record
        tmp_properties = copy.deepcopy(record)
        s_label = self.get_stand_schema(s_label)
        spg_type = self.schema.get(s_label)

        if spg_type is None:
            s_label = "Others"
            spg_type = self.schema.get(s_label)
        record["category"] = s_label

        domain_ontology = properties.get("ontology", "")
        domain_ontology_set = [
            item.strip() for item in domain_ontology.split("->") if len(item.strip()) > 0
        ]
        if domain_ontology_set:
            last_id = None
            # top-level ontology
            if len(domain_ontology_set) > 0:
                ontology = domain_ontology_set[0]
                sub_graph.add_node(id=ontology, name=ontology, label="SemanticConcept")
                last_id = ontology

            # intermediate node
            for i in range(1, len(domain_ontology_set)):
                ontology = domain_ontology_set[i]
                sub_graph.add_node(id=ontology, name=ontology, label="SemanticConcept")
                # semantic node; name == id as expected
                sub_graph.add_edge(
                    s_id=domain_ontology_set[i],
                    s_label="SemanticConcept",
                    p="isA",
                    o_id=domain_ontology_set[i - 1],
                    o_label="SemanticConcept",
                )
                last_id = domain_ontology_set[i - 1]

            # final node
            ontology = domain_ontology_set[-1]
            if (ontology not in s_name and s_label == "KnowledgeUnit") or ontology != s_name:
                sub_graph.add_node(
                    id=domain_ontology_set[-1],
                    name=domain_ontology_set[-1],
                    label="SemanticConcept",
                )

                last_id = domain_ontology_set[-1]
                if len(domain_ontology_set) > 1:
                    # semantic node; name == id as expected
                    sub_graph.add_edge(
                        s_id=domain_ontology_set[-1],
                        s_label="SemanticConcept",
                        p="isA",
                        o_id=domain_ontology_set[-2],
                        o_label="SemanticConcept",
                    )

            if last_id:
                # knowledge unit belongs to semantic node
                sub_graph.add_edge(
                    s_id=s_id,
                    s_label=s_label,
                    p="semantictype",
                    o_id=last_id,
                    o_label="SemanticConcept",
                )

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
                        # property edge; name == id as expected
                        if "relatedQuery" in prop_name:
                            sub_graph.add_edge(
                                # knowledge unit, semantic property edge
                                s_id=o_name,
                                s_label=o_label,
                                p=prop_name.replace("relatedQuery", "relatedTo"),
                                o_id=s_id,
                                o_label=s_label,
                            )
                        else:
                            sub_graph.add_edge(
                                # knowledge unit, semantic property edge
                                s_id=s_id,
                                s_label=s_label,
                                p=prop_name,
                                o_id=o_name,
                                o_label=o_label,
                            )
                    tmp_properties.pop(prop_name)
        record["properties"] = tmp_properties
        sub_graph.add_node(id=s_id, name=s_name, label=s_label, properties=record["properties"])

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

            self.assemble_sub_graph_with_spg_properties(sub_graph, s_name, s_name, s_label, record)
        return sub_graph, entities

    @staticmethod
    def assemble_sub_graph_with_triples(
        sub_graph: SubGraph, entities: list[dict], triples: list[list]
    ):
        """Add edges to the subgraph for each 4-element triple.

        Args:
            sub_graph: The subgraph to add edges to.
            entities: Entities used to look up category information.
            triples: Triples to add, each a [subject, predicate, object, condition]
                list.

        Returns:
            The updated subgraph.
        """

        def get_category_and_name(entities_data, entity_name):
            for entity in entities_data:
                if processing_phrases(entity["name"]) == processing_phrases(entity_name):
                    return entity["category"], entity["name"]
            return None, None

        for tri in triples:
            if len(tri) != 4:
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
            properties = None
            if tri[3] != "":
                properties = {"condition": tri[3]}
            #  s_name: head entity, o_name: tail entity
            if edge_type:
                sub_graph.add_edge(
                    s_name,
                    s_category,
                    edge_type,
                    o_name,
                    o_category,
                    properties=properties,
                )
        return sub_graph

    @staticmethod
    def assemble_sub_graph_with_chunk(sub_graph: SubGraph, entities: list[dict], chunk: Chunk):
        """Add the chunk as a node and link the given entities to it as their source.

        Args:
            sub_graph: The subgraph to add the chunk information to.
            entities: Entities to link to the chunk.
            chunk: The chunk providing the text and metadata.

        Returns:
            The updated subgraph.
        """
        for entity in entities:
            # to chunk.id,
            sub_graph.add_edge(
                entity.get("name"),
                entity.get("category"),
                "source",
                chunk.id,
                CHUNK_TYPE,
            )
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
        """Integrate triples and the chunk into the subgraph.

        Args:
            sub_graph: The subgraph to assemble into.
            chunk: The chunk the subgraph is about.
            entities: Entities identified in the chunk.
            triples: Triples representing relationships between entities.

        Returns:
            The assembled subgraph.
        """
        self.assemble_sub_graph_with_triples(sub_graph, entities, triples)
        self.assemble_sub_graph_with_chunk(sub_graph, entities, chunk)
        return sub_graph

    def assemble_knowledge_unit(
        self,
        sub_graph: SubGraph,
        source_entities: list[dict],
        input_knowledge_units: dict[str, dict],
        triples: list[list],
    ):
        knowledge_unit_nodes = []
        knowledge_units = dict(input_knowledge_units)

        def triple_to_knowledge_unit(triple):
            ret = {}
            name = " ".join(triple)
            ret["content"] = name
            ret["knowledgetype"] = "triple"
            ret["core_entities"] = ",".join(triple)
            return name, ret

        for tri in triples:
            knowledge_unit_name, knowledge_unit_value = triple_to_knowledge_unit(tri)
            if knowledge_unit_name not in knowledge_units:
                knowledge_units[knowledge_unit_name] = knowledge_unit_value

        for knowledge_name, knowledge_value in knowledge_units.items():
            if knowledge_value["knowledgetype"] == "triple":
                knowledge_id = knowledge_name
            else:
                knowledge_id = generate_hash_id(
                    f"{knowledge_name}_{knowledge_value['content'].strip()[:100]}"
                )
            self.assemble_sub_graph_with_spg_properties(
                sub_graph,
                knowledge_id,
                knowledge_name,
                "KnowledgeUnit",
                knowledge_value,
            )
            sub_graph.add_node(
                knowledge_id,
                knowledge_name,
                "KnowledgeUnit",
                knowledge_value,
            )
            knowledge_unit_nodes.append({"name": knowledge_id, "category": "KnowledgeUnit"})
            core_entities = {}
            for item in knowledge_value.get("core_entities", "").split(","):
                if not item.strip():
                    continue
                core_entities[item.strip()] = "Others"

            for core_entity, ent_type in core_entities.items():
                if core_entity == "":
                    continue
                found_in_source_entity = None
                for source_entity in source_entities:
                    if core_entity == source_entity.get("name", ""):
                        found_in_source_entity = source_entity
                        break
                ent_type = self.get_stand_schema(ent_type)
                if found_in_source_entity is None:
                    found_in_source_entity = {"name": core_entity, "category": ent_type}
                    sub_graph.add_node(core_entity, core_entity, ent_type, {})
                sub_graph.add_edge(
                    found_in_source_entity.get("name"),
                    found_in_source_entity.get("category"),
                    "source",
                    knowledge_id,
                    "KnowledgeUnit",
                )
        return knowledge_unit_nodes

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """Extract entities, knowledge units, and triples from the chunk into a subgraph.

        Args:
            input: The chunk to process.
        """

        title = input.name
        passage = title.split("_split_")[0] + "\n" + input.content
        out = []
        entities = self.named_entity_recognition(passage)
        sub_graph, entities = self.assemble_sub_graph_with_spg_records(entities)
        filtered_entities = [
            {k: v for k, v in ent.items() if k in ["name", "category"]} for ent in entities
        ]
        knowledge_unit_entities = self.knowledge_unit_extra(passage, filtered_entities)
        triples = self.triples_extraction(passage, filtered_entities)

        knowledge_unit_nodes = self.assemble_knowledge_unit(
            sub_graph, entities, knowledge_unit_entities, triples
        )
        union_entities = entities + knowledge_unit_nodes
        self.assemble_sub_graph(sub_graph, input, union_entities, triples)
        out.append(sub_graph)
        return out

    async def _ainvoke(self, input: Input, **kwargs) -> list[Output]:
        """Extract entities, knowledge units, and triples from the chunk into a subgraph.

        Args:
            input: The chunk to process.
        """
        title = input.name
        passage = title.split("_split_")[0] + "\n" + input.content
        out = []
        entities = await self.anamed_entity_recognition(passage)
        sub_graph, entities = self.assemble_sub_graph_with_spg_records(entities)
        filtered_entities = [
            {k: v for k, v in ent.items() if k in ["name", "category"]} for ent in entities
        ]

        triples, knowledge_unit_entities = await asyncio.gather(
            self.atriples_extraction(passage, filtered_entities),
            self.aknowledge_unit_extra(passage, filtered_entities),
        )

        knowledge_unit_nodes = self.assemble_knowledge_unit(
            sub_graph, entities, knowledge_unit_entities, triples
        )
        union_entities = entities + knowledge_unit_nodes
        self.assemble_sub_graph(sub_graph, input, union_entities, triples)
        out.append(sub_graph)
        return out
