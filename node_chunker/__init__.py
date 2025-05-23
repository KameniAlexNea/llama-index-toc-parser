"""
Node Chunker package for extracting document structure using Table of Contents.

This package provides tools to chunk documents into hierarchical nodes based on
their table of contents or heading structure.
"""

from .chunks import (
    DocumentFormat,
    chunk_document_by_toc_to_text_nodes,
    get_supported_formats,
)
from .document_chunking import BaseDocumentChunker
from .docx_chunking import DOCXTOCChunker
from .html_chunking import HTMLTOCChunker
from .jupyter_chunking import JupyterNotebookTOCChunker
from .md_chunking import MarkdownTOCChunker
from .pdf_chunking import PDFTOCChunker
from .rst_chunking import RSTTOCChunker

__all__ = [
    "BaseDocumentChunker",
    "DOCXTOCChunker",
    "DocumentFormat",
    "HTMLTOCChunker",
    "JupyterNotebookTOCChunker",
    "MarkdownTOCChunker",
    "PDFTOCChunker",
    "RSTTOCChunker",
    "chunk_document_by_toc_to_text_nodes",
    "get_supported_formats",
]
