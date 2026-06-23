import hashlib
import re
from typing import TypeVar

Input = TypeVar("Input", contravariant=True)
Output = TypeVar("Output", covariant=True)


def generate_hash_id(value) -> str:
    if isinstance(value, dict):
        key = str(sorted(value.items()))
    else:
        key = str(value)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def processing_phrases(phrase):
    phrase = str(phrase)
    return re.sub("[^A-Za-z0-9 ]", " ", phrase.lower()).strip()


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


class KAGConstants:
    # vendored from kag.common.conf.KAGConstants (only what's used downstream)
    KAG_SIMILAR_EDGE_NAME = "similar"
