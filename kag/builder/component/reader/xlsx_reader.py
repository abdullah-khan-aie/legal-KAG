import logging
import os

import pandas as pd

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.common import Input, Output, generate_hash_id
from kag.interface import ReaderABC

logger = logging.getLogger(__name__)


@ReaderABC.register("xlsx")
@ReaderABC.register("xlsx_reader")
class XlsxReader(ReaderABC):
    """Read an ``.xlsx`` workbook into one Chunk per non-empty sheet.

    Each sheet is rendered to a GitHub-flavoured Markdown table (header row +
    data rows), prefixed with the workbook and sheet name for context. This is
    the standard spreadsheet-for-RAG approach (the same xlsx->Markdown conversion
    MarkItDown / the LangChain Excel loaders do): the output is exactly the table
    shape the MarkDownReader and table extractor already handle, so the
    downstream split -> extract -> embed path is unchanged.

    Cells are read as text (``dtype=str``) so exact values -- registration
    numbers, monetary amounts -- are preserved verbatim rather than being
    coerced to floats (e.g. ``12784563`` not ``12784563.0``).
    """

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Read the ``.xlsx`` at ``data`` and return one Chunk per non-empty sheet.

        Args:
            data: Path to an ``.xlsx`` file.

        Raises:
            ValueError: If the input is empty.
            FileNotFoundError: If the path is not an existing file.
            RuntimeError: If the workbook cannot be parsed.
        """
        if not data:
            raise ValueError("Input cannot be empty")
        if not isinstance(data, str) or not os.path.isfile(data):
            raise FileNotFoundError(f"xlsx file not found: {data}")

        basename, _ = os.path.splitext(os.path.basename(data))
        try:
            # sheet_name=None -> {sheet_name: DataFrame} for every sheet.
            sheets = pd.read_excel(data, sheet_name=None, dtype=str)
        except Exception as e:
            raise RuntimeError(f"Failed to read xlsx '{data}': {e}") from e

        chunks: list[Chunk] = []
        for sheet_name, df in sheets.items():
            # Drop fully-empty rows/columns so blank padding doesn't bloat the table.
            df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
            if df.empty:
                continue
            table_md = df.fillna("").to_markdown(index=False)
            content = f"# {basename} — {sheet_name}\n\n{table_md}"
            chunks.append(
                Chunk(
                    id=generate_hash_id(f"{data}::{sheet_name}"),
                    name=f"{basename} / {sheet_name}",
                    content=content,
                    type=ChunkTypeEnum.Table,
                )
            )

        if not chunks:
            logger.info(f"xlsx has no non-empty sheets, skipping: {data}")
        return chunks
