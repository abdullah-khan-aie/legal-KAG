import copy
import pprint
from typing import Any

from kag.common import generate_hash_id


class Node:
    id: str
    name: str
    label: str
    properties: dict[str, str]
    hash_map: dict[int, str] = dict()

    def __init__(self, _id: str, name: str, label: str, properties: dict[str, str]):
        self.name = name
        self.label = label
        self.properties = properties
        self.id = _id

    @property
    def hash_key(self):
        return generate_hash_id(f"{self.id}{self.name}{self.label}")

    @staticmethod
    def unique_key(spg_record):
        return spg_record.spg_type_name + "_" + spg_record.get_property("name", "")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "properties": copy.deepcopy(self.properties),
        }

    @classmethod
    def from_dict(cls, input: dict):
        return cls(
            _id=input["id"],
            name=input["name"],
            label=input["label"],
            properties=input.get("properties", {}),
        )

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.label == other.label
            and self.properties == other.properties
        )

    def __str__(self):
        return f"{self.name}[{self.label}]"


class Edge:
    id: str
    from_id: str
    from_type: str
    to_id: str
    to_type: str
    label: str
    properties: dict[str, str]

    def __init__(
        self,
        _id: str,
        from_node: Node,
        to_node: Node,
        label: str,
        properties: dict[str, str],
    ):
        self.from_id = from_node.id
        self.from_type = from_node.label
        self.to_id = to_node.id
        self.to_type = to_node.label
        self.label = label
        self.properties = properties
        if not _id:
            _id = id(self)
        self.id = _id

    @property
    def hash_key(self):
        return generate_hash_id(
            f"{self.from_id}{self.from_type}{self.to_id}{self.to_type}{self.label}{self.id}"
        )

    def __str__(self):
        return f"{self.from_id}[{self.from_type}]-[{self.label}]->{self.to_id}[{self.to_type}]"

    def to_dict(self):
        return {
            "id": self.id,
            "from": self.from_id,
            "to": self.to_id,
            "fromType": self.from_type,
            "toType": self.to_type,
            "label": self.label,
            "properties": copy.deepcopy(self.properties),
        }

    @classmethod
    def from_dict(cls, input: dict):
        return cls(
            _id=input["id"],
            from_node=Node(
                _id=input["from"],
                name=input["from"],
                label=input["fromType"],
                properties={},
            ),
            to_node=Node(_id=input["to"], name=input["to"], label=input["toType"], properties={}),
            label=input["label"],
            properties=input.get("properties", {}),
        )

    def __eq__(self, other):
        return (
            self.from_id == other.from_id
            and self.to_id == other.to_id
            and self.label == other.label
            and self.properties == other.properties
            and self.from_type == other.from_type
            and self.to_type == other.to_type
        )


class SubGraph:
    id: str
    nodes: list[Node] = list()
    edges: list[Edge] = list()

    def __init__(self, nodes: list[Node], edges: list[Edge]):
        self.nodes = nodes
        self.edges = edges

    def get_node_by_id(self, id, label):
        for n in self.nodes:
            if n.id == id and n.label == label:
                return n
        return None

    def add_node(self, id: str, name: str, label: str, properties=None):
        if not properties:
            properties = dict()
        store_node = self.get_node_by_id(id, label)
        if not store_node:
            self.nodes.append(Node(_id=id, name=name, label=label, properties=properties))
            return self
        if store_node and properties is not None:
            update_prop = dict(properties)
            update_prop.update(store_node.properties if store_node.properties else {})
            store_node.properties = update_prop
        return self

    def add_edge(self, s_id: str, s_label: str, p: str, o_id: str, o_label: str, properties=None):
        if not properties:
            properties = dict()
        s_node = Node(_id=s_id, name=s_id, label=s_label, properties={})
        o_node = Node(_id=o_id, name=o_id, label=o_label, properties={})
        self.edges.append(
            Edge(_id="", from_node=s_node, to_node=o_node, label=p, properties=properties)
        )
        return self

    def to_dict(self):
        return {
            "resultNodes": [n.to_dict() for n in self.nodes],
            "resultEdges": [e.to_dict() for e in self.edges],
        }

    def __repr__(self):
        return pprint.pformat(self.to_dict())

    def merge(self, sub_graph: "SubGraph"):
        self.nodes.extend(sub_graph.nodes)
        self.edges.extend(sub_graph.edges)

    @classmethod
    def from_dict(cls, input: dict[str, Any]):
        return cls(
            nodes=[Node.from_dict(node) for node in input["resultNodes"]],
            edges=[Edge.from_dict(edge) for edge in input["resultEdges"]],
        )

    @property
    def hash_key(self):
        keys = [x.hash_key for x in self.nodes] + [x.hash_key for x in self.edges]
        keys.sort()
        return generate_hash_id("".join(keys))
