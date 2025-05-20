"""Example script to demonstrate the usage of the chunk_document_by_toc_to_text_nodes function.
This script takes a file path, URL, or raw content as input and processes it to generate text nodes based on the document's structure.

Examples:
python example/main.py --source example/document.pdf
python example/main.py --source example/document.md --format md
python example/main.py --source https://example.com/document.html --format html
python example/main.py --source example/notebook.ipynb --format jupyter
"""

import argparse
import logging
import sys
from typing import List, Optional

from llama_index.core.schema import NodeRelationship, TextNode

from node_chunker.chunks import (
    DocumentFormat,
    chunk_document_by_toc_to_text_nodes,
    get_supported_formats,
)

# Set up logging
logger = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="Chunk documents using header/TOC-based hierarchical chunking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python example/main.py --source example/test_markdown.pdf
  python example/main.py --source example/test_markdown.md --format md
  python example/main.py --source https://example.com/document.html --format html
  python example/main.py --source document.docx --format docx
  python example/main.py --source notebook.ipynb --format jupyter
  python example/main.py --source example/test_markdown.rst --format rst
  python example/main.py --source document --format pdf
        """,
    )

    parser.add_argument(
        "--source", default="example/test_markdown.pdf", required=False, help="Path to file, URL, or raw text content"
    )

    # Format specification
    format_group = parser.add_argument_group("Format Options")
    format_group.add_argument(
        "--format",
        choices=[f.value for f in DocumentFormat],
        help="Explicitly specify the document format",
    )

    format_group.add_argument(
        "--list-formats",
        action="store_true",
        help="List available document format types with current dependencies",
    )

    # URL handling
    parser.add_argument(
        "--url",
        action="store_true",
        help="Force interpret source as URL (auto-detected by default)",
    )

    # Output control
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed information including full text content",
    )
    output_group.add_argument(
        "--max-nodes",
        type=int,
        default=None,
        help="Maximum number of nodes to display (default: all)",
    )
    output_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )

    return parser


def display_text_nodes(
    text_nodes: List[TextNode], verbose: bool = False, max_nodes: Optional[int] = None
) -> None:
    """Display text nodes in a user-friendly format"""
    logger.info(f"\nGenerated {len(text_nodes)} TextNode(s):")

    # Determine how many nodes to display
    display_count = len(text_nodes)
    if max_nodes is not None and max_nodes < display_count:
        display_count = max_nodes

    for i, tn in enumerate(text_nodes[:display_count]):
        logger.info(f"\n--- TextNode {i + 1} ---")
        logger.info(f"ID: {tn.id_}")

        if verbose:
            logger.info(f"Text: {tn.text}")
        else:
            text_snippet = (
                (tn.text[:150] + "...") if tn.text and len(tn.text) > 150 else tn.text
            )
            logger.info(f"Text snippet: {text_snippet if text_snippet else 'None'}")

        logger.info(f"Metadata: {tn.metadata}")

        # Print relationship summary
        rel_summary = {}
        if NodeRelationship.SOURCE in tn.relationships:
            rel_summary["SOURCE"] = tn.relationships[NodeRelationship.SOURCE].node_id
        if NodeRelationship.PARENT in tn.relationships:
            rel_summary["PARENT"] = tn.relationships[NodeRelationship.PARENT].node_id
        if NodeRelationship.CHILD in tn.relationships:
            rel_summary["CHILDREN"] = [
                r.node_id for r in tn.relationships[NodeRelationship.CHILD]
            ]
        logger.info(f"Relationships Summary: {rel_summary}")

    if display_count < len(text_nodes):
        logger.info(
            f"\n... and {len(text_nodes) - display_count} more TextNode(s) not shown."
        )


def main():
    """Main function to process documents and display result nodes"""
    parser = get_parser()
    args = parser.parse_args()

    # Configure logging based on arguments
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Just list available formats and exit
    if args.list_formats:
        available_formats = get_supported_formats()
        logger.info("Available document formats (with current dependencies):")
        for fmt in DocumentFormat:
            status = (
                "✓ Available" if fmt in available_formats else "✗ Missing dependencies"
            )
            logger.info(f"  - {fmt.value}: {status}")
        return 0

    # Process the document
    try:
        logger.info(f"Processing document: {args.source}")

        # Handle format specification
        format_type = args.format

        text_nodes = chunk_document_by_toc_to_text_nodes(
            source=args.source,
            is_url=args.url,
            format_type=format_type,
        )

        # Display the generated nodes
        display_text_nodes(text_nodes, verbose=args.verbose, max_nodes=args.max_nodes)

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return 1

    return 0


# Example usage
if __name__ == "__main__":
    sys.exit(main())
