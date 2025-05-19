import importlib.util
import logging
import os
import tempfile
from typing import List, Optional, Set, Union

import requests
from llama_index.core.schema import TextNode

# Get logger for this module
logger = logging.getLogger(__name__)

# Define document type constants
PDF = "pdf"
DOCX = "docx"
HTML = "html"
MARKDOWN = "md"
JUPYTER = "jupyter"
RST = "rst"
ALL = "all"


def _check_format_supported(format_type: str) -> bool:
    """
    Check if the required dependencies for a specific format are installed.

    Args:
        format_type: The document format to check

    Returns:
        True if dependencies are available, False otherwise
    """
    if format_type == PDF:
        return importlib.util.find_spec("fitz") is not None
    elif format_type == DOCX:
        return importlib.util.find_spec("docx") is not None
    elif format_type == HTML:
        return importlib.util.find_spec("bs4") is not None
    elif format_type == MARKDOWN:
        return True  # Markdown has no special dependencies
    elif format_type == JUPYTER:
        return importlib.util.find_spec("nbformat") is not None
    elif format_type == RST:
        return importlib.util.find_spec("docutils") is not None
    else:
        return False


def get_supported_formats() -> Set[str]:
    """
    Get all currently supported document formats based on installed dependencies.

    Returns:
        Set of supported format identifiers
    """
    supported = set()
    for format_type in [PDF, DOCX, HTML, MARKDOWN, JUPYTER, RST]:
        if _check_format_supported(format_type):
            supported.add(format_type)
    return supported


def download_pdf_from_url(url: str) -> str:
    """
    Download a PDF from a URL and save it to a temporary file.

    Args:
        url: The URL of the PDF to download

    Returns:
        Path to the downloaded temporary file
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_path = temp_file.name

        # Write the content to the temporary file
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return temp_path
    except Exception as e:
        logger.error(f"Error downloading PDF from URL: {e}")
        raise


def download_file_from_url(url: str, suffix: str = None) -> str:
    """
    Download a file from a URL and save it to a temporary file.

    Args:
        url: The URL of the file to download
        suffix: Optional file extension with dot (e.g., ".docx", ".pdf")

    Returns:
        Path to the downloaded temporary file
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Create a temporary file with appropriate suffix
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name

        # Write the content to the temporary file
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return temp_path
    except Exception as e:
        logger.error(f"Error downloading file from URL: {e}")
        raise


def _import_chunker_class(format_type: str):
    """
    Dynamically import a chunker class based on format type.

    Args:
        format_type: Document format type

    Returns:
        The chunker class, or None if not available
    """
    try:
        if format_type == PDF:
            from node_chunker.pdf_chunking import PDFTOCChunker

            return PDFTOCChunker
        elif format_type == DOCX:
            from node_chunker.docx_chunking import DOCXTOCChunker

            return DOCXTOCChunker
        elif format_type == HTML:
            from node_chunker.html_chunking import HTMLTOCChunker

            return HTMLTOCChunker
        elif format_type == MARKDOWN:
            from node_chunker.md_chunking import MarkdownTOCChunker

            return MarkdownTOCChunker
        elif format_type == JUPYTER:
            from node_chunker.jupyter_chunking import JupyterNotebookTOCChunker

            return JupyterNotebookTOCChunker
        elif format_type == RST:
            from node_chunker.rst_chunking import RSTTOCChunker

            return RSTTOCChunker
    except ImportError as e:
        logger.warning(f"Failed to import chunker for {format_type}: {e}")
        return None


def chunk_document_by_toc_to_text_nodes(
    source: str,
    is_url: bool = None,
    is_markdown: bool = False,
    is_html: bool = False,
    is_docx: bool = False,
    is_jupyter: bool = False,
    is_rst: bool = False,
    format_type: Optional[str] = None,
    supported_formats: Union[str, List[str]] = ALL,
) -> List[TextNode]:
    """
    Convenience function to create a TOC-based hierarchical chunking of a document
    and return it as a list of LlamaIndex TextNode objects.

    Args:
        source: Path to the document file or URL, or content text
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        is_markdown: Whether the source is markdown text
        is_html: Whether the source is HTML content
        is_docx: Whether the source is a Word document
        is_jupyter: Whether the source is a Jupyter notebook
        is_rst: Whether the source is a reStructuredText document
        format_type: Explicitly specify the format type (overrides boolean flags)
        supported_formats: Which formats to support, either 'all' or a list like ['pdf', 'md']

    Returns:
        A list of TextNode objects representing the document chunks.
    """
    # Determine which formats to support
    if supported_formats == ALL:
        enabled_formats = get_supported_formats()
    else:
        if isinstance(supported_formats, str):
            supported_formats = [supported_formats]
        enabled_formats = {
            fmt for fmt in supported_formats if _check_format_supported(fmt)
        }
        if not enabled_formats:
            raise ValueError(
                f"None of the specified formats {supported_formats} are supported. "
                f"Make sure required dependencies are installed."
            )

    # Convert legacy boolean flags to format_type if not explicitly provided
    if format_type is None:
        if is_markdown:
            format_type = MARKDOWN
        elif is_html:
            format_type = HTML
        elif is_docx:
            format_type = DOCX
        elif is_jupyter:
            format_type = JUPYTER
        elif is_rst:
            format_type = RST
        else:
            # Try to auto-detect format from file extension
            if source.lower().endswith(".pdf"):
                format_type = PDF
            elif source.lower().endswith((".docx", ".doc")):
                format_type = DOCX
            elif source.lower().endswith((".html", ".htm")):
                format_type = HTML
            elif source.lower().endswith((".md", ".markdown")):
                format_type = MARKDOWN
            elif source.lower().endswith(".ipynb"):
                format_type = JUPYTER
            elif source.lower().endswith(".rst"):
                format_type = RST
            else:
                # Default to PDF for backward compatibility
                format_type = PDF

    # Check if the format is supported and enabled
    if format_type not in enabled_formats:
        raise ValueError(
            f"Format {format_type} is not enabled or dependencies not installed. "
            f"Available formats: {enabled_formats}"
        )

    temp_file_path = None
    actual_source_path = source
    source_name_for_metadata = source  # Original source name for metadata

    try:
        if is_url is None:
            is_url = source.startswith(("http://", "https://", "ftp://"))

        # Handle specific formats
        if format_type == MARKDOWN:
            # For markdown, source can be either a file path or the markdown text itself
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to a markdown file
                with open(source, "r", encoding="utf-8") as f:
                    markdown_text = f.read()
            else:
                # It's the markdown text itself
                markdown_text = source
                source_name_for_metadata = "markdown_text"  # Default name

            MarkdownTOCChunker = _import_chunker_class(MARKDOWN)
            with MarkdownTOCChunker(markdown_text, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == HTML:
            # HTML handling
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to an HTML file
                with open(source, "r", encoding="utf-8") as f:
                    html_content = f.read()
            elif is_url:
                # Download HTML content from URL
                response = requests.get(source)
                response.raise_for_status()
                html_content = response.text
                source_name_for_metadata = source  # Use URL as source name
            else:
                # It's the HTML content itself
                html_content = source
                source_name_for_metadata = "html_content"  # Default name

            HTMLTOCChunker = _import_chunker_class(HTML)
            with HTMLTOCChunker(html_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == DOCX:
            # Word document handling
            if is_url:
                logger.info(f"Downloading Word document from URL: {source}")
                temp_file_path = download_file_from_url(source, suffix=".docx")
                actual_source_path = temp_file_path

            DOCXTOCChunker = _import_chunker_class(DOCX)
            with DOCXTOCChunker(
                docx_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == JUPYTER:
            # Jupyter notebook handling
            if is_url:
                logger.info(f"Downloading Jupyter notebook from URL: {source}")
                temp_file_path = download_file_from_url(source, suffix=".ipynb")
                actual_source_path = temp_file_path

            JupyterNotebookTOCChunker = _import_chunker_class(JUPYTER)
            with JupyterNotebookTOCChunker(
                notebook_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == RST:
            # reStructuredText handling
            is_file_path = os.path.exists(source) and not is_url

            if is_file_path:
                # It's a file path to an RST file
                with open(source, "r", encoding="utf-8") as f:
                    rst_content = f.read()
            elif is_url:
                # Download RST content from URL
                response = requests.get(source)
                response.raise_for_status()
                rst_content = response.text
                source_name_for_metadata = source  # Use URL as source name
            else:
                # It's the RST content itself
                rst_content = source
                source_name_for_metadata = "rst_content"  # Default name

            RSTTOCChunker = _import_chunker_class(RST)
            with RSTTOCChunker(rst_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

        elif format_type == PDF:
            # Default to PDF handling
            if is_url:
                logger.info(f"Downloading PDF from URL: {source}")
                temp_file_path = download_pdf_from_url(source)
                actual_source_path = temp_file_path

            PDFTOCChunker = _import_chunker_class(PDF)
            with PDFTOCChunker(
                pdf_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
