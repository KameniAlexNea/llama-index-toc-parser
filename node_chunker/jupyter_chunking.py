import json
import logging
import re
from typing import List, Optional, Tuple

import nbformat

from .document_chunking import BaseDocumentChunker, TOCNode

# Get logger for this module
logger = logging.getLogger(__name__)


class JupyterNotebookTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on Jupyter Notebook
    markdown cells with heading structures.
    """

    def __init__(self, notebook_path: str, source_display_name: str):
        """
        Initialize the chunker with the path to the Jupyter Notebook.

        Args:
            notebook_path: Path to the .ipynb file or JSON content
            source_display_name: The original name of the source
        """
        super().__init__(notebook_path, source_display_name)
        self.notebook = None
        self.cells = []
        self._document_loaded = False
        # Regex for ATX style headers (# Header)
        self.header_pattern = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", re.MULTILINE)

    def load_document(self) -> None:
        """Load the Jupyter notebook and extract its cells"""
        try:
            # Check if source_path is a file path or JSON content
            try:
                self.notebook = nbformat.read(self.source_path, as_version=4)
            except (FileNotFoundError, IsADirectoryError):
                # Treat as JSON content
                notebook_content = json.loads(self.source_path)
                self.notebook = nbformat.from_dict(notebook_content)

            self.cells = self.notebook.cells
            self._document_loaded = True
        except Exception as e:
            logger.error(f"Error loading Jupyter notebook: {e}")
            raise

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from markdown cells with headers.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        # Initialize the document tree
        self.root_node = TOCNode(title="Notebook Root", page_num=0, level=0)

        # Extract headers from markdown cells
        headers = self._extract_headers()

        if not headers:
            # No headers found, treat the entire notebook as one chunk
            self.root_node.content = self._extract_all_cell_content()
            self.root_node.end_page = len(self.cells) - 1
            return self.root_node

        # Process headers and build TOC tree
        for i, (cell_idx, header_level, header_text, header_pos) in enumerate(headers):
            # Create a new node for this header
            node = TOCNode(
                title=header_text,
                page_num=cell_idx,  # Using cell index as page number
                level=header_level,
            )

            # Find the appropriate parent for this node based on its level
            parent = self._find_parent_for_level(self.root_node, header_level)
            parent.add_child(node)

            # Content will include everything after the header in the current cell
            # and content from subsequent cells until the next header cell
            node.content = self._extract_section_content(
                cell_idx, header_pos, headers[i + 1] if i + 1 < len(headers) else None
            )
            node.end_page = (
                headers[i + 1][0] - 1 if i + 1 < len(headers) else len(self.cells) - 1
            )

        return self.root_node

    def _extract_headers(self) -> List[Tuple[int, int, str, int]]:
        """
        Extract headers from markdown cells.

        Returns:
            List of tuples with (cell_index, header_level, header_text, position_in_cell)
        """
        headers = []

        for cell_idx, cell in enumerate(self.cells):
            if cell.cell_type == "markdown":
                # Look for headers in markdown cells
                source = cell.source
                matches = list(self.header_pattern.finditer(source))

                for match in matches:
                    level = len(match.group(1))  # Number of # characters
                    title = match.group(2).strip()
                    if title:
                        headers.append((cell_idx, level, title, match.start()))

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

    def _extract_section_content(
        self, cell_idx: int, header_pos: int, next_header: Optional[Tuple] = None
    ) -> str:
        """
        Extract content for a section starting from a header.

        Args:
            cell_idx: Index of the cell containing the header
            header_pos: Position of the header in the cell source
            next_header: The next header tuple or None

        Returns:
            The extracted content as a string
        """
        content_parts = []
        current_cell = self.cells[cell_idx]

        # For the header cell, include only content after the header
        if current_cell.cell_type == "markdown":
            header_line_end = current_cell.source.find("\n", header_pos)
            if header_line_end == -1:  # Header is the last line
                header_line_end = len(current_cell.source)

            # Add content after the header
            after_header = current_cell.source[header_line_end:].strip()
            if after_header:
                content_parts.append(after_header)

        # Add content from subsequent cells until the next header cell
        next_cell_idx = cell_idx + 1
        end_cell_idx = next_header[0] if next_header is not None else len(self.cells)

        while next_cell_idx < end_cell_idx:
            cell = self.cells[next_cell_idx]

            if cell.cell_type == "markdown":
                content_parts.append(cell.source)
            elif cell.cell_type == "code":
                # For code cells, format with code markers
                code_content = cell.source.strip()
                if code_content:
                    content_parts.append(f"```python\n{code_content}\n```")

                # Include outputs if present
                if hasattr(cell, "outputs") and cell.outputs:
                    for output in cell.outputs:
                        if "text" in output:
                            content_parts.append(f"```\n{output['text']}\n```")
                        elif "data" in output:
                            if "text/plain" in output["data"]:
                                content_parts.append(
                                    f"```\n{output['data']['text/plain']}\n```"
                                )

            next_cell_idx += 1

        return "\n\n".join(content_parts)

    def _extract_all_cell_content(self) -> str:
        """Extract content from all cells in the notebook"""
        content_parts = []

        for cell in self.cells:
            if cell.cell_type == "markdown":
                content_parts.append(cell.source)
            elif cell.cell_type == "code":
                code_content = cell.source.strip()
                if code_content:
                    content_parts.append(f"```python\n{code_content}\n```")

                # Include outputs if present
                if hasattr(cell, "outputs") and cell.outputs:
                    for output in cell.outputs:
                        if "text" in output:
                            content_parts.append(f"```\n{output['text']}\n```")
                        elif "data" in output:
                            if "text/plain" in output["data"]:
                                content_parts.append(
                                    f"```\n{output['data']['text/plain']}\n```"
                                )

        return "\n\n".join(content_parts)

    def close(self) -> None:
        """Clean up resources"""
        self.notebook = None
        self.cells = []
        self._document_loaded = False
