import logging
import re
from typing import Dict, List, Pattern, Tuple

from .document_chunking import BaseDocumentChunker, TOCNode

# Get logger for this module
logger = logging.getLogger(__name__)


class MarkdownTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on Markdown headers.

    This chunker analyzes markdown text, identifies headings (both ATX and Setext style),
    and builds a tree structure representing the document's organization. It handles
    code blocks appropriately to prevent false header detection.
    """

    # Regex patterns for markdown parsing
    ATX_HEADER_PATTERN: Pattern = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$")
    FENCED_CODE_BLOCK_PATTERN: Pattern = re.compile(
        r"```(?:\w+)?\n[\s\S]*?\n```", re.MULTILINE
    )
    INDENTED_CODE_BLOCK_PATTERN: Pattern = re.compile(
        r"(?:^( {4}|\t).*\n)+", re.MULTILINE
    )

    def __init__(self, markdown_text: str, source_display_name: str):
        """
        Initialize the chunker with markdown text.

        Args:
            markdown_text: The markdown text content to be parsed
            source_display_name: The original name of the source (e.g., filename or "markdown_text")

        Raises:
            ValueError: If markdown_text is None or empty
        """
        if not markdown_text:
            raise ValueError("Markdown text cannot be None or empty")

        super().__init__(source_path="", source_display_name=source_display_name)
        self.markdown_text = markdown_text
        self.lines: List[str] = []
        self._document_loaded = False
        self.code_blocks: Dict[str, str] = {}
        self.original_text: str = markdown_text
        self._process_code_blocks()

    def load_document(self) -> None:
        """
        Load the markdown document and split into lines.

        This method prepares the markdown text for processing by splitting it into
        individual lines that can be analyzed for headers and content.

        Raises:
            Exception: If the markdown text can't be split into lines
        """
        try:
            self.lines = self.markdown_text.splitlines()
            self._document_loaded = True
        except Exception as e:
            logger.error(f"Error loading markdown: {e}")
            raise ValueError(f"Failed to load markdown document: {e}")

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the markdown headers.

        This method analyzes the markdown document for headers, creates a hierarchical
        structure, and extracts content for each section.

        Returns:
            The root node of the TOC tree

        Raises:
            ValueError: If headers can't be extracted properly
        """
        if not self._document_loaded:
            self.load_document()

        # Initialize the document tree
        self.root_node = TOCNode(title="Document Root", page_num=0, level=0)

        # Find all headers and their respective line numbers
        try:
            headers = self._extract_headers()
        except Exception as e:
            logger.error(f"Error extracting headers: {e}")
            headers = []

        if not headers:
            # No headers found, treat the entire document as one chunk
            # Use original text with code blocks intact
            self.root_node.content = self.original_text
            self.root_node.end_page = 0  # Only one page for markdown
            return self.root_node

        # Process headers and build TOC tree
        try:
            self._build_tree_from_headers(headers)
        except Exception as e:
            logger.error(f"Error building tree from headers: {e}")
            # Fallback to basic document
            self.root_node.content = self.original_text

        return self.root_node

    def _build_tree_from_headers(self, headers: List[Tuple[int, int, str]]) -> None:
        """
        Build the TOC tree from the extracted headers.

        Args:
            headers: List of tuples with (line_number, header_level, header_title)
        """
        for i, (line_num, level, title) in enumerate(headers):
            # Create a new node for this header
            node = TOCNode(
                title=title,
                page_num=line_num,  # Using line number instead of page number for markdown
                level=level,
            )

            # Find the appropriate parent for this node based on its level
            parent = self._find_parent_for_level(self.root_node, level)
            parent.add_child(node)

            # Determine the content range for this node
            start_line = line_num + 1  # Start after the header line

            # End line is either the line before the next header or the end of document
            end_line = len(self.lines)
            if i < len(headers) - 1:
                end_line = headers[i + 1][0]  # Line number of next header

            # Extract content for this section
            content_slice = self._extract_content(start_line, end_line)
            # Restore code blocks in extracted content
            node.content = self._restore_code_blocks(content_slice)
            node.end_page = 0  # Markdown is treated as a single page

    def _extract_headers(self) -> List[Tuple[int, int, str]]:
        """
        Extract headers and their line numbers from markdown text.

        Returns:
            List of tuples with (line_number, header_level, header_title)
        """
        headers = []
        # ATX style headers already have a regex pattern defined as a class variable

        # Track potential Setext headers for validation
        potential_setext_headers: List[Tuple[int, str]] = []

        for line_num, line in enumerate(self.lines):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Check for ATX style headers (# Header)
            atx_match = self.ATX_HEADER_PATTERN.match(line_stripped)
            if atx_match:
                level = len(atx_match.group(1))  # Number of # characters
                title = atx_match.group(2).strip()
                headers.append((line_num, level, title))
                continue

            # Store potential Setext header candidates
            if line_num > 0 and line_num not in [h[0] for h in headers]:
                potential_setext_headers.append((line_num, line_stripped))

        # Process potential Setext headers
        for i, (line_num, line) in enumerate(potential_setext_headers):
            # Check if this line could be a Setext header underline
            if all(c == "=" for c in line):
                # Check the previous line to see if it's not an ATX header
                if (
                    line_num > 0
                    and self.lines[line_num - 1].strip()
                    and not self.ATX_HEADER_PATTERN.match(
                        self.lines[line_num - 1].strip()
                    )
                ):
                    title = self.lines[line_num - 1].strip()
                    headers.append((line_num - 1, 1, title))  # Level 1 header
            elif all(c == "-" for c in line):
                # Make sure it's not a list item, horizontal rule, or table delimiter
                if (
                    line_num > 0
                    and self.lines[line_num - 1].strip()
                    and not self.ATX_HEADER_PATTERN.match(
                        self.lines[line_num - 1].strip()
                    )
                ):
                    prev_line = self.lines[line_num - 1].strip()
                    # Ensure it's not already a header and not a horizontal rule (---)
                    if len(line) >= 2 and prev_line:
                        # Avoid false positives like list items or table delimiters
                        if (
                            not prev_line.startswith(("-", "*", "+"))
                            and "|" not in prev_line
                        ):
                            headers.append(
                                (line_num - 1, 2, prev_line)
                            )  # Level 2 header

        # Sort headers by line number
        headers.sort(key=lambda x: x[0])
        return headers

    def _find_parent_for_level(self, node: TOCNode, target_level: int) -> TOCNode:
        """
        Find the appropriate parent node for a node with the given level.

        Args:
            node: Current node to start search from
            target_level: The level of the node we want to find a parent for

        Returns:
            The appropriate parent node
        """
        # If this is a level 1 header, its parent is the root node
        if target_level == 1:
            return self.root_node

        # If current node is at the level just above our target, it's our parent
        if node.level == target_level - 1:
            return node

        # If node has children, check the last child first (most recent node at that level)
        if node.children:
            last_child = node.children[-1]
            # If the last child's level is less than our target level, it could be our parent
            if last_child.level < target_level:
                return self._find_parent_for_level(last_child, target_level)

        # If we're here, we need to move up the tree
        if node.parent:
            return self._find_parent_for_level(node.parent, target_level)

        # Fallback to root node if no appropriate parent is found
        return self.root_node

    def _extract_content(self, start_line: int, end_line: int) -> str:
        """
        Extract content from the specified line range.

        Args:
            start_line: Starting line number (inclusive)
            end_line: Ending line number (exclusive)

        Returns:
            The extracted content as a string
        """
        if start_line >= end_line or start_line >= len(self.lines):
            return ""

        # Adjust end_line if it exceeds the document length
        end_line = min(end_line, len(self.lines))

        content_lines = self.lines[start_line:end_line]
        return "\n".join(content_lines)

    def _process_code_blocks(self) -> None:
        """
        Extract fenced and indented code blocks from the markdown text and replace them with placeholders.

        This prevents code block content (especially comments) from being misidentified as headers.
        """
        # Keep original text for later restoration
        self.original_text = self.markdown_text

        # Process fenced code blocks first (```code```)
        def _fenced_replacer(match):
            placeholder = f"__CODE_BLOCK_{len(self.code_blocks)}__"
            self.code_blocks[placeholder] = match.group(0)
            return placeholder

        self.markdown_text = self.FENCED_CODE_BLOCK_PATTERN.sub(
            _fenced_replacer, self.markdown_text
        )

        # Then process indented code blocks (4 spaces or tab)
        def _indented_replacer(match):
            placeholder = f"__INDENTED_BLOCK_{len(self.code_blocks)}__"
            self.code_blocks[placeholder] = match.group(0)
            return placeholder

        self.markdown_text = self.INDENTED_CODE_BLOCK_PATTERN.sub(
            _indented_replacer, self.markdown_text
        )

    def _restore_code_blocks(self, text: str) -> str:
        """
        Restore code block placeholders in text back to their original code block content.

        Args:
            text: Text containing code block placeholders

        Returns:
            Text with original code blocks restored
        """
        result = text
        for placeholder, code in self.code_blocks.items():
            result = result.replace(placeholder, code)
        return result

    def close(self) -> None:
        """Clean up resources"""
        self.lines = []
        self.code_blocks = {}
        self._document_loaded = False
