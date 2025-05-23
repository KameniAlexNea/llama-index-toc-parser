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
from pydantic import BaseModel, Field


class TOCNode(BaseModel):
    """
    Represents a node in the Table of Contents tree structure.

    Attributes:
        title: The node title
        page_num: The page number where this node starts
        level: The hierarchical level of this node (0 = root, 1 = chapter, etc.)
        parent: Optional parent TOCNode
        children: List of child TOCNodes
        content: Text content for this section
        end_page: Optional ending page number of this section
        y_position: Optional y-coordinate of the heading on its page
    """

    title: str
    page_num: int
    level: int
    parent: Optional["TOCNode"] = None
    children: List["TOCNode"] = Field(default_factory=list)
    content: str = ""
    end_page: Optional[int] = None
    y_position: Optional[float] = None

    class Config:
        arbitrary_types_allowed = True

    def add_child(self, child_node: "TOCNode") -> "TOCNode":
        """Add a child node to this node and return self for chaining."""
        self.children.append(child_node)
        child_node.parent = self
        return self


class BaseDocumentChunker(ABC):
    """
    Abstract base class for document chunkers that create hierarchical trees of nodes.

    This class defines the interface for all document chunkers and provides
    common functionality for converting TOC structures into TextNodes.
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
        self.root_node = TOCNode(title="Document Root", page_num=0, level=0)
        self.document_id = f"doc_{uuid.uuid4()}"

    @abstractmethod
    def load_document(self) -> None:
        """Load the document and extract its structure."""
        pass

    @abstractmethod
    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the document headings/TOC.

        Returns:
            The root node of the TOC tree
        """
        pass

    def get_all_nodes(self) -> List[TOCNode]:
        """Get a flattened list of all nodes in the TOC tree."""
        nodes = []

        def collect_nodes(node: TOCNode):
            nodes.append(node)
            for child in node.children:
                collect_nodes(child)

        collect_nodes(self.root_node)
        return nodes

    def get_text_nodes(self) -> List[TextNode]:
        """
        Convert the TOCNode tree into a list of LlamaIndex TextNode objects,
        preserving hierarchical relationships.

        Returns:
            A list of TextNode objects representing the document chunks.
        """
        if not hasattr(self, "_document_loaded") or not self._document_loaded:
            self.build_toc_tree()

        all_toc_nodes = self.get_all_nodes()
        if not all_toc_nodes:
            return []

        text_node_list = []
        toc_node_obj_id_to_text_node_id_map: Dict[int, str] = {}

        # Generate unique IDs for all nodes first
        for toc_node in all_toc_nodes:
            toc_node_obj_id_to_text_node_id_map[id(toc_node)] = f"node_{uuid.uuid4()}"

        # Create TextNodes with proper relationships
        for toc_node in all_toc_nodes:
            text_node_id = toc_node_obj_id_to_text_node_id_map[id(toc_node)]
            metadata = self._create_node_metadata(toc_node)
            relationships = self._create_node_relationships(
                toc_node, toc_node_obj_id_to_text_node_id_map
            )

            # Skip empty Document Root nodes
            if (
                toc_node.title == "Document Root"
                and not toc_node.content.strip()
                and toc_node.level == 0
            ):
                if not any(
                    tn.metadata.get("title") == "Document Root" for tn in text_node_list
                ):
                    pass  # Skip adding Document Root if it has no content
            else:
                text_node = TextNode(
                    id_=text_node_id,
                    text=toc_node.content or "",
                    metadata=metadata,
                    relationships=relationships,
                )
                text_node_list.append(text_node)

        return text_node_list

    def _create_node_metadata(self, toc_node: TOCNode) -> Dict[str, Any]:
        """Create metadata dictionary for a node."""
        metadata = {
            "title": toc_node.title,
            "level": toc_node.level,
            "file_name": os.path.basename(self.source_display_name),
        }

        # Add context path showing the hierarchy
        context = self._build_context_path(toc_node)
        if context:
            metadata["context"] = context

        # Add page information if available
        if hasattr(toc_node, "page_num"):
            page_label = str(toc_node.page_num + 1)
            if toc_node.end_page is not None and toc_node.end_page > toc_node.page_num:
                page_label = f"{toc_node.page_num + 1}-{toc_node.end_page + 1}"

            metadata["page_label"] = page_label
            metadata["start_page_idx"] = toc_node.page_num

            if toc_node.end_page is not None:
                metadata["end_page_idx"] = toc_node.end_page

        return metadata

    def _build_context_path(self, toc_node: TOCNode) -> str:
        """
        Build a hierarchical context path string showing all parent titles.
        Format: "parent1 > parent2 > parent3 > ... > current_node"
        """
        if not toc_node:
            return ""

        path_elements = []
        current = toc_node

        while current:
            # Skip adding "Document Root" to the context path
            if current.title != "Document Root":
                path_elements.insert(0, current.title)
            current = current.parent

        return " > ".join(path_elements)

    def _create_node_relationships(
        self, toc_node: TOCNode, node_id_map: Dict[int, str]
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
        if toc_node.parent and id(toc_node.parent) in node_id_map:
            parent_text_node_id = node_id_map[id(toc_node.parent)]
            relationships[NodeRelationship.PARENT] = RelatedNodeInfo(
                node_id=parent_text_node_id, node_type=ObjectType.TEXT
            )

        # Add child relationships if any
        child_related_nodes = []
        for child_toc_node in toc_node.children:
            if id(child_toc_node) in node_id_map:
                child_text_node_id = node_id_map[id(child_toc_node)]
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
