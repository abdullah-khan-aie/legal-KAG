# Local, dependency-free replacement for knext.schema.client.SchemaClient.
#
# The server SchemaClient.load() does a REST call and returns {type_name: SpgType}.
# This one reads a LOCAL YAML file and returns the same shape, so the extractor
# (and the NER prompt) get their type vocabulary without any OpenSPG server.
#
# The objects expose exactly what the extractor uses:
#   - SpgType.spg_type_enum   (to filter out Index types in the NER prompt)
#   - SpgType.properties      (dict: prop_name -> Property)
#   - Property.object_type_name_en   (the property's value type, e.g. "Text"/"Person")

import os
from enum import Enum

# ---- constants (from knext.schema.client) --------------------------------- #
CHUNK_TYPE = "Chunk"
TABLE_TYPE = "Table"
OTHER_TYPE = "Others"
TEXT_TYPE = "Text"
INTEGER_TYPE = "Integer"
FLOAT_TYPE = "Float"
BASIC_TYPES = [TEXT_TYPE, INTEGER_TYPE, FLOAT_TYPE]


class SpgTypeEnum(str, Enum):  # noqa: UP042
    Basic = "BASIC_TYPE"
    Standard = "STANDARD_TYPE"
    Entity = "ENTITY_TYPE"
    Index = "INDEX_TYPE"
    Event = "EVENT_TYPE"
    Concept = "CONCEPT_TYPE"


class IndexTypeEnum(str, Enum):  # noqa: UP042
    Vector = "VECTOR"
    SparseVector = "SPARSE_VECTOR"
    Text = "TEXT"
    TextAndVector = "TEXT_AND_VECTOR"
    TextAndSparseVector = "TEXT_AND_SPARSE_VECTOR"


# from knext.schema.model.base.ConstraintTypeEnum (values used by spg_prompt)
class ConstraintTypeEnum(str, Enum):  # noqa: UP042
    NotNull = "NOT_NULL"
    MultiValue = "MULTI_VALUE"
    Enum = "ENUM"


# knext.schema.model.schema_helper.SPGTypeName is a str alias; used only as a hint
SPGTypeName = str


# accept friendly YAML index values: TextAndVector / TEXT_AND_VECTOR / Vector ...
_INDEX_ALIASES = {
    "VECTOR": IndexTypeEnum.Vector,
    "SPARSEVECTOR": IndexTypeEnum.SparseVector,
    "SPARSE_VECTOR": IndexTypeEnum.SparseVector,
    "TEXT": IndexTypeEnum.Text,
    "TEXTANDVECTOR": IndexTypeEnum.TextAndVector,
    "TEXT_AND_VECTOR": IndexTypeEnum.TextAndVector,
    "TEXTANDSPARSEVECTOR": IndexTypeEnum.TextAndSparseVector,
    "TEXT_AND_SPARSE_VECTOR": IndexTypeEnum.TextAndSparseVector,
}


# accept friendly YAML values: ENTITY / EntityType / ENTITY_TYPE ...
_TYPE_ALIASES = {
    "ENTITY": SpgTypeEnum.Entity,
    "ENTITYTYPE": SpgTypeEnum.Entity,
    "ENTITY_TYPE": SpgTypeEnum.Entity,
    "CONCEPT": SpgTypeEnum.Concept,
    "CONCEPTTYPE": SpgTypeEnum.Concept,
    "CONCEPT_TYPE": SpgTypeEnum.Concept,
    "EVENT": SpgTypeEnum.Event,
    "EVENTTYPE": SpgTypeEnum.Event,
    "EVENT_TYPE": SpgTypeEnum.Event,
    "STANDARD": SpgTypeEnum.Standard,
    "STANDARD_TYPE": SpgTypeEnum.Standard,
    "BASIC": SpgTypeEnum.Basic,
    "BASIC_TYPE": SpgTypeEnum.Basic,
    "INDEX": SpgTypeEnum.Index,
    "INDEX_TYPE": SpgTypeEnum.Index,
}


class Property:
    """Mirrors the knext Property fields the SPG prompts + constraint extractor read.

    Fields consumed downstream:
      - name                  property name
      - object_type_name      value/target type (spg_prompt uses .split('.')[-1])
      - object_type_name_en   short value type (extractor compares vs BASIC_TYPES)
      - constraint            list of ConstraintTypeEnum values (e.g. "MULTI_VALUE")
      - desc                  optional description (rendered into the prompt)
      - index_type            index config for the vectorizer / graph store
    """

    def __init__(
        self,
        name: str,
        object_type_name_en: str,
        index_type: IndexTypeEnum = IndexTypeEnum.Text,
        object_type_name: str = None,
        constraint=None,
        desc: str = "",
    ):
        self.name = name
        self.object_type_name_en = object_type_name_en
        self.object_type_name = object_type_name or object_type_name_en
        self.index_type = index_type
        self.constraint = constraint or []
        self.desc = desc


class Relation:
    """Mirrors the knext Relation fields spg_prompt.create_prompt_schema reads."""

    def __init__(self, name: str, object_type_name: str, desc: str = ""):
        self.name = name
        self.object_type_name = object_type_name
        self.object_type_name_en = object_type_name
        self.desc = desc


class SpgType:
    def __init__(
        self,
        name: str,
        spg_type_enum: SpgTypeEnum,
        properties: dict[str, Property],
        desc: str = "",
        relations=None,
    ):
        self.name = name
        self.name_en = name
        self.name_zh = name
        self.spg_type_enum = spg_type_enum
        self.properties = properties or {}
        self.desc = desc
        self.relations = relations or {}


class SchemaClient:
    """Reads a local YAML schema file and exposes it like the server client.

    YAML format:
        namespace: LegalKB
        types:
          Contract:
            type: ENTITY
            properties:
              name: Text
              governingLaw: GeographicLocation
              party: Person
          Person:
            type: ENTITY
            properties:
              name: Text
    """

    def __init__(self, schema_path: str = None, project_id=None, host_addr=None):
        # project_id/host_addr accepted but ignored (compat with the old signature)
        self.schema_path = schema_path

    def load(self) -> dict[str, SpgType]:
        types: dict[str, SpgType] = {}
        data = {}
        if self.schema_path and os.path.isfile(self.schema_path):
            import yaml  # local dependency; not the OpenSPG server

            with open(self.schema_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        for type_name, spec in (data.get("types") or {}).items():
            spec = spec or {}
            raw_type = str(spec.get("type", "ENTITY")).upper().replace(" ", "")
            enum = _TYPE_ALIASES.get(raw_type, SpgTypeEnum.Entity)
            type_desc = str(spec.get("desc", ""))
            props = {}
            for pname, pspec in (spec.get("properties") or {}).items():
                # property may be `name: Text` (simple) or a dict with optional
                # `index` (vector index), `desc`, and `multi` (MultiValue constraint):
                #   party: {type: Person, multi: true, desc: a contracting party}
                if isinstance(pspec, dict):
                    ptype = str(pspec.get("type", "Text"))
                    raw_idx = str(pspec.get("index", "TEXT")).upper().replace(" ", "")
                    idx = _INDEX_ALIASES.get(raw_idx, IndexTypeEnum.Text)
                    pdesc = str(pspec.get("desc", ""))
                    constraint = [ConstraintTypeEnum.MultiValue.value] if pspec.get("multi") else []
                else:
                    ptype = str(pspec)
                    idx = IndexTypeEnum.Text
                    pdesc = ""
                    constraint = []
                props[pname] = Property(
                    pname,
                    ptype,
                    idx,
                    object_type_name=ptype,
                    constraint=constraint,
                    desc=pdesc,
                )
            relations = {}
            for rname, rspec in (spec.get("relations") or {}).items():
                if isinstance(rspec, dict):
                    rtype = str(rspec.get("type", OTHER_TYPE))
                    rdesc = str(rspec.get("desc", ""))
                else:
                    rtype = str(rspec)
                    rdesc = ""
                relations[rname] = Relation(rname, rtype, rdesc)
            types[type_name] = SpgType(type_name, enum, props, desc=type_desc, relations=relations)

        # built-in base types the extractor relies on (server always has these):
        # unknown entities fall back to "Others", and chunks link via "Chunk".
        for builtin in (OTHER_TYPE, CHUNK_TYPE):
            types.setdefault(builtin, SpgType(builtin, SpgTypeEnum.Entity, {}))
        return types
