# Minimal stand-in for knext.reasoner.client.ReasonerClient.
#
# The real ReasonerClient is a REST client to OpenSPG's (Scala) reasoner engine.
# SchemaUtils only calls it from get_schema_from_spg() (the schema_file_name=="" path).
# Server-free, the schema is supplied via the CSV path or our YAML SchemaClient, so
# this stand-in preserves the seam and errors clearly if the server path is taken.


class ReasonerClient:
    def __init__(self, host_addr=None, project_id=None, **kwargs):
        self.host_addr = host_addr
        self.project_id = project_id

    def get_reason_schema(self):
        raise NotImplementedError(
            "ReasonerClient.get_reason_schema requires the OpenSPG reasoner server; "
            "use a CSV schema (LogicFormConfiguration.schema_file_name) or the local "
            "YAML SchemaClient instead in the server-free build."
        )
