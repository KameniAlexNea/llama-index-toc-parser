import argparse

from llama_index.core.schema import NodeRelationship

from node_chunker.chunks import chunk_document_by_toc_to_text_nodes

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunk documents (PDF or Markdown) using header/TOC-based hierarchical chunking"
    )

    parser.add_argument("--source", help="Path to file, URL, or raw markdown text")

    parser.add_argument(
        "--markdown",
        "-md",
        action="store_true",
        help="Process input as Markdown (default is PDF)",
    )

    parser.add_argument(
        "--url",
        action="store_true",
        help="Force interpret source as URL (auto-detected by default)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print detailed information"
    )

    args = parser.parse_args()

    source_path_or_url = args.source
    is_url = None if not args.url else True
    is_markdown = args.markdown

    if is_markdown:
        print(f"Processing Markdown: {source_path_or_url}")
    elif is_url or source_path_or_url.startswith(("http://", "https://", "ftp://")):
        print(f"Processing PDF from URL: {source_path_or_url}")
    else:
        print(f"Processing local PDF: {source_path_or_url}")

    text_nodes = chunk_document_by_toc_to_text_nodes(
        source_path_or_url, is_url=is_url, is_markdown=is_markdown
    )

    print(f"\nGenerated {len(text_nodes)} TextNode(s):")
    for i, tn in enumerate(text_nodes):
        print(f"\n--- TextNode {i+1} ---")
        print(f"ID: {tn.id_}")

        if args.verbose:
            print(f"Text: {tn.text}")
        else:
            text_snippet = (
                (tn.text[:150] + "...") if tn.text and len(tn.text) > 150 else tn.text
            )
            print(f"Text snippet: {text_snippet if text_snippet else 'None'}")

        print(f"Metadata: {tn.metadata}")

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
        print(f"Relationships Summary: {rel_summary}")

        if (
            i >= 4 and len(text_nodes) > 5 and not args.verbose
        ):  # Print first few and stop if too many
            print(f"\n... and {len(text_nodes) - (i+1)} more TextNode(s).")
            break
