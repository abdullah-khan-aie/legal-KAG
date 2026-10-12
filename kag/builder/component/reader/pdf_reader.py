import logging
import os
import re

import pdfminer  # noqa
import pdfminer.layout  # noqa
import PyPDF2
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTTextContainer
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser

from kag.builder.component.splitter.length_splitter import LengthSplitter
from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import Edge, Node, SubGraph
from kag.builder.prompt.outline_prompt import OutlinePrompt
from kag.common import Input, Output, generate_hash_id
from kag.interface import LLMClient, ReaderABC

logger = logging.getLogger(__name__)


@ReaderABC.register("pdf")
@ReaderABC.register("pdf_reader")
class PDFReader(ReaderABC):
    """Read a PDF file into Chunk objects, optionally guided by its outline."""

    def __init__(
        self,
        cut_depth: int = 3,
        outline_flag: bool = True,
        is_ocr: bool = False,
        llm: LLMClient = None,
        length_splitter: LengthSplitter = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cut_depth = cut_depth
        self.outline_flag = outline_flag
        self.is_ocr = is_ocr
        self.llm = llm
        self.length_splitter = length_splitter
        self.prompt = OutlinePrompt()

    @property
    def input_types(self):
        return str

    @property
    def output_types(self):
        return Chunk

    def _get_full_outlines(self):
        outlines = self.pdf_reader.outline
        level_outlines = []

        def _extract_outline_page_numbers(outlines, level=0):
            for outline in outlines:
                if isinstance(outline, list):
                    _extract_outline_page_numbers(outline, level + 1)
                else:
                    title = outline.title
                    page_number = self.pdf_reader.get_destination_page_number(outline)
                    level_outlines.append((title, level, page_number, 0))

        _extract_outline_page_numbers(outlines)
        for idx, outline in enumerate(level_outlines):
            level_outlines[idx] = (
                outline[0],
                outline[1],
                outline[2],
                level_outlines[idx + 1][2] if idx + 1 < len(level_outlines) else -1,
            )
        return level_outlines

    @staticmethod
    def extract_content_from_outline(
        page_contents, page_contents_spaced, level_outlines
    ) -> list[Chunk]:
        # Titles are matched against the stripped text because PDF spacing is
        # unreliable, but chunks are sliced from the spaced text, or words run
        # together as "atenantbreakatyear7".
        total_content = "".join(page_contents)
        spaced_total = "".join(page_contents_spaced)

        # The stripped text is a subsequence of the spaced one, so a two-pointer
        # walk maps between them. The sentinel makes end-exclusive bounds safe.
        index_map: list[int] = []
        j = 0
        for ch in total_content:
            while j < len(spaced_total) and spaced_total[j] != ch:
                j += 1
            index_map.append(j)
            j += 1
        index_map.append(len(spaced_total))

        def readable_slice(start: int, end: int) -> str:
            s = index_map[start] if 0 <= start < len(index_map) else len(spaced_total)
            if end is None or end < 0:
                return spaced_total[s:]
            e = index_map[end] if end < len(index_map) else len(spaced_total)
            return spaced_total[s:e]

        def get_content_start(outline, page_contents):
            page_start = outline[2]
            page_end = outline[3]

            previous_pages_length = sum(len(content) for content in page_contents[:page_start])

            find_content = "".join(
                page_contents[page_start : page_end + 1 if page_end != -1 else None]
            )

            def normalize_text(text):
                # some titles use a dash where the Chinese numeral one is meant
                text = text.replace("—", "一")
                text = re.sub(r"［", "[", text)
                text = re.sub(r"］", "]", text)
                text = re.sub(r"（", "(", text)
                text = re.sub(r"）", ")", text)
                return text

            outline = (normalize_text(outline[0]), outline[1], outline[2], outline[3])

            def fuzzy_search(pattern, text, threshold=0.90):
                from difflib import SequenceMatcher

                pattern_len = len(pattern)
                for i in range(len(text) - pattern_len + 1):
                    substring = text[i : i + pattern_len]
                    similarity = SequenceMatcher(None, pattern, substring).ratio()
                    if similarity >= threshold:
                        return i
                return -1

            title_with_spaces = outline[0].strip()
            fuzzy_match_pos = fuzzy_search(title_with_spaces, find_content)
            if fuzzy_match_pos != -1:
                return previous_pages_length + fuzzy_match_pos

            title_no_spaces = title_with_spaces.replace(" ", "")
            find_content_no_spaces = find_content.replace(" ", "")
            fuzzy_match_pos = fuzzy_search(title_no_spaces, find_content_no_spaces)

            if fuzzy_match_pos != -1:
                original_pos = 0
                no_spaces_pos = 0
                while no_spaces_pos < fuzzy_match_pos:
                    if find_content[original_pos] != " ":
                        no_spaces_pos += 1
                    original_pos += 1
                return previous_pages_length + original_pos

            extended_content = "".join(
                page_contents[max(0, page_start - 1) : page_end if page_end != -1 else None]
            )

            fuzzy_match_pos = fuzzy_search(title_with_spaces, extended_content)
            if fuzzy_match_pos != -1:
                extended_previous_length = sum(
                    len(content) for content in page_contents[: max(0, page_start - 1)]
                )
                return extended_previous_length + fuzzy_match_pos

            extended_content_no_spaces = extended_content.replace(" ", "")
            fuzzy_match_pos = fuzzy_search(title_no_spaces, extended_content_no_spaces)
            if fuzzy_match_pos != -1:
                original_pos = 0
                no_spaces_pos = 0
                while no_spaces_pos < fuzzy_match_pos:
                    if extended_content[original_pos] != " ":
                        no_spaces_pos += 1
                    original_pos += 1

                extended_previous_length = sum(
                    len(content) for content in page_contents[: max(0, page_start - 1)]
                )
                return extended_previous_length + original_pos

            return -1

        final_content = []
        for idx, outline in enumerate(level_outlines):
            start = get_content_start(outline, page_contents)
            next_start = (
                get_content_start(level_outlines[idx + 1], page_contents)
                if idx + 1 < len(level_outlines)
                else -1
            )
            if start >= 0 and next_start >= 0:
                content = readable_slice(start, next_start)
                final_content.append((outline[0], outline[1], start, next_start, content))
            elif start >= 0 and next_start < 0 and idx + 1 == len(level_outlines):
                content = readable_slice(start, -1)
                final_content.append((outline[0], outline[1], start, -1, content))

        # The loop above starts at the first bookmark, so anything before it
        # (recitals, attendance, cover blocks) would be dropped without this.
        if final_content:
            first_start = final_content[0][2]
            if isinstance(first_start, int) and first_start > 0:
                preamble = readable_slice(0, first_start)
                if preamble.strip():
                    final_content.insert(0, ("Preamble", 0, 0, first_start, preamble))
        return final_content

    def convert_finel_content_to_chunks(self, final_content) -> tuple[list[Chunk], SubGraph]:
        def create_chunk(title, content, basename):
            chunk = Chunk(
                id=generate_hash_id(f"{basename}#{title}"),
                name=f"{basename}#{title}",
                content=content,
                sub_chunks=[],
            )
            if self.length_splitter:
                split_chunks = self.length_splitter.slide_window_chunk(
                    chunk,
                    self.length_splitter.split_length,
                    self.length_splitter.window_length,
                )
                for split_chunk in split_chunks:
                    split_chunk.parent_id = chunk.id
                return split_chunks
            return [chunk]

        level_map = {}
        chunks = []
        nodes = []
        edges = []
        node_map = {}  # Track created nodes by ID
        chunk_nodes = {}  # Track chunk nodes by their IDs

        def add_bidirectional_edge(
            from_node: Node, to_node: Node, label: str, properties: dict = None
        ):
            """Helper function to add bidirectional edges"""
            if properties is None:
                properties = {}

            edges.append(
                Edge(
                    _id="",
                    from_node=from_node,
                    to_node=to_node,
                    label=label,
                    properties=properties.copy(),
                )
            )

            reverse_label = {
                "hasChild": "hasParent",
                "hasContent": "belongsToTitle",
            }.get(label, f"reverse_{label}")

            edges.append(
                Edge(
                    _id="",
                    from_node=to_node,
                    to_node=from_node,
                    label=reverse_label,
                    properties=properties.copy(),
                )
            )

        basename = os.path.splitext(os.path.basename(self.fd.name))[0]
        root_node_id = f"node_root_{basename}"
        root_node = Node(_id=root_node_id, name=basename, label="Title", properties={"level": "0"})
        nodes.append(root_node)
        node_map[root_node_id] = root_node

        for title, level, start, end, content in final_content:
            created_chunks = create_chunk(title, content, basename)
            chunks.extend(created_chunks)

            title_node_id = f"node_{hash(title)}"
            if title_node_id not in node_map:
                title_node = Node(
                    _id=title_node_id,
                    name=title,
                    label="Title",
                    properties={"level": str(level)},
                )
                nodes.append(title_node)
                node_map[title_node_id] = title_node
            else:
                title_node = node_map[title_node_id]

            for chunk in created_chunks:
                chunk_node = Node(
                    _id=chunk.id,
                    name=chunk.name,
                    label="Chunk",
                    properties={
                        "content": chunk.content,
                    },
                )
                nodes.append(chunk_node)
                chunk_nodes[chunk.id] = chunk_node

                add_bidirectional_edge(title_node, chunk_node, "hasContent")

            if level == 0:
                level_map[0] = chunks[-1]  # Use last chunk as level marker
                add_bidirectional_edge(root_node, title_node, "hasChild", {"level": "1"})
            else:
                parent_found = False
                parent_level = level - 1
                while parent_level >= 0:
                    if parent_level in level_map:
                        for chunk in created_chunks:
                            level_map[parent_level].sub_chunks.append(chunk)
                        parent_chunk = level_map[parent_level]
                        parent_title_node = node_map[
                            f"node_{hash(parent_chunk.name.split('#')[1])}"
                        ]
                        add_bidirectional_edge(
                            parent_title_node,
                            title_node,
                            "hasChild",
                            {"level": str(level)},
                        )
                        parent_found = True
                        break
                    parent_level -= 1

                if not parent_found:
                    add_bidirectional_edge(root_node, title_node, "hasChild", {"level": str(level)})

                level_map[level] = chunks[-1]  # Use last chunk as level marker

        subgraph = SubGraph(nodes=nodes, edges=edges)
        return chunks, subgraph

    def outline_chunk(self, chunk: Chunk | list[Chunk], basename) -> list[Chunk]:
        if isinstance(chunk, Chunk):
            chunk = [chunk]
        outlines = []
        for c in chunk:
            outline = self.llm.invoke({"input": c.content}, self.prompt)
            outlines.extend(outline)
        content = "\n".join([c.content for c in chunk])
        chunks = self.sep_by_outline(content, outlines, basename)
        return chunks

    @staticmethod
    def sep_by_outline(content, outlines, basename):
        position_check = []
        for outline in outlines:
            start = content.find(outline)
            position_check.append((outline, start))
        chunks = []
        for idx, pc in enumerate(position_check):
            chunk = Chunk(
                id=generate_hash_id(f"{basename}#{pc[0]}"),
                name=f"{basename}#{pc[0]}",
                content=content[
                    pc[1] : (
                        position_check[idx + 1][1]
                        if idx + 1 < len(position_check)
                        else len(position_check)
                    )
                ],
            )
            chunks.append(chunk)
        return chunks

    @staticmethod
    def _process_single_page(
        page: str,
        watermark: str,
        remove_header: bool = False,
        remove_footnote: bool = False,
        remove_lists: list[str] = None,
    ) -> list:
        """Clean a single page's text, stripping watermarks and optional headers/footers.

        Args:
            page: The text content of a single page.
            watermark: Watermark text to remove.
            remove_header: Whether to drop the first line.
            remove_footnote: Whether to drop the last line.
            remove_lists: Additional substrings to strip from each line.

        Returns:
            The cleaned text lines.
        """
        lines = page.split("\n")
        if remove_header and len(lines) > 0:
            lines = lines[1:]
        if remove_footnote and len(lines) > 0:
            lines = lines[:-1]

        cleaned = [line.strip().replace(watermark, "") for line in lines]

        if remove_lists is None:
            return cleaned
        for s in remove_lists:
            cleaned = [line.strip().replace(s, "") for line in cleaned]

        return cleaned

    @staticmethod
    def _extract_text_from_page(page_layout: LTPage) -> str:
        """Concatenate the text of all text containers in a page layout.

        Args:
            page_layout: The page layout to extract text from.
        """
        text = ""
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                text += element.get_text()
        return text

    def _invoke(self, data: Input, **kwargs) -> tuple[list[Output], SubGraph]:
        """Read the PDF and return its content as chunks.

        When an outline is available the chunks follow the document structure;
        otherwise the PDF is chunked page by page.

        Args:
            data: The path to the PDF file.

        Raises:
            ValueError: If the input is not a .pdf path.
            FileNotFoundError: If the file does not exist.
        """
        if not data.endswith(".pdf"):
            raise ValueError(f"Please provide a pdf file, got {input}")

        if not os.path.isfile(data):
            raise FileNotFoundError(f"The file {input} does not exist.")

        self.fd = None
        try:
            self.fd = open(data, "rb")
            self.pdf_reader = PyPDF2.PdfReader(self.fd)
            self.level_outlines = self._get_full_outlines()
            self.parser = PDFParser(self.fd)
            self.document = PDFDocument(self.parser)
            chunks = []
            basename, _ = os.path.splitext(os.path.basename(data))

            try:
                outlines = self.document.get_outlines()  # noqa
            except Exception as e:
                logger.warning(f"loading PDF file: {e}")
                self.outline_flag = False

            if not self.outline_flag:
                with open(data, "rb") as file:
                    for idx, page_layout in enumerate(extract_pages(file)):
                        content = ""
                        for element in page_layout:
                            if hasattr(element, "get_text"):
                                content = content + element.get_text()
                        chunk = Chunk(
                            id=generate_hash_id(f"{basename}#{idx}"),
                            name=f"{basename}#{idx}",
                            content=content,
                        )
                        chunks.append(chunk)

            else:
                split_words = []  # noqa

                raw_pages = []

                with open(data, "rb") as file:
                    for idx, page_layout in enumerate(extract_pages(file)):
                        content = ""
                        for element in page_layout:
                            if hasattr(element, "get_text"):
                                content = content + element.get_text()
                        raw_pages.append(content)

                # Used only to locate section boundaries. Kept byte-identical to
                # upstream so matching accuracy is unchanged.
                page_contents = [content.replace("\n", "") for content in raw_pages]
                page_contents = [re.sub(r"\s+", "", content) for content in page_contents]
                page_contents = [
                    re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", "", content)
                    for content in page_contents
                ]
                page_contents = ["".join(content.split()) for content in page_contents]

                # What chunks are actually sliced from. Newlines become spaces so
                # words are not glued together across line breaks.
                page_contents_spaced = [content.replace("\n", " ") for content in raw_pages]

                final_content = self.extract_content_from_outline(
                    page_contents, page_contents_spaced, self.level_outlines
                )
                chunks, subgraph = self.convert_finel_content_to_chunks(final_content)

            return chunks

        except Exception as e:
            raise RuntimeError(f"Error loading PDF file: {e}")
        finally:
            if self.fd:
                self.fd.close()


if __name__ == "__main__":
    pdf_reader = ReaderABC.from_config(
        {
            "type": "pdf_reader",
            "length_splitter": {
                "type": "length_splitter",
                "split_length": 50,
                "window_length": 10,
                "language": "zh",
            },
        }
    )
    pdf_path = os.path.join(
        os.path.dirname(__file__), "../../../../tests/unit/builder/data/aiwen.pdf"
    )
    chunk = pdf_reader.invoke(pdf_path)
    a = 1
