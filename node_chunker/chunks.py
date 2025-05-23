import importlib.util
import logging
import os
from enum import Enum
from typing import List, Optional, Set, Union

from .data_model import DocumentGraph, DocumentNode
from .utils import download_temp_file, read_file_content

# Get logger for this module
logger = logging.getLogger(__name__)


# Define document format enum
class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "md"
    JUPYTER = "jupyter"
    RST = "rst"

    @classmethod
    def from_extension(cls, filename: str) -> Optional["DocumentFormat"]:
        """Determine format from file extension"""
        if filename.lower().endswith(".pdf"):
            return cls.PDF
        elif filename.lower().endswith((".docx", ".doc")):
            return cls.DOCX
        elif filename.lower().endswith((".html", ".htm")):
            return cls.HTML
        elif filename.lower().endswith((".md", ".markdown")):
            return cls.MARKDOWN
        elif filename.lower().endswith(".ipynb"):
            return cls.JUPYTER
        elif filename.lower().endswith(".rst"):
            return cls.RST
        return None


def _check_format_supported(format_type: DocumentFormat) -> bool:
    """
    Check if the required dependencies for a specific format are installed.

    Args:
        format_type: The document format to check

    Returns:
        True if dependencies are available, False otherwise
    """
    if format_type == DocumentFormat.PDF:
        return importlib.util.find_spec("fitz") is not None
    elif format_type == DocumentFormat.DOCX:
        return importlib.util.find_spec("docx") is not None
    elif format_type == DocumentFormat.HTML:
        return importlib.util.find_spec("bs4") is not None
    elif format_type == DocumentFormat.MARKDOWN:
        return True  # Markdown has no special dependencies
    elif format_type == DocumentFormat.JUPYTER:
        return importlib.util.find_spec("nbformat") is not None
    elif format_type == DocumentFormat.RST:
        return importlib.util.find_spec("docutils") is not None
    else:
        return False


def get_supported_formats() -> Set[DocumentFormat]:
    """
    Get all currently supported document formats based on installed dependencies.

    Returns:
        Set of supported format identifiers
    """
    supported = set()
    for format_type in DocumentFormat:
        if _check_format_supported(format_type):
            supported.add(format_type)
    return supported


def _import_chunker_class(format_type: DocumentFormat):
    """
    Dynamically import a chunker class based on format type.

    Args:
        format_type: Document format type

    Returns:
        The chunker class, or None if not available
    """
    try:
        if format_type == DocumentFormat.PDF:
            from node_chunker.pdf_chunking import PDFTOCChunker

            return PDFTOCChunker
        elif format_type == DocumentFormat.DOCX:
            from node_chunker.docx_chunking import DOCXTOCChunker

            return DOCXTOCChunker
        elif format_type == DocumentFormat.HTML:
            from node_chunker.html_chunking import HTMLTOCChunker

            return HTMLTOCChunker
        elif format_type == DocumentFormat.MARKDOWN:
            from node_chunker.md_chunking import MarkdownTOCChunker

            return MarkdownTOCChunker
        elif format_type == DocumentFormat.JUPYTER:
            from node_chunker.jupyter_chunking import JupyterNotebookTOCChunker

            return JupyterNotebookTOCChunker
        elif format_type == DocumentFormat.RST:
            from node_chunker.rst_chunking import RSTTOCChunker

            return RSTTOCChunker
    except ImportError as e:
        logger.warning(f"Failed to import chunker for {format_type}: {e}")
        return None


def chunk_document_by_toc_to_nodes(
    source: str,
    is_url: bool = None,
    format_type: Optional[Union[DocumentFormat, str]] = None,
) -> List[DocumentNode]:
    """
    Create a TOC-based hierarchical chunking of a document and return DocumentNode objects.

    Args:
        source: Path to the document file or URL, or content text
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        format_type: Document format to use (PDF by default if not specified)

    Returns:
        A list of DocumentNode objects representing the document chunks in pre-order.

    Raises:
        ValueError: If the format is unsupported or document processing fails
        ImportError: If required dependencies are missing
    """
    document_graph = chunk_document_by_toc_to_document_graph(source, is_url, format_type)
    return list(document_graph.get_content())


def chunk_document_by_toc_to_text_nodes(
    source: str,
    is_url: bool = None,
    format_type: Optional[Union[DocumentFormat, str]] = None,
):
    """
    Legacy function for backward compatibility with LlamaIndex TextNode format.
    
    Args:
        source: Path to the document file or URL, or content text
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        format_type: Document format to use (PDF by default if not specified)

    Returns:
        A list of TextNode objects representing the document chunks.
    """
    # Import TextNode only when needed for backward compatibility
    from llama_index.core.schema import TextNode
    
    # Get the document graph and convert to TextNodes via chunker
    document_graph = chunk_document_by_toc_to_document_graph(source, is_url, format_type)
    
    # Use the chunker's get_text_nodes method for proper conversion
    if format_type == DocumentFormat.MARKDOWN or (format_type is None and source.endswith(('.md', '.markdown'))):
        MarkdownTOCChunker = _import_chunker_class(DocumentFormat.MARKDOWN)
        is_file_path = os.path.exists(source) and not (is_url or source.startswith(("http://", "https://", "ftp://")))
        
        if is_file_path:
            markdown_text = read_file_content(source)
            source_name = source
        else:
            markdown_text = source
            source_name = "markdown_text"
            
        with MarkdownTOCChunker(markdown_text, source_name) as chunker:
            return chunker.get_text_nodes()
    
    elif format_type == DocumentFormat.PDF or (format_type is None and source.endswith('.pdf')):
        PDFTOCChunker = _import_chunker_class(DocumentFormat.PDF)
        temp_file_path = None
        actual_source_path = source
        
        try:
            if is_url or source.startswith(("http://", "https://", "ftp://")):
                temp_file_path = download_temp_file(source, suffix=".pdf")
                actual_source_path = temp_file_path
            
            with PDFTOCChunker(actual_source_path, source) as chunker:
                return chunker.get_text_nodes()
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_file_path}: {e}")
    
    else:
        raise ValueError(f"TextNode conversion not yet implemented for format: {format_type}")


def chunk_document_by_toc_to_document_graph(
    source: str,
    is_url: bool = None,
    format_type: Optional[Union[DocumentFormat, str]] = None,
) -> DocumentGraph:
    """
    Create a TOC-based hierarchical chunking of a document and return DocumentGraph.

    Args:
        source: Path to the document file or URL, or content text
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        format_type: Document format to use (PDF by default if not specified)

    Returns:
        A DocumentGraph object representing the document structure.

    Raises:
        ValueError: If the format is unsupported or document processing fails
        ImportError: If required dependencies are missing
    """
    # Try to auto-detect format from file extension if not specified
    if format_type is None:
        detected_format = DocumentFormat.from_extension(source)
        format_type = detected_format if detected_format else DocumentFormat.PDF

    # Ensure format_type is a DocumentFormat enum
    if isinstance(format_type, str):
        try:
            format_type = DocumentFormat(format_type)
        except ValueError:
            raise ValueError(f"Unknown format type: {format_type}")

    # Check if the format is supported
    if not _check_format_supported(format_type):
        available = get_supported_formats()
        raise ImportError(
            f"Format {format_type} is not supported (missing dependencies). "
            f"Available formats: {available}"
        )

    temp_file_path = None
    actual_source_path = source
    source_name_for_metadata = source

    try:
        if is_url is None:
            is_url = source.startswith(("http://", "https://", "ftp://"))

        # Handle specific formats
        if format_type == DocumentFormat.MARKDOWN:
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                markdown_text = read_file_content(source)
            else:
                markdown_text = source
                source_name_for_metadata = "markdown_text"

            MarkdownTOCChunker = _import_chunker_class(DocumentFormat.MARKDOWN)
            with MarkdownTOCChunker(markdown_text, source_name_for_metadata) as chunker:
                return chunker.get_document_graph()

        elif format_type == DocumentFormat.PDF:
            if is_url:
                logger.info(f"Downloading PDF from URL: {source}")
                temp_file_path = download_temp_file(source, suffix=".pdf")
                actual_source_path = temp_file_path

            PDFTOCChunker = _import_chunker_class(DocumentFormat.PDF)
            with PDFTOCChunker(
                pdf_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                return chunker.get_document_graph()

        else:
            raise ValueError(f"DocumentGraph support not yet implemented for format: {format_type}")

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {e}")
