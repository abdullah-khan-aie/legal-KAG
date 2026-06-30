# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

from collections.abc import Sequence

from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output
from kag.interface import AlignerABC


@AlignerABC.register("kag")
class KAGAligner(AlignerABC):
    """Align and merge subgraphs into a single deduplicated subgraph."""

    def __init__(self, **kwargs):
        """Initialize the aligner, forwarding keyword arguments to the base class."""
        super().__init__(**kwargs)

    @property
    def input_types(self) -> type[Input]:
        return SubGraph

    @property
    def output_types(self) -> type[Output]:
        return SubGraph

    def invoke(self, input: list[SubGraph], **kwargs) -> SubGraph:
        """Merge subgraphs into one, skipping duplicate nodes and edges.

        Args:
            input: The subgraphs to merge.
        """
        merged_sub_graph = SubGraph(nodes=[], edges=[])
        for sub_graph in input:
            for node in sub_graph.nodes:
                if node not in merged_sub_graph.nodes:
                    merged_sub_graph.nodes.append(node)
            for edge in sub_graph.edges:
                if edge not in merged_sub_graph.edges:
                    merged_sub_graph.edges.append(edge)
        return merged_sub_graph

    def _handle(self, input: Sequence[dict]) -> dict:
        """Deserialize subgraph dicts, merge them, and serialize the result.

        Args:
            input: Dictionaries representing subgraphs.
        """
        _input = [self.input_types.from_dict(i) for i in input]
        _output = self.invoke(_input)
        return _output.to_dict()
