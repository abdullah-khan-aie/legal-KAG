# -*- coding: utf-8 -*-
# Dependency-free vendoring of kag/builder/component/splitter/pattern_splitter.py
# (openspg-kag 0.8.0, Apache-2.0). Splitting logic VERBATIM except:
#   - dropped SplitterABC base + @register decorators -> plain class
#   - Chunk/generate_hash_id/Input/Output from local modules
# No LLM, no server, no network — pure regex + string ops.

# flake8: noqa
import re
from typing import Type, List, Union

from kag.builder.model.chunk import Chunk
from kag.common import generate_hash_id, Input, Output


class PatternSplitter:
    """Splits text content based on a regex pattern and chunking strategy."""

    def __init__(self, pattern_dict: dict = None, chunk_cut_num: int = None):
        if pattern_dict is None:
            pattern_dict = {
                "pattern": r"(\d+)\.([^0-9]+?)？([^0-9第版].*?)(?=\d+\.|$)",
                "group": {"header": 2, "name": 2, "content": 0},
            }
        self.pattern = pattern_dict["pattern"]
        self.group = pattern_dict["group"]
        self.chunk_cut_num = chunk_cut_num

    @property
    def input_types(self) -> Type[Input]:
        return Chunk

    @property
    def output_types(self) -> Type[Output]:
        return List[Chunk]

    def split_sentence(self, content):
        sentence_delimiters = "。？?！!；;\n"
        output = []
        start = 0
        for idx, char in enumerate(content):
            if char in sentence_delimiters:
                end = idx
                tmp = content[start : end + 1].strip()
                if len(tmp) > 0:
                    output.append(tmp)
                start = idx + 1
        res = content[start:]
        if len(res) > 0:
            output.append(res)
        return output

    def slide_window_chunk(
        self,
        content: Union[str, List[str]],
        chunk_size: int = 2000,
        window_length: int = 300,
        sep: str = "\n",
        prefix: str = "SlideWindow",
    ) -> List[Chunk]:
        if isinstance(content, str):
            content = self.split_sentence(content)
        splitted = []
        cur = []
        cur_len = 0
        for sentence in content:
            if cur_len + len(sentence) > chunk_size:
                splitted.append(cur)
                tmp = []
                cur_len = 0
                for item in cur[::-1]:
                    if cur_len >= window_length:
                        break
                    tmp.append(item)
                    cur_len += len(item)
                cur = tmp[::-1]

            cur.append(sentence)
            cur_len += len(sentence)
        if len(cur) > 0:
            splitted.append(cur)

        output = []
        for idx, sentences in enumerate(splitted):
            chunk_name = f"{prefix}#{idx}"
            chunk = Chunk(
                id=generate_hash_id(chunk_name),
                name=chunk_name,
                content=sep.join(sentences),
            )
            output.append(chunk)
        return output

    def chunk_split(self, chunk: Chunk) -> List[Chunk]:
        text = chunk.content

        pattern = re.compile(self.pattern, re.DOTALL)

        matches = pattern.finditer(text)

        chunks = []
        for match in matches:
            chunk = Chunk(
                chunk_header=match.group(self.group["header"]),
                name=match.group(self.group["name"]),
                id=generate_hash_id(match.group(self.group["content"])),
                content=match.group(self.group["content"]),
            )
            chunk = [chunk]

            if self.chunk_cut_num:
                chunk = self.slide_window_chunk(
                    content=chunk[0].content,
                    chunk_size=self.chunk_cut_num,
                    window_length=self.chunk_cut_num / 4,
                    sep="\n",
                    prefix=chunk[0].name,
                )

            chunks.extend(chunk)

        return chunks

    def _invoke(self, data: Chunk, **kwargs) -> List[Output]:
        chunks = self.chunk_split(data)
        return chunks
