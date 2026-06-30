# Partial vendoring of kag/interface/builder/base.py (openspg-kag 0.8.0, Apache-2.0).
# Only BuilderComponentData is kept: it is the lightweight data wrapper the readers
# reference. The heavy BuilderComponent / MPBuilderComponentWrapper bases are
# replaced by the consolidated component bases in kag.interface, so they are not
# vendored here. Logic of BuilderComponentData is verbatim (import stand-in only).

from typing import Any

from kag.common import generate_hash_id


class BuilderComponentData:
    def __init__(self, data: Any, hash_key: str = None, suffix: str = ""):
        self.data = data
        if not hash_key:
            hash_key = self.get_object_hash_key(self.data)
        self.hash_key = f"{hash_key}->{suffix}"

    def get_object_hash_key(self, input_object):
        if hasattr(input_object, "hash_key"):
            return getattr(input_object, "hash_key")
        return generate_hash_id(input_object)

    def to_dict(self):
        if hasattr(self.data, "to_dict"):
            return self.data.to_dict()
        raise NotImplementedError(
            f"data type {type(self.data)} do not implemente method `to_dict`."
        )
