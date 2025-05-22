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
from .document_chunking import BaseDocumentChunker, TOCNode
from .md_chunking import MarkdownTOCChunker
from .pdf_chunking import PDFTOCChunker
from .docx_chunking import DOCXTOCChunker
from .html_chunking import HTMLTOCChunker
from .jupyter_chunking import JupyterNotebookTOCChunker
from .rst_chunking import RSTTOCChunker

__all__ = [
    "BaseDocumentChunker",
    "TOCNode",
    "DocumentFormat",
    "chunk_document_by_toc_to_text_nodes",
    "get_supported_formats",
    "MarkdownTOCChunker",
    "PDFTOCChunker",
    "DOCXTOCChunker",
    "HTMLTOCChunker",
    "JupyterNotebookTOCChunker",
    "RSTTOCChunker",
]
