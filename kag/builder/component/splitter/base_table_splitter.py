# Dependency-free vendoring of kag/builder/component/splitter/base_table_splitter.py
# (openspg-kag 0.8.0, Apache-2.0). Logic verbatim except:
#   - dropped SplitterABC base -> plain class
#   - Chunk from local module

from kag.builder.model.chunk import Chunk


class BaseTableSplitter:
    """Base class for splitting markdown-table data into smaller chunks."""

    def __init__(self, **kwargs):
        pass

    def split_table(self, org_chunk: Chunk, chunk_size: int = 2000, sep: str = "\n"):
        try:
            return self._split_table(org_chunk=org_chunk, chunk_size=chunk_size, sep=sep)
        except Exception:
            return None

    def _split_table(self, org_chunk: Chunk, chunk_size: int = 2000, sep: str = "\n"):
        output = []
        content = org_chunk.content
        table_start = content.find("|")
        table_end = content.rfind("|") + 1
        if table_start is None or table_end is None or table_start == table_end:
            return None
        prefix = content[0:table_start].strip("\n ")
        table_rows = content[table_start:table_end].split("\n")
        table_header = table_rows[0]
        table_header_segmentation = table_rows[1]
        suffix = content[table_end:].strip("\n ")

        splitted = []
        cur = [prefix, table_header, table_header_segmentation]
        cur_len = len(prefix)
        for idx, row in enumerate(table_rows[2:]):
            if cur_len > chunk_size:
                cur.append(suffix)
                splitted.append(cur)
                cur_len = 0
                cur = [prefix, table_header, table_header_segmentation]
            cur.append(row)
            cur_len += len(row)

        cur.append(content[table_end:])
        if len(cur) > 0:
            splitted.append(cur)

        output = []
        for idx, sentences in enumerate(splitted):
            chunk = Chunk(
                id=f"{org_chunk.id}#{chunk_size}#table#{idx}#LEN",
                name=f"{org_chunk.name}#{idx}",
                content=sep.join(sentences),
                type=org_chunk.type,
                **org_chunk.kwargs,
            )
            output.append(chunk)
        return output
