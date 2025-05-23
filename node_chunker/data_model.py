import uuid
from typing import Any, Dict, Iterator, List, Optional


class DocumentNode:
    """
    Represents a single node in the document graph structure.

    Each node can have multiple children and maintains bidirectional relationships.
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        title: str = "",
        content: str = "",
        level: int = 0,
        page_num: int = 0,
        end_page: Optional[int] = None,
        y_position: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.node_id = node_id or str(uuid.uuid4())
        self.title = title
        self.content = content
        self.level = level
        self.page_num = page_num
        self.end_page = end_page
        self.y_position = y_position
        self.metadata = metadata or {}

        # Graph relationships
        self.parent_id: Optional[str] = None
        self.children_ids: List[str] = []

    def __repr__(self) -> str:
        return (
            f"DocumentNode(id={self.node_id}, title='{self.title}', level={self.level})"
        )


class DocumentGraph:
    """
    A graph-based representation of a document's hierarchical structure.
    """

    def __init__(self, root_title: str = "Document Root"):
        self.nodes: Dict[str, DocumentNode] = {}
        self.root_id: Optional[str] = None
        self._create_root(root_title)

    def _create_root(self, title: str) -> None:
        """Create the root node of the document graph."""
        root_node = DocumentNode(title=title, level=0)
        self.root_id = root_node.node_id
        self.nodes[root_node.node_id] = root_node

    def add_node(
        self,
        title: str,
        content: str = "",
        level: int = 1,
        page_num: int = 0,
        end_page: Optional[int] = None,
        y_position: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> str:
        """
        Add a new node to the graph.

        Returns:
            The node_id of the created node
        """
        node = DocumentNode(
            node_id=node_id,
            title=title,
            content=content,
            level=level,
            page_num=page_num,
            end_page=end_page,
            y_position=y_position,
            metadata=metadata,
        )
        self.nodes[node.node_id] = node
        return node.node_id

    def add_child(self, parent_id: str, child_id: str) -> bool:
        """
        Add a child relationship between two nodes.

        Returns:
            True if successful, False otherwise
        """
        if parent_id not in self.nodes or child_id not in self.nodes:
            return False

        parent_node = self.nodes[parent_id]
        child_node = self.nodes[child_id]

        # Avoid duplicate relationships
        if child_id not in parent_node.children_ids:
            parent_node.children_ids.append(child_id)
            child_node.parent_id = parent_id
            return True
        return False

    def get_node(self, node_id: str) -> Optional[DocumentNode]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> List[DocumentNode]:
        """Get all direct children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [
            self.nodes[child_id]
            for child_id in node.children_ids
            if child_id in self.nodes
        ]

    def get_all_children(self, node_id: str) -> List[DocumentNode]:
        """Get all direct children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [
            (self.nodes[child_id], self.get_all_children(self.nodes[child_id]))
            for child_id in node.children_ids
            if child_id in self.nodes
        ]

    def _traverse_preorder(
        self, start_node_id: Optional[str] = None
    ) -> Iterator[DocumentNode]:
        """
        Pre-order traversal: root, then children from left to right.

        Args:
            start_node_id: Node to start traversal from (root if None)

        Yields:
            DocumentNode objects in pre-order
        """
        start_id = start_node_id or self.root_id
        if not start_id or start_id not in self.nodes:
            return

        yield from self._preorder_traversal(start_id)

    def _preorder_traversal(self, node_id: str) -> Iterator[DocumentNode]:
        """Pre-order traversal: root, left subtree, right subtree."""
        node = self.nodes.get(node_id)
        if not node:
            return

        # Yield current node first
        yield node

        # Then yield all children
        for child_id in node.children_ids:
            yield from self._preorder_traversal(child_id)

    def get_content(
        self, start_node_id: Optional[str] = None
    ) -> Iterator[DocumentNode]:
        """
        Get nodes using pre-order traversal.

        Args:
            start_node_id: Node to start from (root if None)

        Yields:
            DocumentNode objects in pre-order
        """
        yield from self._traverse_preorder(start_node_id)

    def get_tree_structure(
        self, start_node_id: Optional[str] = None, indent: str = "  "
    ) -> str:
        """
        Get a string representation of the tree structure in pre-order.

        Returns:
            Formatted tree structure string
        """
        result = []

        def build_tree_string(node_id: str, depth: int):
            node = self.nodes.get(node_id)
            if not node:
                return

            prefix = indent * depth
            result.append(
                f"{prefix}{node.title} (Level {node.level}, Page {node.page_num})"
            )

            for child_id in node.children_ids:
                build_tree_string(child_id, depth + 1)

        start_id = start_node_id or self.root_id
        if start_id:
            build_tree_string(start_id, 0)

        return "\n".join(result)

    def get_parent(self, node_id: str) -> Optional[DocumentNode]:
        """Get the parent of a node."""
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return None
        return self.nodes.get(node.parent_id)

    def get_ancestors(self, node_id: str) -> List[DocumentNode]:
        """Get all ancestors of a node (path to root)."""
        ancestors = []
        current_node = self.get_node(node_id)

        while current_node and current_node.parent_id:
            parent = self.get_parent(current_node.node_id)
            if parent:
                ancestors.append(parent)
                current_node = parent
            else:
                break

        return ancestors
