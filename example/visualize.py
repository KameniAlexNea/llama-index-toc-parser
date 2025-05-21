import os
from typing import Dict, List, Set

from llama_index.core.schema import (NodeRelationship, ObjectType, RelatedNodeInfo,
                                     TextNode)


def _get_node_title(node: TextNode) -> str:
    """Safely get the title of a node."""
    return node.metadata.get("title", f"Untitled Node {node.id_[:8]}")


def _get_node_level(node: TextNode) -> int:
    """Safely get the level of a node."""
    return node.metadata.get("level", 1)


def _format_node_metadata_for_markdown(node: TextNode) -> str:
    """Format selected metadata into a Markdown string."""
    parts = []
    if "page_label" in node.metadata:
        parts.append(f"Page(s): {node.metadata['page_label']}")
    if "context" in node.metadata and node.metadata["context"]:
        parts.append(f"Context: `{node.metadata['context']}`")
    
    # Example of adding more metadata if desired
    # parts.append(f"Node ID: `{node.id_}`")
    # if NodeRelationship.PARENT in node.relationships:
    #     parent_info = node.relationships[NodeRelationship.PARENT]
    #     if isinstance(parent_info, RelatedNodeInfo): # Check if it's a single RelatedNodeInfo
    #         parts.append(f"Parent ID: `{parent_info.node_id}` (Type: {parent_info.node_type})")

    if not parts:
        return ""
    return "> Metadata: " + " | ".join(parts) + "\n"


def _write_node_recursive(
    node_id: str,
    md_file,
    node_map: Dict[str, TextNode],
    children_map: Dict[str, List[str]],
    processed_node_ids: Set[str],
):
    """Recursively write a node and its children to the Markdown file."""
    if node_id in processed_node_ids:
        return
    processed_node_ids.add(node_id)

    node = node_map[node_id]
    title = _get_node_title(node)
    
    # TOCNode level 0 (Document Root) -> metadata['level'] = 0
    # TOCNode level 1 (Chapter) -> metadata['level'] = 1
    # Markdown H1 is '#'. We map TOC level 0 to H1, level 1 to H2, etc.
    markdown_heading_level = _get_node_level(node) + 1
    if markdown_heading_level <= 0: # Ensure positive heading level
        markdown_heading_level = 1
    if markdown_heading_level > 6:  # Cap at H6
        markdown_heading_level = 6
    
    md_file.write(f"{'#' * markdown_heading_level} {title}\n\n")

    metadata_md = _format_node_metadata_for_markdown(node)
    if metadata_md:
        md_file.write(metadata_md + "\n")

    if node.text and node.text.strip():
        md_file.write("```text\n")
        md_file.write(node.text.strip() + "\n")
        md_file.write("```\n\n")
    else:
        # Only print "No content" if it's not a "Document Root" node that might just be a container
        if not (title == "Document Root" and _get_node_level(node) == 0):
             md_file.write("_No specific content for this section._\n\n")
        else:
            md_file.write("\n")


    md_file.write("---\n\n")  # Separator

    if node_id in children_map and children_map[node_id]:
        child_ids = children_map[node_id]
        
        def sort_key(child_id_val):
            child_node = node_map[child_id_val]
            start_page = child_node.metadata.get("start_page_idx", -1)
            # y_pos = child_node.metadata.get("y_position", float('inf')) # Not in TextNode metadata by default
            title_key = _get_node_title(child_node)
            return (start_page, title_key) # Add y_pos here if available and desired

        sorted_child_ids = sorted(child_ids, key=sort_key)
        
        for child_id_val in sorted_child_ids:
            _write_node_recursive(child_id_val, md_file, node_map, children_map, processed_node_ids)


def visualize_text_nodes_to_markdown(text_nodes: List[TextNode], output_md_path: str):
    """
    Visualizes a list of TextNode objects as a hierarchical Markdown file.

    Args:
        text_nodes: A list of TextNode objects, typically from a document chunker.
        output_md_path: The path to save the generated Markdown file.
    """
    if not text_nodes:
        print("No text nodes to visualize.")
        with open(output_md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Document Content\n\n")
            md_file.write("No content found in the provided TextNodes.\n")
        return

    node_map: Dict[str, TextNode] = {node.id_: node for node in text_nodes}
    
    # Build children_map: parent_node_id -> list of child_node_ids
    # This relies on NodeRelationship.CHILD being correctly populated.
    children_map: Dict[str, List[str]] = {node_id: [] for node_id in node_map.keys()}
    for node_id, node in node_map.items():
        if NodeRelationship.CHILD in node.relationships:
            child_infos = node.relationships[NodeRelationship.CHILD]
            if not isinstance(child_infos, list): # Handle single child case
                child_infos = [child_infos]
            
            for child_info in child_infos:
                if child_info.node_id in node_map: # Ensure child is part of the provided list
                    children_map[node_id].append(child_info.node_id)

    # Identify root nodes: nodes whose parent is not another TextNode in the list
    root_ids: List[str] = []
    for node_id, node in node_map.items():
        is_root = True
        if NodeRelationship.PARENT in node.relationships:
            parent_info = node.relationships[NodeRelationship.PARENT]
            if isinstance(parent_info, RelatedNodeInfo): # Ensure it's a single parent
                 if parent_info.node_type == ObjectType.TEXT and parent_info.node_id in node_map:
                    is_root = False # Its parent is another TextNode in our list
        if is_root:
            root_ids.append(node_id)
            
    def root_sort_key(node_id_val):
        node = node_map[node_id_val]
        level_key = _get_node_level(node) # Prefer lower levels (e.g., Document Root) first
        start_page = node.metadata.get("start_page_idx", -1)
        title_key = _get_node_title(node)
        return (level_key, start_page, title_key)

    sorted_root_ids = sorted(root_ids, key=root_sort_key)
    
    processed_node_ids: Set[str] = set()

    with open(output_md_path, "w", encoding="utf-8") as md_file:
        main_doc_title = "Document Content Structure"
        if sorted_root_ids:
            first_root_node = node_map[sorted_root_ids[0]]
            if "file_name" in first_root_node.metadata:
                main_doc_title = f"Content of: {first_root_node.metadata['file_name']}"
        
        md_file.write(f"# {main_doc_title}\n\n")

        if not sorted_root_ids and text_nodes:
            # This case implies all nodes have a TextNode parent within the list,
            # or relationships are structured unexpectedly.
            md_file.write("Warning: Could not determine clear root nodes based on PARENT relationships. ")
            md_file.write("This might indicate a circular dependency or all nodes being children. ")
            md_file.write("Attempting to render all nodes sorted by page and title as a flat list if hierarchy fails.\n\n")
            # Fallback: render all nodes, sorted. This might not show hierarchy well.
            all_nodes_sorted_for_fallback = sorted(
                text_nodes, 
                key=lambda n: (_get_node_level(n), n.metadata.get("start_page_idx", -1), _get_node_title(n))
            )
            for node_obj in all_nodes_sorted_for_fallback:
                 if node_obj.id_ not in processed_node_ids:
                    # For this fallback, we don't have children_map readily for non-roots
                    # So, just print the node itself without recursion.
                    # This part of the fallback needs refinement if true hierarchy is lost.
                    # A better fallback might be to try to find nodes with level 0 or 1.
                    # For now, the _write_node_recursive will only print the node if its children are in children_map.
                     _write_node_recursive(node_obj.id_, md_file, node_map, children_map, processed_node_ids)

        else:
            for root_id in sorted_root_ids:
                if root_id not in processed_node_ids:
                    _write_node_recursive(root_id, md_file, node_map, children_map, processed_node_ids)

    print(f"Markdown visualization saved to {output_md_path}")


# Example Usage (commented out):
# """
from node_chunker.pdf_chunking import PDFTOCChunker # Replace with your actual chunker
#
if __name__ == "__main__":
    # This is a placeholder. You'd get text_nodes from your actual chunking process.
    # Example:
    pdf_file_path = "example/data/test_markdown.pdf"
    display_name = os.path.basename(pdf_file_path)
    
    try:
        with PDFTOCChunker(pdf_path=pdf_file_path, source_display_name=display_name) as chunker:
            text_nodes = chunker.get_text_nodes()
    
        output_markdown_file = "document_visualization.md"
        if text_nodes:
            visualize_text_nodes_to_markdown(text_nodes, output_markdown_file)
        else:
            print(f"No text nodes were generated for {display_name}.")
    
    except FileNotFoundError:
        print(f"Error: PDF file not found at {pdf_file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


    # --- Dummy TextNode creation for testing the visualizer directly ---
    doc_id = "doc_123"
    node1 = TextNode(
        id_="node_1", text="Content of Chapter 1.",
        metadata={"title": "Chapter 1", "level": 1, "page_label": "1-5", "start_page_idx": 0, "file_name": "dummy.pdf"},
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id, node_type=ObjectType.DOCUMENT),
            # NodeRelationship.PARENT: RelatedNodeInfo(node_id=doc_id, node_type=ObjectType.DOCUMENT) # Example if parent is doc
        }
    )
    node2 = TextNode(
        id_="node_2", text="Content of Section 1.1.",
        metadata={"title": "Section 1.1", "level": 2, "page_label": "2-3", "start_page_idx": 1, "file_name": "dummy.pdf", "context": "Chapter 1 > Section 1.1"},
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id, node_type=ObjectType.DOCUMENT),
            NodeRelationship.PARENT: RelatedNodeInfo(node_id="node_1", node_type=ObjectType.TEXT)
        }
    )
    node3 = TextNode(
        id_="node_3", text="Content of Section 1.2.",
        metadata={"title": "Section 1.2", "level": 2, "page_label": "4-5", "start_page_idx": 3, "file_name": "dummy.pdf", "context": "Chapter 1 > Section 1.2"},
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id, node_type=ObjectType.DOCUMENT),
            NodeRelationship.PARENT: RelatedNodeInfo(node_id="node_1", node_type=ObjectType.TEXT)
        }
    )
    node4 = TextNode(
        id_="node_4", text="Content of Chapter 2.",
        metadata={"title": "Chapter 2", "level": 1, "page_label": "6-10", "start_page_idx": 5, "file_name": "dummy.pdf"},
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id, node_type=ObjectType.DOCUMENT),
        }
    )

    # Manually set CHILD relationships for the dummy example as the chunker would
    node1.relationships[NodeRelationship.CHILD] = [
        RelatedNodeInfo(node_id="node_2", node_type=ObjectType.TEXT),
        RelatedNodeInfo(node_id="node_3", node_type=ObjectType.TEXT)
    ]

    sample_text_nodes = [node1, node2, node3, node4] # Order doesn't strictly matter for visualizer input
    output_file = "visualization_output_dummy.md"
    visualize_text_nodes_to_markdown(sample_text_nodes, output_file)

    # Test with an empty list
    visualize_text_nodes_to_markdown([], "empty_visualization.md")

    # Test with a "Document Root" node
    root_doc_node = TextNode(
        id_="doc_root_node", text="This is the main document overview.",
        metadata={"title": "Document Root", "level": 0, "page_label": "1-10", "start_page_idx": 0, "file_name": "dummy_root.pdf"},
        relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="doc_456", node_type=ObjectType.DOCUMENT)}
    )
    chapter_a_node = TextNode(
        id_="chap_a", text="Content of Chapter A.",
        metadata={"title": "Chapter A", "level": 1, "page_label": "1-5", "start_page_idx": 0, "file_name": "dummy_root.pdf", "context": "Chapter A"},
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id="doc_456", node_type=ObjectType.DOCUMENT),
            NodeRelationship.PARENT: RelatedNodeInfo(node_id="doc_root_node", node_type=ObjectType.TEXT)
        }
    )
    root_doc_node.relationships[NodeRelationship.CHILD] = [RelatedNodeInfo(node_id="chap_a", node_type=ObjectType.TEXT)]

    visualize_text_nodes_to_markdown([root_doc_node, chapter_a_node], "visualization_with_root_dummy.md")
# """
