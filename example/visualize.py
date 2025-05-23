import os
from typing import Set

from node_chunker.data_model import DocumentGraph


def visualize_document_to_markdown(document_graph: DocumentGraph, output_md_path: str):
    """
    Visualizes a DocumentGraph as a hierarchical Markdown file.

    Args:
        document_graph: A DocumentGraph object from the document chunker
        output_md_path: The path to save the generated Markdown file
    """
    if not document_graph.nodes:
        print("No nodes in document graph to visualize.")
        with open(output_md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Document Content\n\n")
            md_file.write("No content found in the DocumentGraph.\n")
        return

    def _write_node_recursive(node_id: str, md_file, processed_node_ids: Set[str]):
        """Recursively write a DocumentNode and its children to the Markdown file."""
        if node_id in processed_node_ids:
            return
        processed_node_ids.add(node_id)

        node = document_graph.get_node(node_id)
        if not node:
            return

        title = node.title or f"Untitled Node {node_id[:8]}"

        # Use level directly for Markdown heading
        markdown_heading_level = max(1, min(6, node.level))

        # Skip Document Root heading if it has no content
        if not (node.title == "Document Root" and not node.content.strip()):
            md_file.write(f"{'#' * markdown_heading_level} {title}\n\n")

        # Add metadata if available
        if node.page_num >= 0:
            if node.end_page is not None and node.end_page > node.page_num:
                md_file.write(f"> Page(s): {node.page_num + 1}-{node.end_page + 1}\n\n")
            else:
                md_file.write(f"> Page: {node.page_num + 1}\n\n")

        # Write node content
        if node.content and node.content.strip():
            md_file.write(node.content + "\n\n")

        # Process children in order
        children = document_graph.get_children(node_id)
        if children:
            sorted_children = sorted(children, key=lambda child: (child.page_num, child.title))
            for child in sorted_children:
                _write_node_recursive(child.node_id, md_file, processed_node_ids)

    processed_node_ids: Set[str] = set()

    with open(output_md_path, "w", encoding="utf-8") as md_file:
        if document_graph.root_id:
            _write_node_recursive(document_graph.root_id, md_file, processed_node_ids)

    print(f"Document saved as parsed to {output_md_path}")


# Example Usage:
if __name__ == "__main__":
    from node_chunker.chunks import chunk_document_by_toc_to_document_graph
    
    # Test with PDF
    pdf_file_path = "example/data/test_markdown.pdf"
    if os.path.exists(pdf_file_path):
        try:
            document_graph = chunk_document_by_toc_to_document_graph(pdf_file_path)
            visualize_document_to_markdown(document_graph, "example/ignore/result.md")
        except Exception as e:
            print(f"Error processing PDF: {e}")
    
    # Test with Markdown
    markdown_content = """# Chapter 1
This is chapter 1 content.

## Section 1.1
This is section 1.1 content.

# Chapter 2
This is chapter 2 content.
"""
    
    try:
        document_graph = chunk_document_by_toc_to_document_graph(markdown_content, format_type="md")
        visualize_document_to_markdown(document_graph, "example/ignore/parsed.md")
    except Exception as e:
        print(f"Error processing Markdown: {e}")
