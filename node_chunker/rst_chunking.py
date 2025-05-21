import logging

from docutils.core import publish_doctree
from docutils.nodes import Node, Text, section, title

from .document_chunking import BaseDocumentChunker, TOCNode

# Get logger for this module
logger = logging.getLogger(__name__)


class RSTTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on reStructuredText sections.
    """

    def __init__(self, rst_content: str, source_display_name: str):
        """
        Initialize the chunker with reStructuredText content.

        Args:
            rst_content: The reStructuredText content or file path
            source_display_name: The original name of the source
        """
        super().__init__(source_path=rst_content, source_display_name=source_display_name)
        self.doctree = None
        self._document_loaded = False
        self._section_map = {}  # Maps docutils section nodes to our TOC nodes

    def load_document(self) -> None:
        """Load the RST document and parse it with docutils"""
        try:
            # Parse the RST content
            self.doctree = publish_doctree(self.source_path)
            self._document_loaded = True
        except Exception as e:
            logger.error(f"Error loading RST document: {e}")
            raise

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the RST sections.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        # Initialize the document tree
        self.root_node = TOCNode(title="Document Root", page_num=0, level=0)

        # If no sections found, treat entire document as one chunk
        if not self.doctree.traverse(section):
            self.root_node.content = self._get_full_text(self.doctree)
            self.root_node.end_page = 0  # RST doesn't have pages
            return self.root_node

        # Process sections recursively
        self._process_sections(self.doctree, self.root_node, 0)

        return self.root_node

    def _process_sections(
        self, node: Node, parent_toc_node: TOCNode, level: int
    ) -> None:
        """
        Process RST document sections recursively.

        Args:
            node: Current docutils node
            parent_toc_node: Parent TOCNode to attach new nodes to
            level: Current hierarchy level
        """
        # Process all sections at this level
        for section_node in node.traverse(section, siblings=True):
            # Skip if we've already processed this section
            if id(section_node) in self._section_map:
                continue

            # Get the section title
            section_title = "Untitled Section"
            title_nodes = section_node.traverse(title, siblings=True, descend=False)
            if title_nodes:
                section_title = self._get_full_text(title_nodes[0]).strip()

            # Create a TOC node for this section
            section_level = level + 1
            toc_node = TOCNode(
                title=section_title,
                page_num=0,  # RST doesn't have pages
                level=section_level,
            )
            parent_toc_node.add_child(toc_node)
            self._section_map[id(section_node)] = toc_node

            # Extract content from this section, excluding subsections
            toc_node.content = self._extract_section_content(section_node)
            toc_node.end_page = 0  # RST doesn't have pages

            # Process subsections recursively
            subsections = list(
                section_node.traverse(section, siblings=True, descend=False)
            )
            if subsections:
                for subsection in subsections:
                    self._process_sections(subsection, toc_node, section_level)

    def _extract_section_content(self, section_node: Node) -> str:
        """
        Extract content from a section, excluding subsections.

        Args:
            section_node: The section node to extract content from

        Returns:
            The extracted content as a string
        """
        # Get the title first
        title_text = ""
        title_nodes = section_node.traverse(title, siblings=True, descend=False)
        if title_nodes:
            title_text = self._get_full_text(title_nodes[0])

        # Extract content excluding subsections
        content_parts = [title_text] if title_text else []

        # Process all child nodes except subsections and title
        for node in section_node.children:
            if not isinstance(node, title) and not isinstance(node, section):
                content_parts.append(self._get_full_text(node))

        return "\n\n".join(part for part in content_parts if part.strip())

    def _get_full_text(self, node: Node) -> str:
        """
        Extract all text from a node and its children.

        Args:
            node: The docutils node to extract text from

        Returns:
            The extracted text as a string
        """
        if isinstance(node, Text):
            return node.astext()

        text_parts = []
        for child in node.children:
            text_parts.append(self._get_full_text(child))

        return "".join(text_parts)

    def close(self) -> None:
        """Clean up resources"""
        self.doctree = None
        self._section_map = {}
        self._document_loaded = False
