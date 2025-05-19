import logging
import os
import tempfile
from typing import List

import requests
from llama_index.core.schema import TextNode

from node_chunker.docx_chunking import DOCXTOCChunker
from node_chunker.html_chunking import HTMLTOCChunker
from node_chunker.jupyter_chunking import JupyterNotebookTOCChunker
from node_chunker.md_chunking import MarkdownTOCChunker
from node_chunker.pdf_chunking import PDFTOCChunker
from node_chunker.rst_chunking import RSTTOCChunker

# Get logger for this module
logger = logging.getLogger(__name__)


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


def chunk_document_by_toc_to_text_nodes(
    source: str,
    is_url: bool = None,
    is_markdown: bool = False,
    is_html: bool = False,
    is_docx: bool = False,
    is_jupyter: bool = False,
    is_rst: bool = False,
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

    Returns:
        A list of TextNode objects representing the document chunks.
    """
    temp_file_path = None
    actual_source_path = source
    source_name_for_metadata = source  # Original source name for metadata

    try:
        if is_url is None:
            is_url = source.startswith(("http://", "https://", "ftp://"))

        if is_markdown:
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

            with MarkdownTOCChunker(markdown_text, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()
        elif is_html:
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

            with HTMLTOCChunker(html_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()
        elif is_docx:
            # Word document handling
            if is_url:
                logger.info(f"Downloading Word document from URL: {source}")
                temp_file_path = download_file_from_url(source, suffix=".docx")
                actual_source_path = temp_file_path

            with DOCXTOCChunker(
                docx_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()
        elif is_jupyter:
            # Jupyter notebook handling
            if is_url:
                logger.info(f"Downloading Jupyter notebook from URL: {source}")
                temp_file_path = download_file_from_url(source, suffix=".ipynb")
                actual_source_path = temp_file_path

            with JupyterNotebookTOCChunker(
                notebook_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()
        elif is_rst:
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

            with RSTTOCChunker(rst_content, source_name_for_metadata) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()
        else:
            # Default to PDF handling
            if is_url:
                logger.info(f"Downloading PDF from URL: {source}")
                temp_file_path = download_pdf_from_url(source)
                actual_source_path = temp_file_path

            with PDFTOCChunker(
                pdf_path=actual_source_path,
                source_display_name=source_name_for_metadata,
            ) as chunker:
                chunker.build_toc_tree()
                return chunker.get_text_nodes()

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
