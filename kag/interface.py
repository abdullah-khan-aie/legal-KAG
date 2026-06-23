import copy
import json
from abc import ABC
from string import Template

from common import Input, Output


class ReaderABC:
    def __init__(self, **kwargs):
        self.language = kwargs.pop("language", "en")
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    @property
    def input_types(self) -> type[Input]:
        return None

    @property
    def output_types(self) -> type[Output]:
        return None

    def invoke(self, input, **kwargs) -> list[Output]:
        return self._invoke(input, **kwargs)

    def _invoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError


# --- kag.interface.PromptABC (minimal; build/parse logic verbatim) --------- #
class PromptABC(ABC):
    template_en: str = ""
    template_zh: str = ""

    def __init__(self, language: str = "", **kwargs):
        if not language:
            language = "en"
        self.language = language
        if not hasattr(self, f"template_{self.language}"):
            raise ValueError(f"language {self.language} not supported yet.")
        self.template = getattr(self, f"template_{self.language}")
        self.template_variables_value = {}
        self.example_input = kwargs.get("example_input", None)
        self.example_output = kwargs.get("example_output", None)
        if isinstance(self.example_output, str):
            try:
                self.example_output = json.loads(self.example_output)
            except Exception:
                pass

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    def is_json_format(self):
        return True

    @property
    def template_variables(self) -> list[str]:
        raise NotImplementedError(
            f"{self.__class__.__name__} need to implement `template_variables` method."
        )

    def process_template_string_to_avoid_dollar_problem(self, template_string):
        new_template_str = template_string.replace("$", "$$")
        for var in self.template_variables:
            new_template_str = new_template_str.replace(f"$${var}", f"${var}")
        return new_template_str

    def _build_dict_prompt(self, variables) -> str:
        tmpl = copy.deepcopy(self.template)
        tmpl.update(variables)
        if self.example_input and self.example_output:
            tmpl["example"] = {
                "input": self.example_input,
                "output": (
                    json.loads(self.example_output)
                    if isinstance(self.example_output, str)
                    else self.example_output
                ),
            }
        return json.dumps(tmpl, ensure_ascii=False)

    def _build_str_prompt(self, variables) -> str:
        template_string = self.process_template_string_to_avoid_dollar_problem(self.template)
        template = Template(template_string)
        prompt = template.substitute(**variables)
        if self.example_input and self.example_output:
            prompt = json.loads(prompt)
            prompt["example"] = {
                "input": self.example_input,
                "output": self.example_output,
            }
            prompt = json.dumps(prompt, ensure_ascii=False)
        return prompt

    def build_prompt(self, variables) -> str:
        self.template_variables_value = variables
        if isinstance(self.template, str):
            return self._build_str_prompt(variables)
        elif isinstance(self.template, dict):
            return self._build_dict_prompt(variables)
        raise ValueError(
            f"Unsupported template format, expect [str|dict], but got {type(self.template)}"
        )

    def parse_response(self, response: str, **kwargs):
        raise NotImplementedError(
            f"{self.__class__.__name__} need to implement `parse_response` method."
        )


# --- kag.interface.LLMClient (minimal; bind your own model) ---------------- #
class LLMClient:
    def __init__(self, call=None, **kwargs):
        self._call = call
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    def call(self, prompt, **kwargs) -> str:
        if self._call is not None:
            return self._call(prompt, **kwargs)
        raise NotImplementedError(
            "Bind your model: subclass LLMClient and implement call(), "
            "or construct it with LLMClient(call=<your_model_callable>)."
        )

    __call__ = call

    def invoke(self, variables, prompt_op, **kwargs):
        prompt = prompt_op.build_prompt(variables)
        if not prompt:
            return []
        response = self.call(prompt, **kwargs)
        return prompt_op.parse_response(response, **kwargs)

    async def acall(self, prompt, **kwargs) -> str:
        # default async: run the sync model call
        return self.call(prompt, **kwargs)

    async def ainvoke(self, variables, prompt_op, **kwargs):
        prompt = prompt_op.build_prompt(variables)
        if not prompt:
            return []
        response = await self.acall(prompt, **kwargs)
        return prompt_op.parse_response(response, **kwargs)


# --- kag.interface.ExtractorABC (minimal) ---------------------------------- #
class ExtractorABC:
    def __init__(self, **kwargs):
        self.language = kwargs.pop("language", "en")
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    @property
    def input_types(self):
        return None

    @property
    def output_types(self):
        return None

    def invoke(self, input, **kwargs) -> list[Output]:
        return self._invoke(input, **kwargs)

    async def ainvoke(self, input, **kwargs) -> list[Output]:
        return await self._ainvoke(input, **kwargs)

    def _invoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError

    async def _ainvoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError


# --- kag.interface.ExternalGraphLoaderABC (stub) --------------------------- #
class ExternalGraphLoaderABC:
    """Optional external NER / linking source. Default-unused (callers check None)."""

    def ner(self, content):
        return []

    def get_allowed_labels(self):
        return []


# --- kag.interface.PostProcessorABC (minimal) ------------------------------ #
class PostProcessorABC:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    def invoke(self, input, **kwargs) -> list[Output]:
        return self._invoke(input, **kwargs)

    async def ainvoke(self, input, **kwargs) -> list[Output]:
        return self._invoke(input, **kwargs)

    def _invoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError


# --- vector search seam (replaces knext.search.client.SearchClient) --------- #
class SearchClientABC:
    """Bindable similarity-search seam for entity linking.

    Default is a NO-OP (returns no matches) so the postprocessor runs filter-only
    with zero infrastructure. Bind your store (e.g. Neo4j vector index) by
    subclassing and implementing search_vector(...) to return a list of
    {"score": float, "node": {"id": ..., "__labels__": [...]}}.
    """

    def search_vector(
        self, label, property_key, query_vector, topk=10, ef_search=None, params=None
    ):
        return []


# --- kag.interface.VectorizerABC (minimal) --------------------------------- #
class VectorizerABC:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    def invoke(self, input, **kwargs) -> list[Output]:
        return self._invoke(input, **kwargs)

    async def ainvoke(self, input, **kwargs) -> list[Output]:
        return await self._ainvoke(input, **kwargs)

    def _invoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError

    async def _ainvoke(self, input, **kwargs) -> list[Output]:
        raise NotImplementedError


# --- kag.interface.VectorizeModelABC (minimal; bind your embedding model) --- #
class VectorizeModelABC:
    """Embedding model seam. Bind your model:
        VectorizeModelABC(vectorize=lambda texts: [embed(t) for t in texts])
    or subclass and implement `vectorize(texts) -> List[vector]`.
    Maps a list[str] -> list of vectors. Never touches the OpenSPG server.
    """

    def __init__(self, vectorize=None, **kwargs):
        self._vectorize = vectorize
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    def vectorize(self, texts):
        if self._vectorize is not None:
            return self._vectorize(texts)
        raise NotImplementedError(
            "Bind your embedding model: VectorizeModelABC(vectorize=<fn>) "
            "or subclass and implement vectorize()."
        )

    async def avectorize(self, texts):
        return self.vectorize(texts)


class SparseVectorizeModelABC(VectorizeModelABC):
    """Optional sparse-embedding variant (default-unused)."""
