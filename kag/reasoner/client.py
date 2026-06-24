# Server-free stand-in for knext.reasoner.client.ReasonerClient.
#
# The real ReasonerClient is a REST client to OpenSPG's (Scala) reasoner engine.
# SchemaUtils calls get_reason_schema() from get_schema_from_spg() (the default
# schema_file_name=="" path). To keep SchemaUtils 100% verbatim AND run without
# the server, this stand-in returns the schema built from the LOCAL YAML schema
# (the same file the ingestion pipeline uses), shaped exactly as the verbatim
# get_schema_from_spg expects (objects with name_en/name_zh/name/parent_type_name/
# properties/relations, properties exposing to_dict()). The YAML path comes from
# KAG_PROJECT_CONF.schema_path (or the INGEST_SCHEMA_PATH env var); if no schema
# is found, an empty schema is returned so SchemaUtils still constructs (identity
# label maps) rather than failing.


class _Attr:
    """Property/attribute view shaped for SchemaUtils._convert_spg_attr_set."""

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


class ReasonerClient:
    def __init__(self, host_addr=None, project_id=None, **kwargs):
        self.host_addr = host_addr
        self.project_id = project_id

    def get_reason_schema(self):
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
