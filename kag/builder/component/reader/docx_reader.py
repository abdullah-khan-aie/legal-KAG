import os

from docx import Document
from docx.text.paragraph import Paragraph

from kag.builder.component.splitter.length_splitter import LengthSplitter
from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import Edge, Node, SubGraph
from kag.builder.prompt.outline_prompt import OutlinePrompt
from kag.common import Input, Output, generate_hash_id
from kag.interface import LLMClient, ReaderABC


class DocxNode:
    def __init__(self, title: str, level: int, content: str = "", node_type: str = "heading"):
        """Initialize a node in the document tree.

        Args:
            title: The title or text of the node.
            level: The hierarchical level.
            content: The content text.
            node_type: The node type, e.g. "heading", "list", or "paragraph".
        """
        self.title = title
        self.display_title = (
            title[:100] + "..." if len(title) > 100 else title
        )  # Truncated for display
        self.level = level
        self.content = content
        self.node_type = node_type
        self.children: list[DocxNode] = []
        self.properties: dict[
            str, str
        ] = {}  # Store additional properties like style, indent level, etc.

    def __str__(self):
        return f"{self.node_type}({self.level}): {self.display_title}"

    def add_child(self, child: "DocxNode") -> None:
        """Add a child node with proper level adjustment if needed."""
        if child.level <= self.level and self.node_type == "heading":
            # Adjust child level to maintain hierarchy
            level_diff = self.level + 1 - child.level
            child.level += level_diff
        self.children.append(child)

    def get_node_id(self) -> str:
        """Generate a stable node ID that's not dependent on the full title."""
        return generate_hash_id(f"{self.node_type}_{self.level}_{self.title[:100]}")


@ReaderABC.register("docx")
@ReaderABC.register("docx_reader")
class DocxReader(ReaderABC):
    """Read a Docx file into Chunk objects following its heading hierarchy."""

    def __init__(
        self,
        llm: LLMClient = None,
        cut_depth: int = 5,
        length_splitter: LengthSplitter = None,
        **kwargs,
    ):
        """Initialize the reader with optional LLM, cut depth, and length splitter.

        Args:
            llm: LLM client used for generating outlines.
            cut_depth: Heading level at which to cut the document into chunks.
            length_splitter: Splitter used to break up over-long chunks.
        """
        super().__init__(**kwargs)
        self.llm = llm
        self.prompt = OutlinePrompt()
        self.cut_depth = cut_depth
        self.length_splitter = length_splitter

    def outline_chunk(self, chunk: Chunk | list[Chunk], basename) -> list[Chunk]:
        """Generate outlines via the LLM and split the content by them.

        Args:
            chunk: A chunk or list of chunks to outline.
            basename: Base name used for generated chunk ids and names.
        """
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
        """Split content into chunks at the positions of the given outlines.

        Args:
            content: The content to split.
            outlines: Outlines marking where to split the content.
            basename: Base name used for generated chunk ids and names.
        """
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

    @classmethod
    def _get_heading_level(cls, paragraph: Paragraph) -> tuple[int, bool]:
        """Determine a paragraph's heading level and whether it is a true heading.

        Args:
            paragraph: The paragraph to inspect.

        Returns:
            A tuple of (heading level 1-6, or 0 if not a heading; whether it is a
            real style-based heading rather than merely formatted text).
        """
        # 1. Check for built-in heading styles - Most reliable method
        if paragraph.style and paragraph.style.name:
            style_name = paragraph.style.name.lower()
            # Check for standard heading styles (Heading 1, Heading 2, etc.)
            if style_name.startswith("heading"):
                try:
                    return int(style_name[7:]), True
                except ValueError:
                    pass
            # Check for title style
            elif style_name == "title":
                return 1, True
            # Check for TOC styles (Table of Contents)
            elif style_name.startswith("toc"):
                try:
                    return int(style_name[3:]), True
                except ValueError:
                    pass
            # Check for outline level property if available
            elif hasattr(paragraph.style, "outline_level") and paragraph.style.outline_level:
                return paragraph.style.outline_level, True

        # 2. Check for outline level in paragraph properties
        if hasattr(paragraph._element, "pPr") and paragraph._element.pPr is not None:
            pPr = paragraph._element.pPr
            if (
                pPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl")
                is not None
            ):
                outline_level = pPr.find(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl"
                ).get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                if outline_level is not None:
                    try:
                        return (
                            int(outline_level) + 1,
                            True,
                        )  # Convert 0-based to 1-based level
                    except ValueError:
                        pass

        # 3. Check for special formatting as fallback - Less reliable.
        # Use the tracked-change/hyperlink-aware walker so a heading whose first
        # run is wrapped in <w:ins>/<w:del>/<w:hyperlink> is not missed here.
        first_run = next((run for run, _ in cls._iter_paragraph_runs(paragraph)), None)
        if first_run is not None:
            if first_run.bold or (
                first_run.font.size and first_run.font.size > 12 * 20
            ):  # Size in twips (20 twips = 1 point)
                # If text is numbered (e.g., "1.", "1.1", "1.1.1")
                text = cls._paragraph_plain_text(paragraph).strip()
                if text and text[0].isdigit():
                    # Count the number of dot-separated numbers
                    parts = text.split(" ", 1)[0].rstrip(".")
                    if all(p.isdigit() for p in parts.split(".")):
                        return len(parts.split(".")), False
                # Otherwise treat as level 1 heading
                return 1, False

        return 0, False

    # WordprocessingML main namespace, used to identify run wrappers by tag.
    _W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    @classmethod
    def _iter_paragraph_runs(cls, paragraph: Paragraph):
        """Yield ``(run, change)`` for every run in the paragraph, in document order.

        ``paragraph.runs`` only returns ``<w:r>`` elements that are *direct*
        children of ``<w:p>``. Runs nested inside ``<w:ins>`` (tracked insertion),
        ``<w:del>`` (tracked deletion) or ``<w:hyperlink>`` are silently dropped,
        so redline edits and linked text vanish. This walks the paragraph body
        recursively and returns each run together with its change type
        (``"ins"``, ``"del"`` or ``None``), preserving reading order.

        Args:
            paragraph: A python-docx paragraph object.
        """
        from docx.text.run import Run

        def walk(parent, change):
            for child in parent:
                tag = child.tag.split("}")[-1]
                if tag == "r":
                    yield Run(child, paragraph), change
                elif tag == "ins":
                    yield from walk(child, "ins")
                elif tag == "del":
                    yield from walk(child, "del")
                elif tag == "hyperlink":
                    # Hyperlink is not itself a change; keep the enclosing change.
                    yield from walk(child, change)

        yield from walk(paragraph._element, None)

    @classmethod
    def _paragraph_plain_text(cls, paragraph: Paragraph) -> str:
        """Concatenate the untagged text of every run, including tracked/linked runs.

        Used where a paragraph's raw text is needed (empty-paragraph detection,
        heading titles) so that a fully tracked-change paragraph is not treated
        as empty and dropped.
        """
        return "".join(cls._extract_run_text(run) for run, _ in cls._iter_paragraph_runs(paragraph))

    @staticmethod
    def _extract_run_text(run) -> str:
        """Extract text from a run, including special characters, symbols, and fields.

        Args:
            run: A python-docx run object.
        """
        text = run.text

        # Handle special elements
        if hasattr(run, "_element") and run._element is not None:
            for elem in run._element:
                if elem.tag.endswith("delText"):  # tracked-deletion text (not <w:t>)
                    text += elem.text or ""
                elif elem.tag.endswith("tab"):
                    text += "\t"
                elif elem.tag.endswith("br"):  # Line break
                    text += "\n"
                elif elem.tag.endswith("cr"):  # Carriage return
                    text += "\n"
                elif elem.tag.endswith("noBreakHyphen"):  # Non-breaking hyphen
                    text += "-"
                elif elem.tag.endswith("softHyphen"):  # Soft hyphen
                    text += "\u00ad"
                elif elem.tag.endswith("sym"):  # Symbol
                    if "char" in elem.attrib:
                        text += elem.attrib["char"]
                elif elem.tag.endswith("fldChar"):  # Field character (complex field)
                    if elem.get("fldCharType") == "begin":
                        # Start of a complex field (like a hyperlink)
                        pass
                elif elem.tag.endswith("instrText"):  # Field instruction text
                    field_text = elem.text
                    if field_text and field_text.strip().startswith("HYPERLINK"):
                        # Extract hyperlink URL
                        url = field_text.split('"')[1] if '"' in field_text else ""
                        text += f"[{text}]({url})"
                elif elem.tag.endswith("drawing"):  # Inline image
                    text += "[IMAGE]"

        return text

    def _extract_paragraph_text(self, paragraph: Paragraph) -> str:
        """Extract a paragraph's text with markdown-style formatting indicators.

        Args:
            paragraph: A python-docx paragraph object.
        """
        text_parts = []

        # Handle paragraph formatting
        if paragraph.style and paragraph.style.name:
            style_name = paragraph.style.name.lower()
            if not (style_name.startswith("heading") or style_name == "title"):
                text_parts.append(f"[{style_name}]")

        # Handle paragraph alignment
        if paragraph.alignment:
            alignment_map = {0: "left", 1: "center", 2: "right", 3: "justify"}
            if paragraph.alignment in alignment_map:
                text_parts.append(f"[align={alignment_map[paragraph.alignment]}]")

        for run, change in self._iter_paragraph_runs(paragraph):
            run_text = self._extract_run_text(run)
            if run_text.strip():
                formatted_text = run_text

                # Basic formatting
                if run.bold:
                    formatted_text = f"**{formatted_text}**"
                if run.italic:
                    formatted_text = f"*{formatted_text}*"
                if run.underline:
                    formatted_text = f"_{formatted_text}_"

                # Additional formatting - check attributes carefully
                if hasattr(run, "_element") and run._element is not None:
                    # Check for strikethrough
                    if run._element.rPr is not None:
                        strike = run._element.rPr.find(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}strike"
                        )
                        dstrike = run._element.rPr.find(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}dstrike"
                        )
                        if strike is not None or dstrike is not None:
                            formatted_text = f"~~{formatted_text}~~"

                # Font properties
                if hasattr(run, "font"):
                    # Vertical alignment (subscript/superscript)
                    if hasattr(run.font, "subscript") and run.font.subscript:
                        formatted_text = f"<sub>{formatted_text}</sub>"
                    if hasattr(run.font, "superscript") and run.font.superscript:
                        formatted_text = f"<sup>{formatted_text}</sup>"

                    # Text color
                    if hasattr(run.font, "color") and run.font.color and run.font.color.rgb:
                        formatted_text = (
                            f'<span style="color: #{run.font.color.rgb}">{formatted_text}</span>'
                        )

                    # Highlight color
                    if hasattr(run.font, "highlight_color") and run.font.highlight_color:
                        formatted_text = f"<mark>{formatted_text}</mark>"

                # Tag tracked changes inline so redline edits survive ingestion.
                if change == "ins":
                    formatted_text = f"[ins: {formatted_text}]"
                elif change == "del":
                    formatted_text = f"[del: {formatted_text}]"

                text_parts.append(formatted_text)

        return " ".join(text_parts)

    def _extract_footnote_text(self, footnote) -> str:
        """Extract text from a footnote."""
        footnote_text = []
        for paragraph in footnote.paragraphs:
            para_text = self._extract_paragraph_text(paragraph)
            if para_text.strip():
                footnote_text.append(para_text)
        return " ".join(footnote_text)

    @staticmethod
    def _extract_comment_text(comment) -> str:
        """Extract text from a comment."""
        return f"[Comment by {comment.author} at {comment.date}: {comment.text}]"

    def _extract_table_text(self, table) -> str:
        """Extract a table's text as a markdown table.

        Args:
            table: A python-docx table object.
        """
        table_text = []
        for i, row in enumerate(table.rows):
            row_text = []
            for cell in row.cells:
                # Extract all paragraphs from the cell
                cell_text = []
                for paragraph in cell.paragraphs:
                    para_text = self._extract_paragraph_text(paragraph)
                    if para_text.strip():
                        cell_text.append(para_text)
                row_text.append(" ".join(cell_text))

            # Format row as markdown table row
            if i == 0:
                table_text.append("| " + " | ".join(row_text) + " |")
                table_text.append("| " + " | ".join(["---"] * len(row_text)) + " |")
            else:
                table_text.append("| " + " | ".join(row_text) + " |")

        return "\n".join(table_text)

    def _extract_list_text(self, paragraph: Paragraph, list_style: str = None) -> str:
        """Extract a list item's text with markdown bullet or numbered formatting.

        Args:
            paragraph: A python-docx paragraph object.
            list_style: The list style (bullet or number).
        """
        text = self._extract_paragraph_text(paragraph)

        # Determine list style and level
        level = 0
        if paragraph._element.pPr and paragraph._element.pPr.numPr:
            numPr = paragraph._element.pPr.numPr
            if hasattr(numPr, "numId") and numPr.numId.val:
                # It's a numbered list
                if hasattr(numPr, "ilvl"):
                    level = int(numPr.ilvl.val)
                return f"{'    ' * level}1. {text}"

        # Default to bullet list
        return f"{'    ' * level}* {text}"

    def _build_document_tree(self, doc: Document) -> DocxNode:
        """Build a hierarchical node tree from the document's headings and content.

        Args:
            doc: The document to process.

        Returns:
            The root node of the document tree.
        """
        root = DocxNode("root", 0, node_type="root")
        stack = [root]
        current_content = []
        in_list = False

        print(f"Processing document with {len(doc.paragraphs)} paragraphs")

        # First, collect all sections to handle headers, footers, and footnotes
        sections = doc.sections
        for section in sections:
            # Process headers
            for header in [section.header]:
                if header.is_linked_to_previous:
                    continue
                header_text = []
                for paragraph in header.paragraphs:
                    para_text = self._extract_paragraph_text(paragraph)
                    if para_text.strip():
                        header_text.append(para_text)
                if header_text:
                    current_content.append("[Header]")
                    current_content.extend(header_text)
                    current_content.append("")

            # Process footers
            for footer in [section.footer]:
                if footer.is_linked_to_previous:
                    continue
                footer_text = []
                for paragraph in footer.paragraphs:
                    para_text = self._extract_paragraph_text(paragraph)
                    if para_text.strip():
                        footer_text.append(para_text)
                if footer_text:
                    current_content.append("[Footer]")
                    current_content.extend(footer_text)
                    current_content.append("")

        # Process main document body
        for element in doc._body._body:
            try:
                if element.tag.endswith("p"):  # Paragraph
                    para = Paragraph(element, doc)
                    # Get paragraph properties
                    style_name = para.style.name if para.style else "Normal"

                    # Determine paragraph type and level
                    heading_level, is_real_heading = self._get_heading_level(para)
                    is_list = bool(para._element.pPr and para._element.pPr.numPr)

                    # Plain text incl. tracked-change/hyperlink runs, so a fully
                    # redlined paragraph is not seen as empty and skipped below.
                    text = self._paragraph_plain_text(para).strip()

                    # Check for footnotes in the paragraph
                    footnotes = []
                    if hasattr(para._element, "xpath"):
                        for footnote_ref in para._element.xpath(".//w:footnoteReference"):
                            footnote_id = footnote_ref.get(
                                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id"
                            )
                            if hasattr(doc, "_footnotes") and doc._footnotes:
                                for footnote in doc._footnotes:
                                    if footnote.get("id") == footnote_id:
                                        footnote_text = self._extract_footnote_text(footnote)
                                        footnotes.append(f"[^{footnote_id}]: {footnote_text}")

                    # Check for comments in the paragraph
                    comments = []
                    if hasattr(para._element, "xpath"):
                        for comment_ref in para._element.xpath(".//w:commentReference"):
                            comment_id = comment_ref.get(
                                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id"
                            )
                            if hasattr(doc, "_comments") and doc._comments:
                                for comment in doc._comments:
                                    if comment.get("id") == comment_id:
                                        comment_text = self._extract_comment_text(comment)
                                        comments.append(comment_text)

                    if not text and not footnotes and not comments:  # Skip empty paragraphs
                        continue

                    # Handle different types of paragraphs
                    if (
                        heading_level > 0
                    ):  # Changed: Remove is_real_heading check to capture more headings
                        # Save accumulated content before creating new heading
                        if current_content:
                            stack[-1].content = "\n".join(current_content)
                            current_content = []

                        new_node = DocxNode(text, heading_level, node_type="heading")
                        new_node.properties.update(
                            {
                                "style": style_name,
                                "is_real_heading": str(is_real_heading),
                            }
                        )

                        # Find appropriate parent by checking levels
                        while len(stack) > 1:  # Keep at least root
                            if stack[-1].level < heading_level or (
                                stack[-1].level == heading_level
                                and stack[-1].properties.get("is_real_heading") == "True"
                                and is_real_heading is False
                            ):
                                break
                            stack.pop()

                        stack[-1].add_child(new_node)
                        stack.append(new_node)
                        in_list = False

                    elif is_list:
                        list_text = self._extract_list_text(para)
                        if not in_list:
                            current_content.append("")  # Add blank line before list
                        current_content.append(list_text)
                        # Add footnotes and comments if any
                        current_content.extend(footnotes)
                        current_content.extend(comments)
                        in_list = True

                    else:
                        # Regular paragraph
                        para_text = self._extract_paragraph_text(para)
                        if in_list:
                            current_content.append("")  # Add blank line after list
                        current_content.append(para_text)
                        # Add footnotes and comments if any
                        current_content.extend(footnotes)
                        current_content.extend(comments)
                        in_list = False

                elif element.tag.endswith("tbl"):  # Table
                    if current_content:
                        current_content.append("")  # Add blank line before table

                    from docx.table import Table

                    table = Table(element, doc)
                    table_text = self._extract_table_text(table)
                    current_content.append(table_text)
                    current_content.append("")  # Add blank line after table
                    in_list = False

                elif element.tag.endswith("sectPr"):  # Section break
                    if current_content:
                        stack[-1].content = "\n".join(current_content)
                        current_content = []
                    current_content.append("\n---\n")  # Add horizontal rule for section breaks
            except Exception as e:
                print(f"Error processing element: {e}")
                continue
        # Handle remaining content
        if current_content:
            stack[-1].content = "\n".join(current_content)

        # Clean up empty nodes
        def clean_node(node: DocxNode) -> bool:
            """Remove empty nodes and return whether this node should be kept"""
            # First clean children
            node.children = [child for child in node.children if clean_node(child)]
            # Keep node if it has content, non-empty children, or a meaningful title
            return bool(
                node.content.strip() or node.children or (node.title and node.title != "root")
            )

        root.children = [child for child in root.children if clean_node(child)]

        print(f"Document tree built with {len(root.children)} top-level sections")
        return root

    def _convert_to_outputs(
        self,
        node: DocxNode,
        id: str,
        parent_id: str = None,
        parent_titles: list[str] = None,
        parent_contents: list[str] = None,
        node_map: dict[str, Node] = None,
    ) -> tuple[list[Output], dict[DocxNode, Output], SubGraph]:
        outputs = []
        node_chunk_map = {}
        nodes = []  # For SubGraph
        edges = []  # For SubGraph
        if node_map is None:
            node_map = {}  # Track title nodes by id
        chunk_nodes = {}  # Track chunk nodes by id

        if parent_titles is None:
            parent_titles = []
        if parent_contents is None:
            parent_contents = []

        # Use truncated title for path building
        truncated_title = node.title[:50] + "..." if len(node.title) > 50 else node.title
        current_titles = parent_titles + ([truncated_title] if node.title != "root" else [])
        print(f"\nProcessing node: {truncated_title}")
        print(f"Current titles path: {' / '.join(current_titles)}")

        def add_bidirectional_edge(
            from_node: Node, to_node: Node, label: str, properties: dict = None
        ):
            """Helper function to add bidirectional edges between nodes"""
            if properties is None:
                properties = {}
            edges.append(Edge("", from_node, to_node, label, properties))
            edges.append(Edge("", to_node, from_node, label, properties))

        # Create title node for current node if it has a title
        if node.title != "root":
            # Use node's get_node_id method for stable ID generation
            title_node_id = node.get_node_id()
            if title_node_id not in node_map:
                title_node = Node(
                    _id=title_node_id,
                    name=truncated_title,  # Use truncated title for display
                    label="Title",
                    properties={
                        "level": str(node.level),
                        "type": node.node_type,
                        "full_title": node.title,  # Store full title as property
                        **node.properties,  # Include other properties
                    },
                )
                nodes.append(title_node)
                node_map[title_node_id] = title_node
                print(f"Created title node: {truncated_title}")

            # Create chunk for current node if it has content or is a leaf node
            if node.content or not node.children:
                # Use truncated titles for path
                full_title = " / ".join(filter(None, current_titles))
                print(f"Creating chunk for: {full_title}")

                # Store parent content separately
                parent_content = (
                    "\n".join(filter(None, parent_contents)) if parent_contents else None
                )

                # Use node's content if available, otherwise use title as content for leaf nodes
                chunk_content = node.content if node.content else node.title
                current_output = Chunk(
                    id=f"{generate_hash_id(node.get_node_id())}",  # Use stable node ID for chunk ID
                    parent_id=parent_id,
                    name=full_title,
                    content=chunk_content,
                    parent_content=parent_content,
                    type=ChunkTypeEnum.Text,
                )

                # Apply length splitter if configured and content is too long
                if self.length_splitter:
                    split_chunks = self.length_splitter.slide_window_chunk(
                        current_output,
                        self.length_splitter.split_length,
                        self.length_splitter.window_length,
                    )
                    for idx, split_chunk in enumerate(split_chunks):
                        split_chunk.parent_id = current_output.id
                        # Add index to split chunk name for clarity
                        split_chunk.name = f"{full_title} (Part {idx + 1})"
                        outputs.append(split_chunk)
                        # Create chunk node for each split chunk
                        chunk_node = Node(
                            _id=split_chunk.id,
                            name=split_chunk.name,
                            label="Chunk",
                            properties={
                                "content": split_chunk.content[:100] + "..."
                            },  # Truncate content in properties
                        )
                        nodes.append(chunk_node)
                        chunk_nodes[split_chunk.id] = chunk_node
                        # Add bidirectional edges between title and split chunk
                        add_bidirectional_edge(node_map[title_node_id], chunk_node, "hasContent")
                    # Map the original node to all split chunks
                    node_chunk_map[node] = split_chunks
                else:
                    outputs.append(current_output)
                    node_chunk_map[node] = current_output
                    # Create single chunk node
                    chunk_node = Node(
                        _id=current_output.id,
                        name=full_title,
                        label="Chunk",
                        properties={
                            "content": (
                                chunk_content[:100] + "..."
                                if len(chunk_content) > 100
                                else chunk_content
                            )
                        },
                    )
                    nodes.append(chunk_node)
                    chunk_nodes[current_output.id] = chunk_node
                    # Add bidirectional edges between title and chunk
                    add_bidirectional_edge(node_map[title_node_id], chunk_node, "hasContent")

        # Process children
        if node.children:
            print(f"Processing {len(node.children)} children")
            for child in node.children:
                (
                    child_outputs,
                    child_node_chunk_map,
                    child_subgraph,
                ) = self._convert_to_outputs(
                    child,
                    id,
                    parent_id=parent_id,
                    parent_titles=current_titles,
                    parent_contents=parent_contents + ([node.content] if node.content else []),
                    node_map=node_map,
                )
                outputs.extend(child_outputs)
                node_chunk_map.update(child_node_chunk_map)
                nodes.extend(child_subgraph.nodes)
                edges.extend(child_subgraph.edges)

                # Add title hierarchy relationship if both parent and child have titles
                if node.title != "root" and child.title != "root":
                    parent_node = node_map[node.get_node_id()]
                    child_node = node_map[child.get_node_id()]
                    add_bidirectional_edge(
                        parent_node, child_node, "hasChild", {"level": str(child.level)}
                    )

        return outputs, node_chunk_map, SubGraph(nodes=nodes, edges=edges)

    def _invoke(self, data: Input, **kwargs) -> tuple[list[Output], SubGraph]:
        """Read the Docx file and return chunks following its title hierarchy.

        Args:
            data: The path to the Docx file to process.

        Raises:
            ValueError: If the input is empty.
            IOError: If the file cannot be read.
        """
        if not data:
            raise ValueError("Input cannot be empty")

        try:
            doc = Document(data)
            document_root = self._build_document_tree(doc)
        except OSError as e:
            raise OSError(f"Failed to read file: {input}") from e

        basename, _ = os.path.splitext(os.path.basename(data))
        # Create a new root node with the file name and transfer document_root's children
        file_root = DocxNode(basename, 0)
        file_root.children = document_root.children  # Transfer children directly
        file_root.content = document_root.content  # Transfer content if any

        chunks, _, subgraph = self._convert_to_outputs(file_root, data)
        print("\nExtracted chunks:")
        for chunk in chunks:
            print(f"\nChunk: {chunk.name}")
            print(f"Content: {chunk.content}")
            if chunk.parent_content:
                print(f"Parent Content: {chunk.parent_content}")
        return chunks


if __name__ == "__main__":
    reader = ReaderABC.from_config({"type": "docx_reader"})
    chunks = reader.invoke("/Users/zhangxinhong.zxh/Downloads/default.docx", write_ckpt=False)
    print("Extracted chunks:")
    for chunk in chunks:
        print(f"\nChunk: {chunk.name}")
        print(f"Content: {chunk.content}")
        if chunk.parent_content:
            print(f"Parent Content: {chunk.parent_content}")
