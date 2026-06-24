# Re-export shim: extracted solver/prompt modules import VectorizeModelABC from
# kag.interface.common.vectorize_model directly. Re-export the package seam.
from kag.interface import VectorizeModelABC  # noqa: F401
