# Minimal stand-in for knext.common.rest (ApiClient / Configuration).
# Used only by the server-coupled open_spg_reporter, which streams results to the
# OpenSPG server UI. Server-free we use trace_log_reporter; these keep imports
# working without the REST SDK.


class Configuration:
    def __init__(self, host=None, **kwargs):
        self.host = host
        for k, v in kwargs.items():
            setattr(self, k, v)


class ApiClient:
    def __init__(self, configuration=None, **kwargs):
        self.configuration = configuration
