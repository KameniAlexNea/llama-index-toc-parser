import logging
from typing import Optional, List

import fitz  # PyMuPDF

from .document_chunking import BaseDocumentChunker, TOCNode

logger = logging.getLogger(__name__)
TEXT_EXTRACTION_FLAGS = (
    fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_LIGATURES & ~fitz.TEXT_PRESERVE_IMAGES
)


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
        self.root_node.y_position = 0.0  # Document root starts at y=0 on page 0

    def load_document(self) -> None:
        """Load the PDF document and extract its TOC."""
        try:
            self.doc = fitz.open(self.source_path)
            self.toc = self.doc.get_toc()
            self._document_loaded = True

            if not self.toc:
                logger.warning("No TOC found in the document.")
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
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

        # Determine end pages and extract content
        self._set_end_pages_and_content(self.root_node)

        return self.root_node

    def _find_heading_y_position(self, page: fitz.Page, title: str) -> float:
        """
        Find the y-coordinate of a heading on a page.
        Returns the y-coordinate (bbox[1]) or 0.0 if not found.
        """
        # Clean the title for matching
        clean_title = "".join(c for c in title if c.isalnum() or c.isspace()).strip().lower()
        if not clean_title:
            return 0.0

        blocks = page.get_text("dict", flags=TEXT_EXTRACTION_FLAGS)["blocks"]
        
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_text = "".join(span["text"] for span in line.get("spans", []))
                    clean_line = "".join(
                        c for c in line_text if c.isalnum() or c.isspace()
                    ).strip().lower()
                    
                    if clean_title in clean_line:
                        return block["bbox"][1]  # y0 of the block
                        
        return 0.0  # Fallback if title not found

    def _process_outline(self, toc_items: List, parent_node: TOCNode, level=1) -> None:
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
                page_num = max(0, page_num - 1)
                current_item_level = item_level  # TOC level from PDF

                # Only process items that match our current tree level
                if current_item_level == level:
                    page_obj = self.doc.load_page(page_num)
                    y_pos = self._find_heading_y_position(page_obj, title)
                    node = TOCNode(
                        title=title,
                        page_num=page_num,
                        level=level,
                        parent=parent_node,
                        y_position=y_pos,
                    )
                    parent_node.add_child(node)
                    processed_indices.add(i)

                    # Find children of this node
                    children_toc_items = []
                    j = i + 1
                    while j < len(toc_items):
                        if toc_items[j][0] > current_item_level:  # Deeper level
                            children_toc_items.append(toc_items[j])
                            processed_indices.add(j)
                        elif toc_items[j][0] <= current_item_level:  # Same or higher level
                            break
                        j += 1

                    if children_toc_items:
                        self._process_outline(children_toc_items, node, level + 1)

    def _set_end_pages_and_content(self, node: TOCNode) -> int:
        """
        Recursively set end pages and extract content for each node.

        Args:
            node: The current node to process

        Returns:
            The end page of this node (overall span)
        """
        # Determine node's overall end page (span)
        if not node.children:
            # Leaf node: end_page is determined by the next sibling or document end
            next_section_start_page = self.doc.page_count
            if node.parent and node.parent.children:
                siblings = node.parent.children
                try:
                    idx = siblings.index(node)
                    if idx < len(siblings) - 1:
                        next_section_start_page = siblings[idx + 1].page_num
                except ValueError:
                    pass  # Should not occur

            node.end_page = max(
                node.page_num, min(next_section_start_page - 1, self.doc.page_count - 1)
            )
        else:
            # Non-leaf node: end_page is determined by the last child's end_page
            last_child_end_page = -1
            for child in node.children:
                child_end_page = self._set_end_pages_and_content(child)
                last_child_end_page = max(last_child_end_page, child_end_page)
            node.end_page = max(node.page_num, last_child_end_page)

        # Extract content for the current node
        current_node_start_y = node.y_position if node.y_position is not None else 0.0
        content_end_page_idx = node.end_page
        content_end_y_on_final_page = None

        if node.children:
            first_child = node.children[0]
            if first_child.page_num > node.page_num:
                # Parent's content ends on the page before the first child's page
                content_end_page_idx = first_child.page_num - 1
            else:  # first_child.page_num == node.page_num
                # Parent's content ends on the same page, just before the first child
                content_end_page_idx = node.page_num
                content_end_y_on_final_page = first_child.y_position
        else:  # Leaf node
            # Check if next sibling is on this content_end_page_idx
            if node.parent and node.parent.children:
                siblings = node.parent.children
                try:
                    idx = siblings.index(node)
                    if idx < len(siblings) - 1:
                        next_sibling = siblings[idx + 1]
                        if next_sibling.page_num == content_end_page_idx:
                            content_end_y_on_final_page = next_sibling.y_position
                except ValueError:
                    pass

        # Ensure content_end_page_idx is valid
        actual_content_end_page = min(
            max(node.page_num, content_end_page_idx),
            self.doc.page_count - 1
        )

        if node.page_num > actual_content_end_page:
            node.content = ""  # No pages for content
        else:
            node.content = self._extract_content(
                node.page_num,
                actual_content_end_page,
                start_y_on_first_page=current_node_start_y,
                end_y_on_final_page=content_end_y_on_final_page,
            )

        # Fallback for nodes that might have been missed
        if node.title == "Document Root" and not self.toc and not node.content:
            node.content = self._extract_content(0, self.doc.page_count - 1)

        # Ensure end_page is at least the start page
        if node.end_page is None or node.end_page < node.page_num:
            node.end_page = node.page_num

        return node.end_page

    def _extract_content(
        self,
        start_page_idx: int,
        end_page_idx: int,
        start_y_on_first_page: Optional[float] = None,
        end_y_on_final_page: Optional[float] = None,
    ) -> str:
        """
        Extract text content from a range of pages, respecting y-boundaries on first/last page.
        """
        content_parts = []

        # Ensure start_page is not greater than end_page
        if start_page_idx > end_page_idx:
            return ""

        for page_num in range(start_page_idx, end_page_idx + 1):
            if not (0 <= page_num < self.doc.page_count):
                continue

            page = self.doc.load_page(page_num)

            # Determine y-boundaries for the current page
            start_y = (
                start_y_on_first_page if page_num == start_page_idx and 
                start_y_on_first_page is not None else 0.0
            )
            
            end_y = (
                end_y_on_final_page if page_num == end_page_idx and 
                end_y_on_final_page is not None else float("inf")
            )

            # If start_y is greater or equal to end_y on the same page, skip
            if start_y >= end_y:
                continue

            blocks = page.get_text("dict", flags=TEXT_EXTRACTION_FLAGS)["blocks"]
            page_content = []
            
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    block_y0 = block["bbox"][1]  # Top of block
                    block_y1 = block["bbox"][3]  # Bottom of block

                    # Check if block is within the y-boundaries
                    if block_y1 > start_y and block_y0 < end_y:
                        block_text_parts = []
                        for line in block.get("lines", []):
                            line_text = "".join(span["text"] for span in line.get("spans", []))
                            block_text_parts.append(line_text)
                        
                        if block_text_parts:
                            page_content.append(" ".join(block_text_parts))

            if page_content:
                content_parts.append("\n".join(page_content))

        return "\n".join(content_parts).strip()

    def close(self) -> None:
        """Close the PDF file and clean up resources."""
        if self.doc:
            self.doc.close()
            self.doc = None
            self._document_loaded = False
