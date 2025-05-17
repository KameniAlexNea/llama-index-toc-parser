import fitz  # PyMuPDF
import requests
import tempfile
import os
from typing import List

from llama_index.core.schema import (
    TextNode,
    NodeRelationship,
)
from .document_chunking import BaseDocumentChunker, TOCNode


class PDFTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on the PDF's table of contents.
    """

    def __init__(self, pdf_path: str, source_display_name: str):
        """
        Initialize the chunker with the path to the PDF file.

        Args:
            pdf_path: Path to the PDF file (can be temporary)
            source_display_name: The original name of the source (e.g., URL or original filename)
        """
        super().__init__(pdf_path, source_display_name)
        self.doc = None
        self.toc = None
        self._document_loaded = False

    def load_document(self) -> None:
        """Load the PDF document and extract its TOC"""
        try:
            # Use PyMuPDF for both TOC extraction and text extraction
            self.doc = fitz.open(self.source_path)
            self.toc = self.doc.get_toc()
            self._document_loaded = True

            if not self.toc:
                print("Warning: No TOC found in the document.")
        except Exception as e:
            print(f"Error loading PDF: {e}")
            raise

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the TOC entries.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        if not self.toc:
            # Create a single node for the whole document
            self.root_node.end_page = self.doc.page_count - 1
            for page_num in range(self.doc.page_count):
                page = self.doc.load_page(page_num)
                self.root_node.content += page.get_text() + "\n"
            return self.root_node

        # Process PyMuPDF TOC and create a tree
        self._process_outline(self.toc, self.root_node)

        # Now determine end pages and extract content
        self._set_end_pages_and_content(self.root_node)

        return self.root_node

    def _process_outline(self, toc_items, parent_node: TOCNode, level=1):
        """
        Process TOC items into our node tree.

        Args:
            toc_items: TOC items from PyMuPDF
            parent_node: The parent node to attach to
            level: Current hierarchy level
        """
        if not toc_items:
            return

        processed_indices = set()

        for i, item in enumerate(toc_items):
            if i in processed_indices:
                continue

            # PyMuPDF TOC format is [level, title, page, ...]
            if len(item) >= 3:
                item_level, title, page_num = item[:3]

                # Adjust page number (PyMuPDF pages are 1-based, we want 0-based)
                page_num = page_num - 1 if page_num > 0 else 0

                current_item_level_from_toc = item_level  # TOC level from PDF

                # Only process items that match our current tree level
                if current_item_level_from_toc == level:
                    node = TOCNode(
                        title=title, page_num=page_num, level=level, parent=parent_node
                    )
                    parent_node.add_child(node)
                    processed_indices.add(i)

                    # Find children of this node (items with higher TOC level, indicating deeper nesting)
                    children_toc_items = []
                    j = i + 1
                    while j < len(toc_items):
                        if (
                            toc_items[j][0] > current_item_level_from_toc
                        ):  # Deeper level
                            children_toc_items.append(toc_items[j])
                            processed_indices.add(j)
                        elif (
                            toc_items[j][0] <= current_item_level_from_toc
                        ):  # Same or shallower level, stop collecting children
                            break
                        j += 1

                    if children_toc_items:
                        # For children, the *next* level in our tree is level + 1
                        # The first level of these children_toc_items will be current_item_level_from_toc + 1
                        # We need to pass the children_toc_items and the *expected* next level for *them*
                        # which is children_toc_items[0][0] if it exists, or simply level + 1 for our tree structure.
                        # The _process_outline function itself uses its 'level' parameter to filter.
                        self._process_outline(children_toc_items, node, level + 1)

    def _set_end_pages_and_content(self, node: TOCNode) -> int:
        """
        Recursively set end pages and extract content for each node.

        Args:
            node: The current node to process

        Returns:
            The end page of this node
        """
        if not node.children:
            # Leaf node
            next_section_start_page = self.doc.page_count  # Default if no next sibling

            if node.parent:
                siblings = node.parent.children
                try:
                    idx = siblings.index(node)
                    if idx < len(siblings) - 1:  # If there is a next sibling
                        next_section_start_page = siblings[idx + 1].page_num
                except ValueError:
                    pass  # Should not typically occur

            calculated_end_page = next_section_start_page - 1
            node.end_page = max(
                node.page_num, min(calculated_end_page, self.doc.page_count - 1)
            )

            node.content = self._extract_content(node.page_num, node.end_page)
            return node.end_page

        # Non-leaf node
        last_child_end_page = -1
        for child_idx, child in enumerate(node.children):
            child_end_page = self._set_end_pages_and_content(child)
            last_child_end_page = max(last_child_end_page, child_end_page)

        # A non-leaf node's content ends where its first child begins (if text exists before it)
        # Its overall span (end_page) is determined by its last child's end_page.
        node.end_page = (
            last_child_end_page if last_child_end_page != -1 else node.page_num
        )

        # Content for non-leaf node: text from its start page up to the page before its first child starts.
        # Or, if it has no children with content or all children start on same page, its own content might be empty.
        if node.children:
            first_child_page = node.children[0].page_num
            # Ensure there are pages between node.page_num and first_child_page
            if first_child_page > node.page_num:
                node.content = self._extract_content(
                    node.page_num, first_child_page - 1
                )
            # First child starts on the same page or earlier (error), so no preceding content for parent
            else:
                node.content = ""
        elif (
            not node.content
        ):  # If it's a leaf node that somehow didn't get content above
            node.content = self._extract_content(node.page_num, node.end_page)

        # If a non-leaf node has no specific content of its own (e.g. "Document Root" or a chapter title page)
        # and its end_page was not updated by children, ensure it's at least its own start page.
        if node.end_page is None or node.end_page < node.page_num:
            node.end_page = node.page_num
            if (
                not node.content
            ):  # If it has no children and no content, extract for its single page
                node.content = self._extract_content(node.page_num, node.end_page)

        return node.end_page

    def _extract_content(self, start_page: int, end_page: int) -> str:
        """Extract text content from a range of pages"""
        content = ""
        # Ensure start_page is not greater than end_page
        if start_page > end_page:
            return ""  # Or handle as an error/warning

        for page_idx in range(start_page, end_page + 1):
            if 0 <= page_idx < self.doc.page_count:
                page = self.doc.load_page(page_idx)
                content += page.get_text() + "\n"
        return content

    def close(self) -> None:
        """Close the PDF file"""
        if self.doc:
            self.doc.close()
            self.doc = None  # Ensure it's None after closing
            self._document_loaded = False

