import logging
import os
import urllib.parse  # Import for URL decoding

from kag.builder.model.chunk import Chunk
from kag.common import Input, Output, generate_hash_id
from kag.interface import ReaderABC

logger = logging.getLogger(__name__)


@ReaderABC.register("txt")
@ReaderABC.register("txt_reader")
class TXTReader(ReaderABC):
    """Read a text file (or raw text) into a single Chunk."""

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Read the input as a file path or raw text and return it as one Chunk.

        Args:
            data: A path to a text file or direct text content.
            **kwargs: ``perform_url_decode`` (bool): percent-decode the input when
                treated as a path; defaults to False.

        Raises:
            ValueError: If the input is empty.
            IOError: If the file cannot be read.
        """
        if not data:
            raise ValueError("Input cannot be empty")

        perform_url_decode = kwargs.get("perform_url_decode", False)

        path_str = data
        if not isinstance(path_str, str):
            try:
                path_str = str(data)
            except Exception as e:
                raise TypeError(f"Input cannot be converted to string: {input}. Error: {e}")

        original_input_repr = repr(path_str)

        if perform_url_decode:
            try:
                # Attempt to decode percent-encoding (URL encoding)
                decoded_path = urllib.parse.unquote(path_str)
                if decoded_path != path_str:
                    print(
                        f"DEBUG: Successfully URL-decoded input: {original_input_repr} -> '{decoded_path}'"
                    )
                path_str = decoded_path
            except Exception as e:
                print(
                    f"WARN: Unexpected error during URL decoding attempt for {original_input_repr}: {e}"
                )
                path_str = original_input_repr
        else:
            print(f"DEBUG: URL decoding skipped for input: {original_input_repr}")

        print(f"DEBUG: Processing file path: '{path_str}'")

        is_file = os.path.isfile(path_str)

        if is_file:
            try:
                with open(path_str, encoding="utf-8") as f:
                    file_content = f.read()
                basename, _ = os.path.splitext(os.path.basename(path_str))
                logger.info(f"Read content from file: {path_str}")
            except OSError as e:
                raise OSError(
                    f"Failed to read file: '{path_str}' (Original input was: {original_input_repr})"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"An unexpected error occurred while reading file '{path_str}': {e}"
                )
        else:
            file_content = path_str
            basename = "direct_content"
            logger.info("Input is not a file path, treating as direct content.")

        chunk = Chunk(
            id=generate_hash_id(path_str),
            name=urllib.parse.unquote(basename),
            content=file_content,
        )
        return [chunk]


if __name__ == "__main__":
    reader = TXTReader()
    reader.invoke("ckpt/file_scanner/%E5%91%A8%E6%9D%B0%E4%BC%A6.txt")
