# Re-export shim: some extracted solver modules import LLMClient from
# kag.interface.common.llm_client directly. The server-free build keeps the
# minimal LLMClient seam in the interface package; re-export it here.
from kag.interface import LLMClient  # noqa: F401
