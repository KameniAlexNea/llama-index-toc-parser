import fitz  # PyMuPDF
import requests
import tempfile
import os
from typing import List

from llama_index.core.schema import (
    TextNode,
    NodeRelationship,
)
from node_chunker.markdown_chunking import MarkdownTOCChunker
from node_chunker.pdf_chunking import PDFTOCChunker

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
        print(f"Error downloading PDF from URL: {e}")
        raise



def chunk_document_by_toc_to_text_nodes(
    source: str, is_url: bool = None, is_markdown: bool = False
) -> List[TextNode]:
    """
    Convenience function to create a TOC-based hierarchical chunking of a document
    and return it as a list of LlamaIndex TextNode objects.

    Args:
        source: Path to the document file or URL, or markdown text content
        is_url: Force URL interpretation if True, file path if False, or auto-detect if None
        is_markdown: Whether the source is markdown text (True) or a PDF file/URL (False)

    Returns:
        A list of TextNode objects representing the document chunks.
    """
    temp_file_path = None
    actual_source_path = source
    source_name_for_metadata = source  # Original source name for metadata

    try:
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
        else:
            # PDF handling
            if is_url is None:
                is_url = source.startswith(("http://", "https://", "ftp://"))

            if is_url:
                print(f"Downloading PDF from URL: {source}")
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


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        source_path_or_url = sys.argv[1]

        is_url_check = source_path_or_url.startswith(("http://", "https://", "ftp://"))
        if is_url_check:
            print(f"Processing PDF from URL: {source_path_or_url}")
        else:
            print(f"Processing local PDF: {source_path_or_url}")

        text_nodes = chunk_document_by_toc_to_text_nodes(
            source_path_or_url
        )  # Updated function call

        print(f"\nGenerated {len(text_nodes)} TextNode(s):")
        for i, tn in enumerate(text_nodes):
            print(f"\n--- TextNode {i+1} ---")
            print(f"ID: {tn.id_}")
            text_snippet = (
                (tn.text[:150] + "...") if tn.text and len(tn.text) > 150 else tn.text
            )
            print(f"Text snippet: {text_snippet if text_snippet else 'None'}")
            print(f"Metadata: {tn.metadata}")
            # print(f"Relationships: {tn.relationships}") # Can be verbose

            # Print relationship summary
            rel_summary = {}
            if NodeRelationship.SOURCE in tn.relationships:
                rel_summary["SOURCE"] = tn.relationships[
                    NodeRelationship.SOURCE
                ].node_id
            if NodeRelationship.PARENT in tn.relationships:
                rel_summary["PARENT"] = tn.relationships[
                    NodeRelationship.PARENT
                ].node_id
            if NodeRelationship.CHILD in tn.relationships:
                rel_summary["CHILDREN"] = [
                    r.node_id for r in tn.relationships[NodeRelationship.CHILD]
                ]
            print(f"Relationships Summary: {rel_summary}")

            if i >= 4 and len(text_nodes) > 5:  # Print first few and stop if too many
                print(f"\n... and {len(text_nodes) - (i+1)} more TextNode(s).")
                break
    else:
        print("Please provide a PDF file path or URL as an argument.")
