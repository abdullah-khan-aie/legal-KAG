import asyncio
import copy
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output, processing_phrases, to_camel_case
from kag.interface import ExternalGraphLoaderABC, ExtractorABC, LLMClient, PromptABC
from kag.schema.client import BASIC_TYPES, CHUNK_TYPE, SchemaClient, SpgTypeEnum

logger = logging.getLogger(__name__)


@ExtractorABC.register("schema_constraint")
@ExtractorABC.register("schema_constraint_extractor")
class SchemaConstraintExtractor(ExtractorABC):
    """
    Perform knowledge extraction for enforcing schema constraints, including entities, events and their edges.
    The types of entities and events, along with their respective attributes, are automatically inherited from the project's schema.
    """

    def __init__(
        self,
        llm: LLMClient,
        ner_prompt: PromptABC = None,
        std_prompt: PromptABC = None,
        relation_prompt: PromptABC = None,
        event_prompt: PromptABC = None,
        external_graph: ExternalGraphLoaderABC = None,
        **kwargs,
    ):
        """
        Initializes the SchemaBasedExtractor instance.

        Args:
            llm (LLMClient): The language model client used for extraction.
            ner_prompt (PromptABC, optional): The prompt for named entity recognition. Defaults to None.
            std_prompt (PromptABC, optional): The prompt for named entity standardization. Defaults to None.
            relation_prompt (PromptABC, optional): The prompt for relation extraction. Defaults to None.
            event_prompt (PromptABC, optional): The prompt for event extraction. Defaults to None.
            external_graph (ExternalGraphLoaderABC, optional): The external graph loader for additional data. Defaults to None.
        """
        super().__init__(**kwargs)
        self.llm = llm
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        type_names = [
            name for name, value in self.schema.items() if value.spg_type_enum != SpgTypeEnum.Index
        ]
        from kag.builder.prompt.ner import OpenIENERPrompt
        from kag.builder.prompt.std import OpenIEEntitystandardizationdPrompt

        self.ner_prompt = ner_prompt or OpenIENERPrompt(schema=type_names)
        self.std_prompt = std_prompt or OpenIEEntitystandardizationdPrompt()
        self.relation_prompt = relation_prompt
        self.event_prompt = event_prompt
        self.external_graph = external_graph

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
            if name not in dedup:
                dedup.add(name)
                output.append(
                    {
                        "name": name,
                        "category": item.label,
                        "properties": item.properties,
                    }
                )
        for item in ner_result:
            name = item.get("name", None)
            category = item.get("category", None)
            if name is None or category is None:
                continue
            if not isinstance(name, str):
                continue
            if name not in dedup:
                dedup.add(name)
                output.append(item)
        return output

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def named_entity_recognition(self, passage: str):
        """
        Performs named entity recognition on a given text passage.
        Args:
            passage (str): The text to perform named entity recognition on.
        Returns:
            The result of the named entity recognition operation.
        """
        ner_result = self._named_entity_recognition_llm(passage)
        return self._named_entity_recognition_process(passage, ner_result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def anamed_entity_recognition(self, passage: str):
        """
        Performs named entity recognition on a given text passage.
        Args:
            passage (str): The text to perform named entity recognition on.
        Returns:
            The result of the named entity recognition operation.
        """
        ner_result = await self._anamed_entity_recognition_llm(passage)
        return self._named_entity_recognition_process(passage, ner_result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def named_entity_standardization(self, passage: str, entities: list[dict]):
        """
        Performs named entity standardization on a given text passage and entities.

        Args:
            passage (str): The text passage.
            entities (List[Dict]): The list of entities to standardize.

        Returns:
            The result of the named entity standardization operation.
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
        """
        Performs named entity standardization on a given text passage and entities.

        Args:
            passage (str): The text passage.
            entities (List[Dict]): The list of entities to standardize.

        Returns:
            The result of the named entity standardization operation.
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
    def relations_extraction(self, passage: str, entities: list[dict]):
        """
        Performs relation extraction on a given text passage and entities.

        Args:
            passage (str): The text passage.
            entities (List[Dict]): The list of entities.

        Returns:
            The result of the relation extraction operation.
        """
        if self.relation_prompt is None:
            logger.debug("Relation extraction prompt not configured, skip.")

            return []
        return self.llm.invoke(
            {"input": passage, "entity_list": entities},
            self.relation_prompt,
            with_except=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def arelations_extraction(self, passage: str, entities: list[dict]):
        """
        Performs relation extraction on a given text passage and entities.

        Args:
            passage (str): The text passage.
            entities (List[Dict]): The list of entities.

        Returns:
            The result of the relation extraction operation.
        """
        if self.relation_prompt is None:
            logger.debug("Relation extraction prompt not configured, skip.")

            return []
        return await self.llm.ainvoke(
            {"input": passage, "entity_list": entities},
            self.relation_prompt,
            with_except=False,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    def event_extraction(self, passage: str):
        """
        Performs event extraction on a given text passage.

        Args:
            passage (str): The text passage.

        Returns:
            The result of the event extraction operation.
        """
        if self.event_prompt is None:
            logger.debug("Event extraction prompt not configured, skip.")
            return []
        return self.llm.invoke({"input": passage}, self.event_prompt, with_except=False)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def aevent_extraction(self, passage: str):
        """
        Performs event extraction on a given text passage.

        Args:
            passage (str): The text passage.

        Returns:
            The result of the event extraction operation.
        """
        if self.event_prompt is None:
            logger.debug("Event extraction prompt not configured, skip.")
            return []
        return await self.llm.ainvoke({"input": passage}, self.event_prompt, with_except=False)

    def parse_nodes_and_edges(self, entities: list[dict], category: str = None):
        """
        Parses nodes and edges from a list of entities.

        Args:
            entities (List[Dict]): The list of entities.

        Returns:
            Tuple[List[Node], List[Edge]]: The parsed nodes and edges.
        """
        graph = SubGraph([], [])
        entities = copy.deepcopy(entities)
        root_nodes = []
        for record in entities:
            if record is None:
                continue
            if isinstance(record, str):
                record = {"name": record}
            s_name = record.get("name", "")
            s_label = record.get("category", category)
            properties = record.get("properties", {})
            # At times, the name and/or label is placed in the properties.
            if not s_name:
                s_name = properties.pop("name", "")
            if not s_label:
                s_label = properties.pop("category", "")
            if not s_name or not s_label:
                continue
            s_name = processing_phrases(s_name)
            root_nodes.append((s_name, s_label))
            tmp_properties = copy.deepcopy(properties)
            spg_type = self.schema.get(s_label)
            for prop_name, prop_value in properties.items():
                if prop_value is None:
                    tmp_properties.pop(prop_name)
                    continue
                if prop_name in spg_type.properties:
                    prop_schema = spg_type.properties.get(prop_name)
                    o_label = prop_schema.object_type_name_en
                    if o_label not in BASIC_TYPES:
                        # pop and convert property to node and edge
                        if not isinstance(prop_value, list):
                            prop_value = [prop_value]
                        (
                            new_root_nodes,
                            new_nodes,
                            new_edges,
                        ) = self.parse_nodes_and_edges(prop_value, o_label)
                        graph.nodes.extend(new_nodes)
                        graph.edges.extend(new_edges)
                        # connect current node to property generated nodes
                        for node in new_root_nodes:
                            graph.add_edge(
                                s_id=s_name,
                                s_label=s_label,
                                p=prop_name,
                                o_id=node[0],
                                o_label=node[1],
                            )
                        tmp_properties.pop(prop_name)
            record["properties"] = tmp_properties
            # NOTE: For property converted to nodes/edges, we keep a copy of the original property values.
            #       Perhaps it is not necessary?
            graph.add_node(id=s_name, name=s_name, label=s_label, properties=properties)

            if "official_name" in record:
                official_name = processing_phrases(record["official_name"])
                if official_name != s_name:
                    graph.add_node(
                        id=official_name,
                        name=official_name,
                        label=s_label,
                        properties=dict(properties),
                    )
                    graph.add_edge(
                        s_id=s_name,
                        s_label=s_label,
                        p="OfficialName",
                        o_id=official_name,
                        o_label=s_label,
                    )

        return root_nodes, graph.nodes, graph.edges

    @staticmethod
    def add_relations_to_graph(sub_graph: SubGraph, entities: list[dict], relations: list[list]):
        """
        Add edges to the subgraph based on a list of relations and entities.
        Args:
            sub_graph (SubGraph): The subgraph to add edges to.
            entities (List[Dict]): A list of entities, for looking up category information.
            relations (List[list]): A list of relations, each representing a relationship to be added to the subgraph.
        Returns:
            The constructed subgraph.

        """

        for rel in relations:
            if len(rel) != 5:
                continue
            s_name, s_category, predicate, o_name, o_category = rel
            s_name = processing_phrases(s_name)
            sub_graph.add_node(s_name, s_name, s_category)
            o_name = processing_phrases(o_name)
            sub_graph.add_node(o_name, o_name, o_category)
            edge_type = to_camel_case(predicate)
            if edge_type:
                sub_graph.add_edge(s_name, s_category, edge_type, o_name, o_category)
        return sub_graph

    @staticmethod
    def add_chunk_to_graph(sub_graph: SubGraph, chunk: Chunk):
        """
        Associates a Chunk object with the subgraph, adding it as a node and connecting it with existing nodes.
        Args:
            sub_graph (SubGraph): The subgraph to add the chunk information to.
            chunk (Chunk): The chunk object containing the text and metadata.
        Returns:
            The constructed subgraph.
        """
        for node in sub_graph.nodes:
            sub_graph.add_edge(node.id, node.label, "source", chunk.id, CHUNK_TYPE)
        sub_graph.add_node(
            id=chunk.id,
            name=chunk.name,
            label=CHUNK_TYPE,
            properties={
                "id": chunk.id,
                "name": chunk.name,
                "content": f"{chunk.name}\n{chunk.content}",
                **chunk.kwargs,
            },
        )
        sub_graph.id = chunk.id
        return sub_graph

    def assemble_subgraph(
        self,
        chunk: Chunk,
        entities: list[dict],
        relations: list[list],
        events: list[dict],
    ):
        """
        Assembles a subgraph from the given chunk, entities, events, and relations.

        Args:
            chunk (Chunk): The chunk object.
            entities (List[Dict]): The list of entities.
            events (List[Dict]): The list of events.

        Returns:
            The constructed subgraph.
        """
        graph = SubGraph([], [])
        _, entity_nodes, entity_edges = self.parse_nodes_and_edges(entities)
        graph.nodes.extend(entity_nodes)
        graph.edges.extend(entity_edges)
        _, event_nodes, event_edges = self.parse_nodes_and_edges(events)
        graph.nodes.extend(event_nodes)
        graph.edges.extend(event_edges)
        self.add_relations_to_graph(graph, entities, relations)
        self.add_chunk_to_graph(graph, chunk)
        return graph

    @staticmethod
    def append_official_name(source_entities: list[dict], entities_with_official_name: list[dict]):
        """
        Appends official names to entities.

        Args:
            source_entities (List[Dict]): A list of source entities.
            entities_with_official_name (List[Dict]): A list of entities with official names.
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

    @staticmethod
    def postprocess_graph(graph):
        """
        Postprocesses the graph by merging nodes with the same name and label.

        Args:
            graph (SubGraph): The graph to postprocess.

        Returns:
            The postprocessed graph.
        """
        try:
            all_node_properties = {}
            for node in graph.nodes:
                id_ = node.id
                name = node.name
                label = node.label
                key = (id_, name, label)
                if key not in all_node_properties:
                    all_node_properties[key] = node.properties
                else:
                    all_node_properties[key].update(node.properties)
            new_graph = SubGraph([], [])
            for key, node_properties in all_node_properties.items():
                id_, name, label = key
                new_graph.add_node(id=id_, name=name, label=label, properties=node_properties)
            new_graph.edges = graph.edges
            return new_graph
        except:  # noqa: E722
            return graph

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """
        Invokes the extractor on the given input.

        Args:
            input (Input): The input data.
            **kwargs: Additional keyword arguments.

        Returns:
            List[Output]: The list of output results.
        """
        title = input.name
        passage = title + "\n" + input.content

        out = []
        entities = self.named_entity_recognition(passage)
        events = self.event_extraction(passage)
        named_entities = []
        for entity in entities:
            named_entities.append({"name": entity["name"], "category": entity["category"]})
        relations = self.relations_extraction(passage, named_entities)
        std_entities = self.named_entity_standardization(passage, named_entities)
        self.append_official_name(entities, std_entities)
        subgraph = self.assemble_subgraph(input, entities, relations, events)
        out.append(self.postprocess_graph(subgraph))
        logger.debug(f"input passage:\n{passage}")
        logger.debug(f"output graphs:\n{out}")
        return out

    async def _ainvoke(self, input: Input, **kwargs) -> list[Output]:
        """
        Invokes the extractor on the given input.

        Args:
            input (Input): The input data.
            **kwargs: Additional keyword arguments.

        Returns:
            List[Output]: The list of output results.
        """
        title = input.name
        passage = title + "\n" + input.content

        out = []
        entities, events = await asyncio.gather(
            self.anamed_entity_recognition(passage), self.aevent_extraction(passage)
        )
        named_entities = []
        for entity in entities:
            named_entities.append({"name": entity["name"], "category": entity["category"]})
        relations, std_entities = await asyncio.gather(
            self.arelations_extraction(passage, named_entities),
            self.anamed_entity_standardization(passage, named_entities),
        )

        self.append_official_name(entities, std_entities)
        subgraph = self.assemble_subgraph(input, entities, relations, events)
        out.append(self.postprocess_graph(subgraph))
        logger.debug(f"input passage:\n{passage}")
        logger.debug(f"output graphs:\n{out}")
        return out
