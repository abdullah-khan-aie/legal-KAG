# Minimal reasoner package. ReasonerApi is the server REST client used by the
# server-coupled open_spg_reporter; server-free it is never invoked.
class ReasonerApi:
    def __init__(self, api_client=None, **kwargs):
        self.api_client = api_client

    def __getattr__(self, name):
        def _server_only(*args, **kwargs):
            raise NotImplementedError(
                "ReasonerApi streams to the OpenSPG server and is not available "
                "in the server-free build; use trace_log_reporter instead."
            )

        return _server_only
