import os

from kag.builder.component.reader.dict_reader import DictReader
from kag.builder.component.reader.docx_reader import DocxReader
from kag.builder.component.reader.markdown_reader import MarkDownReader
from kag.builder.component.reader.pdf_reader import PDFReader
from kag.builder.component.reader.txt_reader import TXTReader
from kag.common import Input, Output
from kag.interface import ReaderABC


@ReaderABC.register("mix", as_default=True)
@ReaderABC.register("mix_reader")
class MixReader(ReaderABC):
    """Dispatch each input to a type-specific reader based on its file suffix or shape."""

    def __init__(
        self,
        txt_reader: TXTReader = None,
        pdf_reader: PDFReader = None,
        docx_reader: DocxReader = None,
        md_reader: MarkDownReader = None,
        dict_reader: DictReader = None,
        **kwargs,
    ):
        """Initialize the reader, mapping each input type to its delegate reader.

        Args:
            txt_reader: Reader for .txt files.
            pdf_reader: Reader for .pdf files.
            docx_reader: Reader for .docx files.
            md_reader: Reader for .md files.
            dict_reader: Reader for dictionary inputs.
        """
        super().__init__(**kwargs)
        self.reader_map = {
            "txt": txt_reader,
            "pdf": pdf_reader,
            "docx": docx_reader,
            "md": md_reader,
            "dict": dict_reader,
        }

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Select the reader matching the input and delegate parsing to it.

        Args:
            data: A file path or a dictionary to parse.

        Raises:
            ValueError: If the input is empty.
            FileNotFoundError: If the input file does not exist.
            NotImplementedError: If the file suffix is not supported.
            KeyError: If no reader is configured for the input type.
        """
        if not data:
            raise ValueError("Input cannot be empty")
        if isinstance(data, dict):
            reader_type = "dict"

        else:
            if not os.path.exists(data):
                raise FileNotFoundError(f"File {input} not found.")

            file_suffix = data.split(".")[-1]
            if file_suffix not in self.reader_map:
                raise NotImplementedError(f"File suffix {file_suffix} not supported yet.")
            reader_type = file_suffix

        reader = self.reader_map[reader_type]
        if reader is None:
            raise KeyError(f"{reader_type} reader not correctly configured.")
        return reader._invoke(data)
