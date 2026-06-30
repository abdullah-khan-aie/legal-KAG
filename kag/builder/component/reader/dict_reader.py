from kag.builder.model.chunk import Chunk
from kag.common import Input, Output
from kag.interface import ReaderABC


@ReaderABC.register("dict")
@ReaderABC.register("dict_reader")
class DictReader(ReaderABC):
    """Read a dictionary into a Chunk.

    Attributes:
        id_col: Dictionary key mapped to the chunk's id.
        name_col: Dictionary key mapped to the chunk's name.
        content_col: Dictionary key mapped to the chunk's content.
    """

    def __init__(self, id_col: str = "id", name_col: str = "name", content_col: str = "content"):
        """Initialize the reader with the dictionary keys to map onto the chunk.

        Args:
            id_col: Dictionary key mapped to the chunk's id.
            name_col: Dictionary key mapped to the chunk's name.
            content_col: Dictionary key mapped to the chunk's content.
        """
        super().__init__()
        self.id_col = id_col
        self.name_col = name_col
        self.content_col = content_col

    @property
    def input_types(self) -> Input:
        return dict

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """Convert the input dictionary into a single-element list of one Chunk.

        Args:
            input: The dictionary to convert.
        """
        chunk_id = input.get(self.id_col)
        chunk_name = input.get(self.name_col)
        chunk_content = input.get(self.content_col)
        if self.id_col in input:
            input.pop(self.id_col)
        if self.name_col in input:
            input.pop(self.name_col)
        if self.content_col in input:
            input.pop(self.content_col)

        return [Chunk(id=chunk_id, name=chunk_name, content=chunk_content, **input)]
