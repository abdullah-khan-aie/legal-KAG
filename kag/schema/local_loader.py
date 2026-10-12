"""Load the project schema from the local YAML into the shape ``SchemaUtils`` expects.

Server-free replacement for kag's ``ReasonerClient.get_reason_schema()``. Reads the local schema
YAML (``INGEST_SCHEMA_PATH`` / ``KAG_PROJECT_CONF.schema_path``) via ``SchemaClient``
and reshapes it into the lightweight type objects the solver's schema helpers
consume -- no server, no project_id, no host_addr.
"""

from __future__ import annotations


class _Attr:
    """Property view shaped for ``SchemaUtils._convert_spg_attr_set``."""

    def __init__(self, name, name_zh, constraint):
        self._name = name
        self._name_zh = name_zh
        self._constraint = constraint

    def to_dict(self):
        return {
            "name": self._name,
            "name_zh": self._name_zh,
            "constraint": self._constraint,
        }


class _Relation:
    def __init__(self, name, name_zh, object_type_name):
        self.name = name
        self.name_zh = name_zh
        self.object_type_name = object_type_name
        self.sub_properties = {}


class _SpgType:
    def __init__(self, name_en, name_zh, name, parent_type_name, properties, relations):
        self.name_en = name_en
        self.name_zh = name_zh
        self.name = name
        self.parent_type_name = parent_type_name
        self.properties = properties
        self.relations = relations


class LocalSchemaLoader:
    """Loads the local YAML schema into ``_SpgType`` objects for the solver."""

    @staticmethod
    def load():
        import os

        from kag.common.conf import KAG_PROJECT_CONF
        from kag.schema.client import SchemaClient

        schema_path = getattr(KAG_PROJECT_CONF, "schema_path", "") or os.environ.get(
            "INGEST_SCHEMA_PATH", ""
        )
        if not schema_path or not os.path.isfile(schema_path):
            return {}

        namespace = getattr(KAG_PROJECT_CONF, "namespace", "") or ""

        def _full(type_name):
            if not namespace or "." in type_name:
                return type_name
            return f"{namespace}.{type_name}"

        local_schema = SchemaClient(schema_path=schema_path).load()
        spg_schema = {}
        for type_name, spg_type in local_schema.items():
            properties = {}
            for prop_name, prop in spg_type.properties.items():
                properties[prop_name] = _Attr(prop.name, prop.name, getattr(prop, "constraint", []))
            relations = {}
            for rel_name, rel in getattr(spg_type, "relations", {}).items():
                relations[rel_name] = _Relation(rel.name, rel.name, _full(rel.object_type_name))
            full_name = _full(type_name)
            spg_schema[full_name] = _SpgType(
                name_en=type_name,
                name_zh=type_name,
                name=full_name,
                parent_type_name=None,
                properties=properties,
                relations=relations,
            )
        return spg_schema
