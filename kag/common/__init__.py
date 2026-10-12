#   - Input/Output: from knext.common.base.runnable (type vars)
#   - generate_hash_id, processing_phrases, to_camel_case: from kag.common.utils
#   - escape_single_quotes: from kag.common.utils

import hashlib
import re
from typing import TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")


def generate_hash_id(value) -> str:
    if isinstance(value, dict):
        key = str(sorted(value.items()))
    else:
        key = str(value)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def processing_phrases(phrase):
    phrase = str(phrase)
    return re.sub("[^A-Za-z0-9一-龥 ]", " ", phrase.lower()).strip()


def to_camel_case(phrase):
    s = processing_phrases(phrase).replace(" ", "_")
    return "".join(word.capitalize() if i != 0 else word for i, word in enumerate(s.split("_")))


def to_snake_case(name):
    words = re.findall("[A-Za-z][a-z0-9]*", name)
    result = "_".join(words).lower()
    return result


def get_vector_field_name(property_key: str):
    name = f"{property_key}_vector"
    name = to_snake_case(name)
    return "_" + name


def get_sparse_vector_field_name(property_key: str):
    name = f"{property_key}_sparse"
    name = to_snake_case(name)
    return "_" + name


def escape_single_quotes(s: str):
    return s.replace("'", "\\'")


class KAGConstants:
    # vendored from kag.common.conf.KAGConstants (only what's used downstream)
    KAG_SIMILAR_EDGE_NAME = "similar"
