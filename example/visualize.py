import os
from typing import Set

from node_chunker.data_model import DocumentGraph, DocumentNode


def visualize_document_graph_to_markdown(document_graph: DocumentGraph, output_md_path: str):
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

    def _write_graph_node_recursive(node_id: str, md_file, processed_node_ids: Set[str]):
        """Recursively write a DocumentNode and its children to the Markdown file."""
        if node_id in processed_node_ids:
            return
        processed_node_ids.add(node_id)

        node = document_graph.get_node(node_id)
        if not node:
            return

        title = node.title or f"Untitled Node {node_id[:8]}"

        # Use level directly for Markdown heading (level 1 -> H1, level 2 -> H2, etc.)
        markdown_heading_level = node.level
        if markdown_heading_level <= 0:  # Ensure positive heading level
            markdown_heading_level = 1
        if markdown_heading_level > 6:  # Cap at H6
            markdown_heading_level = 6

        # Skip Document Root heading if it has no content
        if not (node.title == "Document Root" and not node.content.strip()):
            md_file.write(f"{'#' * markdown_heading_level} {title}\n\n")

        # Add metadata if available
        metadata_parts = []
        if hasattr(node, 'page_num') and node.page_num >= 0:
            if node.end_page is not None and node.end_page > node.page_num:
                metadata_parts.append(f"Page(s): {node.page_num + 1}-{node.end_page + 1}")
            else:
                metadata_parts.append(f"Page: {node.page_num + 1}")
        
        if metadata_parts:
            md_file.write("> Metadata: " + " | ".join(metadata_parts) + "\n\n")

        # Write node content
        if node.content and node.content.strip():
            md_file.write(node.content + "\n\n")

        # Process children in order
        children = document_graph.get_children(node_id)
        if children:
            # Sort children by page number and title
            sorted_children = sorted(
                children, 
                key=lambda child: (child.page_num, child.title)
            )
            
            for child in sorted_children:
                _write_graph_node_recursive(child.node_id, md_file, processed_node_ids)

    processed_node_ids: Set[str] = set()

    with open(output_md_path, "w", encoding="utf-8") as md_file:
        # Start from root node
        if document_graph.root_id:
            _write_graph_node_recursive(document_graph.root_id, md_file, processed_node_ids)

    print(f"DocumentGraph markdown visualization saved to {output_md_path}")


def visualize_chunker_to_markdown(chunker, output_md_path: str):
    """
    Convenience function to visualize DocumentGraph from a chunker.

    Args:
        chunker: A document chunker instance (PDFTOCChunker, MarkdownTOCChunker, etc.)
        output_md_path: The path to save the generated Markdown file
    """
    document_graph = chunker.get_document_graph()
    visualize_document_graph_to_markdown(document_graph, output_md_path)


def visualize_nodes_to_markdown(nodes: list[DocumentNode], output_md_path: str):
    """
    Visualizes a list of DocumentNode objects as a flat Markdown file.

    Args:
        nodes: A list of DocumentNode objects
        output_md_path: The path to save the generated Markdown file
    """
    if not nodes:
        print("No nodes to visualize.")
        with open(output_md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Document Content\n\n")
            md_file.write("No content found in the provided nodes.\n")
        return

    with open(output_md_path, "w", encoding="utf-8") as md_file:
        for node in nodes:
            title = node.title or f"Untitled Node {node.node_id[:8]}"
            
            # Use level for heading
            markdown_heading_level = max(1, min(6, node.level))
            
            md_file.write(f"{'#' * markdown_heading_level} {title}\n\n")
            
            # Add metadata
            metadata_parts = []
            if node.page_num >= 0:
                if node.end_page is not None and node.end_page > node.page_num:
                    metadata_parts.append(f"Page(s): {node.page_num + 1}-{node.end_page + 1}")
                else:
                    metadata_parts.append(f"Page: {node.page_num + 1}")
            
            if metadata_parts:
                md_file.write("> Metadata: " + " | ".join(metadata_parts) + "\n\n")
            
            # Write content
            if node.content and node.content.strip():
                md_file.write(node.content + "\n\n")

    print(f"Nodes markdown visualization saved to {output_md_path}")


# Example Usage:
if __name__ == "__main__":
    from node_chunker.pdf_chunking import PDFTOCChunker
    from node_chunker.md_chunking import MarkdownTOCChunker
    from node_chunker.chunks import chunk_document_by_toc_to_document_graph, chunk_document_by_toc_to_nodes
    
    # Test with PDF using DocumentGraph approach
    pdf_file_path = "example/data/test.pdf"
    if os.path.exists(pdf_file_path):
        try:
            # Using the new function directly
            document_graph = chunk_document_by_toc_to_document_graph(pdf_file_path)
            visualize_document_graph_to_markdown(
                document_graph, 
                "example/ignore/pdf_graph_visualization.md"
            )
            
            # Also test with chunker directly
            with PDFTOCChunker(pdf_file_path, os.path.basename(pdf_file_path)) as chunker:
                visualize_chunker_to_markdown(
                    chunker,
                    "example/ignore/pdf_chunker_visualization.md"
                )
                
            # Test nodes visualization
            nodes = chunk_document_by_toc_to_nodes(pdf_file_path)
            visualize_nodes_to_markdown(nodes, "example/ignore/pdf_nodes_visualization.md")
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
    
    # Test with Markdown using DocumentGraph approach
    markdown_content = """# Chapter 1
This is chapter 1 content.

## Section 1.1
This is section 1.1 content.

## Section 1.2
This is section 1.2 content.

# Chapter 2
This is chapter 2 content.
"""
    
    try:
        # Using the new function directly
        document_graph = chunk_document_by_toc_to_document_graph(
            markdown_content, 
            format_type="md"
        )
        visualize_document_graph_to_markdown(
            document_graph,
            "example/ignore/markdown_graph_visualization.md"
        )
        
        # Also test getting nodes directly
        nodes = chunk_document_by_toc_to_nodes(markdown_content, format_type="md")
        print(f"Found {len(nodes)} nodes in markdown content")
        visualize_nodes_to_markdown(nodes, "example/ignore/markdown_nodes_visualization.md")
        
    except Exception as e:
        print(f"Error processing Markdown: {e}")

    # Test creating DocumentGraph manually
    test_graph = DocumentGraph("Test Document")
    
    # Add some test nodes
    chap1_id = test_graph.add_node("Chapter 1", "This is chapter 1 content.", level=1, page_num=0)
    test_graph.add_child(test_graph.root_id, chap1_id)
    
    sec1_id = test_graph.add_node("Section 1.1", "This is section 1.1 content.", level=2, page_num=1)
    test_graph.add_child(chap1_id, sec1_id)
    
    sec2_id = test_graph.add_node("Section 1.2", "This is section 1.2 content.", level=2, page_num=2)
    test_graph.add_child(chap1_id, sec2_id)
    
    chap2_id = test_graph.add_node("Chapter 2", "This is chapter 2 content.", level=1, page_num=3)
    test_graph.add_child(test_graph.root_id, chap2_id)
    
    visualize_document_graph_to_markdown(test_graph, "example/ignore/manual_test_graph.md")
    
    # Test pre-order traversal
    print("Pre-order traversal:")
    for node in test_graph.get_content():
        print(f"  {node.title} (Level {node.level})")
