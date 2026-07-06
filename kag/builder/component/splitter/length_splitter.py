from kag.builder.component.splitter.base_table_splitter import BaseTableSplitter
from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.common import generate_hash_id


class LengthSplitter(BaseTableSplitter):
    def __init__(
        self,
        split_length: int = 500,
        window_length: int = 100,
        strict_length: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.split_length = split_length
        self.window_length = window_length
        self.strict_length = strict_length

    @property
    def input_types(self):
        return Chunk

    @property
    def output_types(self):
        return Chunk

    def chunk_breakdown(self, chunk):
        chunks = self.logic_break(chunk)
        if chunks:
            res_chunks = []
            for c in chunks:
                res_chunks.extend(self.chunk_breakdown(c))
        else:
            res_chunks = self.slide_window_chunk(chunk, self.split_length, self.window_length)
        return res_chunks

    @staticmethod
    def logic_break(chunk):
        return None

    @staticmethod
    def split_sentence(content):
        sentence_delimiters = ".。？?！!"
        output = []
        start = 0
        for idx, char in enumerate(content):
            if char in sentence_delimiters:
                end = idx
                tmp = content[start : end + 1].strip()
                if len(tmp) > 0:
                    output.append(tmp.strip())
                start = idx + 1
        res = content[start:].strip()
        if len(res) > 0:
            output.append(res)
        return output

    def slide_window_chunk(
        self,
        org_chunk: Chunk,
        chunk_size: int = 2000,
        window_length: int = 300,
        sep: str = "\n",
    ) -> list[Chunk]:
        if org_chunk.type == ChunkTypeEnum.Table:
            table_chunks = self.split_table(org_chunk=org_chunk, chunk_size=chunk_size, sep=sep)
            if table_chunks is not None:
                return table_chunks
        if getattr(self, "strict_length", False):
            return self.strict_length_chunk(org_chunk)

        content = self.split_sentence(org_chunk.content)
        splitted = []
        cur = []
        cur_len = 0
        for sentence in content:
            if cur_len + len(sentence) > chunk_size:
                if cur:
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
            if idx > 0:
                new_id = generate_hash_id(f"{org_chunk.id}#{idx}")
                new_name = f"{org_chunk.name}_split_{idx}"
            else:
                new_id = org_chunk.id
                new_name = org_chunk.name
            chunk = Chunk(
                id=new_id,
                name=new_name,
                content=sep.join(sentences),
                type=org_chunk.type,
                chunk_size=chunk_size,
                window_length=window_length,
                **org_chunk.kwargs,
            )
            output.append(chunk)
        return output

    def strict_length_chunk(self, org_chunk: Chunk) -> list[Chunk]:
        content = org_chunk.content
        total_length = len(content)
        output = []
        position = 0
        chunk_index = 0
        while position < total_length:
            chunk_content = content[position : position + self.split_length]
            chunk = Chunk(
                id=generate_hash_id(f"{org_chunk.id}#{chunk_index}"),
                name=f"{org_chunk.name}_split_{chunk_index}",
                content=chunk_content,
                type=org_chunk.type,
                chunk_size=self.split_length,
                window_length=self.window_length,
                **org_chunk.kwargs,
            )
            output.append(chunk)
            position = position + self.split_length - self.window_length
            chunk_index += 1
            if position < 0:
                position = 0
        return output

    def invoke(self, data: Chunk, **kwargs) -> list[Chunk]:
        # Public entry point matching the splitter contract the pipeline calls.
        # SemanticSplitter exposed `invoke`; the stock LengthSplitter only has
        # `_invoke`, so wrap it to keep the interface consistent.
        return self._invoke(data, **kwargs)

    def _invoke(self, data: Chunk, **kwargs) -> list[Chunk]:
        cutted = []
        if isinstance(data, list):
            for item in data:
                cutted.extend(self.slide_window_chunk(item, self.split_length, self.window_length))
        else:
            cutted.extend(self.slide_window_chunk(data, self.split_length, self.window_length))
        return cutted
