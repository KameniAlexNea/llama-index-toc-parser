import logging
import os
import tempfile

from markitdown import MarkItDown

from .document_chunking import BaseDocumentChunker, TOCNode
from .md_chunking import MarkdownTOCChunker

logger = logging.getLogger(__name__)


class HTMLTOCChunker(BaseDocumentChunker):
    """
    A document chunker that converts HTML to Markdown using MarkItDown and then
    creates a hierarchical tree of nodes based on Markdown headings.
    """

    def __init__(self, html_content: str, source_display_name: str):
        """
        Initialize the chunker with HTML content.

        Args:
            html_content: The HTML content as a string
            source_display_name: The original name of the source (e.g., URL or filename)
        """
        super().__init__(
            source_path=source_display_name, source_display_name=source_display_name
        )
        self.html_content = html_content
        self.markdown_content = None
        self._document_loaded = False

    def load_document(self) -> None:
        """Load the HTML string, convert it to Markdown using MarkItDown."""
        md_converter = MarkItDown(enable_plugins=False)
        temp_file_path = None

        try:
            # MarkItDown expects a file path, so save html_content to a temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".html", encoding="utf-8"
            ) as tmp_file:
                tmp_file.write(self.html_content)
                temp_file_path = tmp_file.name

            result = md_converter.convert(temp_file_path)
            self.markdown_content = result.text_content
            self._document_loaded = True

        except Exception as e:
            logger.error(f"Error converting HTML to Markdown: {e}")
            raise
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the converted Markdown content.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        if self.markdown_content is None:
            logger.error("Markdown content is not available after load_document.")
            # Return a basic root node if conversion failed
            self.root_node = TOCNode(
                title="Document Root", page_num=0, level=0, content=""
            )
            return self.root_node

        # Use MarkdownTOCChunker to process the converted content
        md_chunker = MarkdownTOCChunker(
            markdown_text=self.markdown_content,
            source_display_name=self.source_display_name,
        )
        self.root_node = md_chunker.build_toc_tree()

        return self.root_node

    def close(self) -> None:
        """Clean up resources"""
        self.markdown_content = None
        self._document_loaded = False
