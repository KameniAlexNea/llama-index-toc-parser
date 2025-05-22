import importlib.util
import logging
import os
from enum import Enum
from typing import List, Optional, Set, Union

from llama_index.core.schema import TextNode

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


def download_file_from_url(url: str, suffix: str = None) -> str:
    """
    Download a file from a URL and save it to a temporary file.

    Args:
        url: The URL of the file to download
        suffix: Optional file extension with dot (e.g., ".docx", ".pdf")

    Returns:
        Path to the downloaded temporary file

    Note: This function is deprecated, use utils.download_temp_file instead
    """
    logger.warning("download_file_from_url is deprecated. Use utils.download_temp_file instead.")
    from .utils import download_temp_file
    return download_temp_file(url, suffix)


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


def chunk_document_by_toc_to_text_nodes(
    source: str,
    is_url: bool = None,
    format_type: Optional[Union[DocumentFormat, str]] = None,
) -> List[TextNode]:
    """
    Create a TOC-based hierarchical chunking of a document and return TextNode objects.

    Args:
        source: Path to the document file or URL, or content text
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        format_type: Document format to use (PDF by default if not specified)

    Returns:
        A list of TextNode objects representing the document chunks.

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
    source_name_for_metadata = source  # Original source name for metadata

    try:
        if is_url is None:
            is_url = source.startswith(("http://", "https://", "ftp://"))

        # Handle specific formats
        if format_type == DocumentFormat.MARKDOWN:
            # For markdown, source can be either a file path or the markdown text itself
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to a markdown file
                markdown_text = read_file_content(source)
            else:
                # It's the markdown text itself
                markdown_text = source
                source_name_for_metadata = "markdown_text"  # Default name

            MarkdownTOCChunker = _import_chunker_class(DocumentFormat.MARKDOWN)
            with MarkdownTOCChunker(markdown_text, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DocumentFormat.HTML:
            # HTML handling
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to an HTML file
                html_content = read_file_content(source)
            elif is_url:
                # Download HTML content from URL
                import requests
                response = requests.get(source, timeout=30)
                response.raise_for_status()
                html_content = response.text
                source_name_for_metadata = source  # Use URL as source name
            else:
                # It's the HTML content itself
                html_content = source
                source_name_for_metadata = "html_content"  # Default name

            HTMLTOCChunker = _import_chunker_class(DocumentFormat.HTML)
            with HTMLTOCChunker(html_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DocumentFormat.DOCX:
            # Word document handling
            if is_url:
                logger.info(f"Downloading Word document from URL: {source}")
                from .utils import download_temp_file
                temp_file_path = download_temp_file(source, suffix=".docx")
                actual_source_path = temp_file_path

            DOCXTOCChunker = _import_chunker_class(DocumentFormat.DOCX)
            with DOCXTOCChunker(
                docx_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DocumentFormat.JUPYTER:
            # Jupyter notebook handling
            if is_url:
                logger.info(f"Downloading Jupyter notebook from URL: {source}")
                from .utils import download_temp_file
                temp_file_path = download_temp_file(source, suffix=".ipynb")
                actual_source_path = temp_file_path

            JupyterNotebookTOCChunker = _import_chunker_class(DocumentFormat.JUPYTER)
            with JupyterNotebookTOCChunker(
                notebook_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DocumentFormat.RST:
            # reStructuredText handling
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to an RST file
                rst_content = read_file_content(source)
            elif is_url:
                # Download RST content from URL
                import requests
                response = requests.get(source, timeout=30)
                response.raise_for_status()
                rst_content = response.text
                source_name_for_metadata = source  # Use URL as source name
            else:
                # It's the RST content itself
                rst_content = source
                source_name_for_metadata = "rst_content"  # Default name

            RSTTOCChunker = _import_chunker_class(DocumentFormat.RST)
            with RSTTOCChunker(rst_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DocumentFormat.PDF:
            # PDF handling
            if is_url:
                logger.info(f"Downloading PDF from URL: {source}")
                from .utils import download_temp_file
                temp_file_path = download_temp_file(source, suffix=".pdf")
                actual_source_path = temp_file_path

            PDFTOCChunker = _import_chunker_class(DocumentFormat.PDF)
            with PDFTOCChunker(
                pdf_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {str(e)}")
