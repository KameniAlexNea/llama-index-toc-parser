import os
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from llama_index.core.schema import (
    NodeRelationship,
    ObjectType,
    RelatedNodeInfo,
    TextNode,
)
from .data_model import DocumentGraph, DocumentNode


class BaseDocumentChunker(ABC):
    """
    Abstract base class for document chunkers that create hierarchical graphs of nodes.

    This class defines the interface for all document chunkers and provides
    common functionality for converting DocumentGraph structures into TextNodes.
    """

    def __init__(self, source_path: str, source_display_name: str):
        """
        Initialize the chunker with the path to the document.

        Args:
            source_path: Path to the document file
            source_display_name: The original name of the source (e.g., URL or original filename)
        """
        self.source_path = source_path
        self.source_display_name = source_display_name
        self.document_id = f"doc_{uuid.uuid4()}"

    @abstractmethod
    def load_document(self) -> None:
        """Load the document and extract its structure."""
        pass

    @abstractmethod
    def build_toc_tree(self) -> DocumentGraph:
        """
        Build a graph structure from the document headings/TOC.

        Returns:
            The document graph
        """
        pass

    def get_all_nodes(self) -> List[DocumentNode]:
        """Get a flattened list of all nodes in pre-order."""
        if not hasattr(self, 'document_graph'):
            self.build_toc_tree()
        
        return list(self.document_graph.get_content_preorder())

    def get_text_nodes(self) -> List[TextNode]:
        """
        Convert the DocumentGraph into a list of LlamaIndex TextNode objects,
        preserving hierarchical relationships.

        Returns:
            A list of TextNode objects representing the document chunks.
        """
        if not hasattr(self, "_document_loaded") or not self._document_loaded:
            self.build_toc_tree()

        all_nodes = self.get_all_nodes()
        if not all_nodes:
            return []

        text_node_list = []
        node_id_to_text_node_id_map: Dict[str, str] = {}

        # Generate unique IDs for all nodes first
        for node in all_nodes:
            node_id_to_text_node_id_map[node.node_id] = f"node_{uuid.uuid4()}"

        # Create TextNodes with proper relationships
        for node in all_nodes:
            text_node_id = node_id_to_text_node_id_map[node.node_id]
            metadata = self._create_node_metadata(node)
            relationships = self._create_node_relationships(
                node, node_id_to_text_node_id_map
            )

            # Skip empty Document Root nodes
            if (
                node.title == "Document Root"
                and not node.content.strip()
                and node.level == 0
            ):
                if not any(
                    tn.metadata.get("title") == "Document Root" for tn in text_node_list
                ):
                    pass  # Skip adding Document Root if it has no content
            else:
                text_node = TextNode(
                    id_=text_node_id,
                    text=node.content or "",
                    metadata=metadata,
                    relationships=relationships,
                )
                text_node_list.append(text_node)

        return text_node_list

    def _create_node_metadata(self, node: DocumentNode) -> Dict[str, Any]:
        """Create metadata dictionary for a node."""
        metadata = {
            "title": node.title,
            "level": node.level,
            "file_name": os.path.basename(self.source_display_name),
        }

        # Add context path showing the hierarchy
        context = self._build_context_path(node)
        if context:
            metadata["context"] = context

        # Add page information if available
        if hasattr(node, "page_num"):
            page_label = str(node.page_num + 1)
            if node.end_page is not None and node.end_page > node.page_num:
                page_label = f"{node.page_num + 1}-{node.end_page + 1}"

            metadata["page_label"] = page_label
            metadata["start_page_idx"] = node.page_num

            if node.end_page is not None:
                metadata["end_page_idx"] = node.end_page

        return metadata

    def _build_context_path(self, node: DocumentNode) -> str:
        """
        Build a hierarchical context path string showing all parent titles.
        Format: "parent1 > parent2 > parent3 > ... > current_node"
        """
        if not node or not hasattr(self, 'document_graph'):
            return ""

        path_elements = []
        ancestors = self.document_graph.get_ancestors(node.node_id)
        
        # Add ancestors in reverse order (from root to immediate parent)
        for ancestor in reversed(ancestors):
            if ancestor.title != "Document Root":
                path_elements.append(ancestor.title)
        
        # Add current node
        if node.title != "Document Root":
            path_elements.append(node.title)

        return " > ".join(path_elements)

    def _create_node_relationships(
        self, node: DocumentNode, node_id_map: Dict[str, str]
    ) -> Dict[NodeRelationship, Any]:
        """Create relationship dictionary for a node."""
        relationships = {}

        # Add source relationship
        relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
            node_id=self.document_id,
            node_type=ObjectType.DOCUMENT,
            metadata={"file_name": os.path.basename(self.source_display_name)},
        )

        # Add parent relationship if exists
        if hasattr(self, 'document_graph'):
            parent = self.document_graph.get_parent(node.node_id)
            if parent and parent.node_id in node_id_map:
                parent_text_node_id = node_id_map[parent.node_id]
                relationships[NodeRelationship.PARENT] = RelatedNodeInfo(
                    node_id=parent_text_node_id, node_type=ObjectType.TEXT
                )

            # Add child relationships if any
            children = self.document_graph.get_children(node.node_id)
            child_related_nodes = []
            for child in children:
                if child.node_id in node_id_map:
                    child_text_node_id = node_id_map[child.node_id]
                    child_related_nodes.append(
                        RelatedNodeInfo(
                            node_id=child_text_node_id, node_type=ObjectType.TEXT
                        )
                    )

            if child_related_nodes:
                relationships[NodeRelationship.CHILD] = child_related_nodes

        return relationships

    @abstractmethod
    def close(self) -> None:
        """Close the document and free resources."""
        pass

    def __enter__(self):
        self.load_document()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
