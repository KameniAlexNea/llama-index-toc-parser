import logging

from markitdown import MarkItDown

from .document_chunking import BaseDocumentChunker, TOCNode
from .md_chunking import MarkdownTOCChunker

logger = logging.getLogger(__name__)


class DOCXTOCChunker(BaseDocumentChunker):
    """
    A document chunker that converts a Word document to Markdown and then
    creates a hierarchical tree of nodes based on Markdown headings.
    """

    def __init__(self, docx_path: str, source_display_name: str):
        """
        Initialize the chunker with the path to the Word document.

        Args:
            docx_path: Path to the Word document file
            source_display_name: The original name of the source
        """
        super().__init__(source_path=docx_path, source_display_name=source_display_name)
        self.markdown_content = None
        self._document_loaded = False

    def load_document(self) -> None:
        """Load the Word document, convert it to Markdown using MarkItDown."""
        md_converter = MarkItDown(enable_plugins=False)

        try:
            # Convert DOCX to Markdown using MarkItDown
            result = md_converter.convert(self.source_path)
            self.markdown_content = result.text_content
            self._document_loaded = True

        except Exception as e:
            logger.error(f"Error converting Word document to Markdown: {e}")
            raise

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
