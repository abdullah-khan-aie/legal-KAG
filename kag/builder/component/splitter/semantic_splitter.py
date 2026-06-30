import logging
import re

from kag.builder.model.chunk import Chunk
from kag.builder.prompt.semantic_seg_prompt import SemanticSegPrompt
from kag.common import Input, Output, generate_hash_id
from kag.interface import LLMClient

logger = logging.getLogger(__name__)


class SemanticSplitter:
    """Semantically splits text into chunks using an LLM."""

    def __init__(
        self,
        llm: LLMClient,
        kept_char_pattern: str = None,
        split_length: int = 1000,
        **kwargs,
    ):
        if kept_char_pattern is None:
            self.kept_char_pattern = re.compile(r"[^一-龥　-〿！-／：-＠［-｀｛-･\x00-\x7F]+")
        else:
            self.kept_char_pattern = re.compile(kept_char_pattern)
        self.split_length = split_length
        self.llm = llm
        self.semantic_seg_op = SemanticSegPrompt()

    @property
    def input_types(self) -> type[Input]:
        return Chunk

    @property
    def output_types(self) -> type[Output]:
        return Chunk

    @staticmethod
    def parse_llm_output(content: str, llm_output: list):
        seg_info = llm_output

        seg_info.sort()
        locs = [x[0] for x in seg_info]
        abstracts = [x[1] for x in seg_info]
        locs.append(len(content))
        splitted = []
        for idx in range(len(abstracts)):
            start = locs[idx]
            end = locs[idx + 1]
            splitted.append(
                {
                    "name": abstracts[idx],
                    "content": content[start:end],
                    "length": end - start,
                }
            )

        return splitted

    def semantic_chunk(
        self,
        org_chunk: Chunk,
        chunk_size: int = 1000,
    ) -> list[Chunk]:
        result = self.llm.invoke({"input": org_chunk.content}, self.semantic_seg_op)
        splitted = self.parse_llm_output(org_chunk.content, result)
        if len(splitted) == 0:
            return [org_chunk]
        logger.debug(f"splitted = {splitted}")
        chunks = []
        for idx, item in enumerate(splitted):
            split_name = item["name"]
            if len(item["content"]) < chunk_size:
                chunk = Chunk(
                    id=f"{org_chunk.id}#{chunk_size}#{idx}#SEM",
                    name=f"{org_chunk.name}#{split_name}",
                    content=item["content"],
                    abstract=item["name"],
                    **org_chunk.kwargs,
                )
                chunks.append(chunk)
            else:
                print("chunk over size")
                innerChunk = Chunk(
                    id=generate_hash_id(item["content"]),
                    name=f"{org_chunk.name}#{split_name}",
                    content=item["content"],
                )
                chunks.extend(self.semantic_chunk(innerChunk, chunk_size))
        return chunks

    def invoke(self, input: Input, **kwargs) -> list[Output]:
        """Public entry point; delegates to the splitting implementation."""
        return self._invoke(input, **kwargs)

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        chunks = self.semantic_chunk(input, self.split_length)
        return chunks
