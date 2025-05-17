import re
from typing import List, Tuple

from .document_chunking import BaseDocumentChunker, TOCNode


class MarkdownTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on Markdown headers.
    """

    def __init__(self, markdown_text: str, source_display_name: str):
        """
        Initialize the chunker with markdown text.

        Args:
            markdown_text: The markdown text content
            source_display_name: The original name of the source (e.g., filename or "markdown_text")
        """
        super().__init__(source_path="", source_display_name=source_display_name)
        self.markdown_text = markdown_text
        self.lines = []
        self._document_loaded = False

    def load_document(self) -> None:
        """Load the markdown document and split into lines"""
        try:
            self.lines = self.markdown_text.splitlines()
            self._document_loaded = True
        except Exception as e:
            print(f"Error loading markdown: {e}")
            raise

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the markdown headers.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        # Initialize the document tree
        self.root_node = TOCNode(title="Document Root", page_num=0, level=0)
        current_node = self.root_node

        # Find all headers and their respective line numbers
        headers = self._extract_headers()

        if not headers:
            # No headers found, treat the entire document as one chunk
            self.root_node.content = self.markdown_text
            self.root_node.end_page = 0  # Only one page for markdown
            return self.root_node

        # Process headers and build TOC tree
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
            node.content = self._extract_content(start_line, end_line)
            node.end_page = 0  # Markdown is treated as a single page

        return self.root_node

    def _extract_headers(self) -> List[Tuple[int, int, str]]:
        """
        Extract headers and their line numbers from markdown text.

        Returns:
            List of tuples with (line_number, header_level, header_title)
        """
        headers = []
        # Regex for ATX style headers (# Header)
        atx_header_pattern = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$")

        for line_num, line in enumerate(self.lines):
            # Check for ATX style headers
            atx_match = atx_header_pattern.match(line.strip())
            if atx_match:
                level = len(atx_match.group(1))  # Number of # characters
                title = atx_match.group(2).strip()
                headers.append((line_num, level, title))
                continue

            # Check for Setext style headers (underlined with === or ---)
            if line_num > 0 and line.strip() and all(c == "=" for c in line.strip()):
                title = self.lines[line_num - 1].strip()
                if title:  # Make sure the previous line has content
                    headers.append((line_num - 1, 1, title))  # Level 1 header
                    continue

            if line_num > 0 and line.strip() and all(c == "-" for c in line.strip()):
                title = self.lines[line_num - 1].strip()
                # Ensure it's not already a header
                if title and not atx_header_pattern.match(title):
                    headers.append((line_num - 1, 2, title))  # Level 2 header

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

    def close(self) -> None:
        """Clean up resources"""
        self.lines = []
        self._document_loaded = False
