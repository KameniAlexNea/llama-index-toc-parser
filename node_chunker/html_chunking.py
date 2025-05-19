import logging
from typing import List, Tuple

from bs4 import BeautifulSoup, NavigableString, Tag

from .document_chunking import BaseDocumentChunker, TOCNode

# Get logger for this module
logger = logging.getLogger(__name__)


class HTMLTOCChunker(BaseDocumentChunker):
    """
    A document chunker that creates a hierarchical tree of nodes based on HTML headings (h1-h6).
    """

    def __init__(self, html_content: str, source_display_name: str):
        """
        Initialize the chunker with HTML content.

        Args:
            html_content: The HTML content as a string
            source_display_name: The original name of the source (e.g., URL or filename)
        """
        super().__init__(source_path="", source_display_name=source_display_name)
        self.html_content = html_content
        self.soup = None
        self._document_loaded = False

    def load_document(self) -> None:
        """Load the HTML document and parse it with BeautifulSoup"""
        try:
            self.soup = BeautifulSoup(self.html_content, "html.parser")
            self._document_loaded = True
        except Exception as e:
            logger.error(f"Error loading HTML: {e}")
            raise

    def build_toc_tree(self) -> TOCNode:
        """
        Build a tree structure from the HTML headings.

        Returns:
            The root node of the TOC tree
        """
        if not self._document_loaded:
            self.load_document()

        # Initialize the document tree
        self.root_node = TOCNode(title="Document Root", page_num=0, level=0)

        # Find all headers in the HTML document
        headers = self._extract_headers()

        if not headers:
            # No headers found, treat the entire document as one chunk
            body = self.soup.body or self.soup
            self.root_node.content = self._get_element_text(body)
            self.root_node.end_page = 0  # HTML is treated as a single page
            return self.root_node

        # Process headers and build TOC tree
        for i, (heading_tag, level, title) in enumerate(headers):
            # Create a new node for this header
            node = TOCNode(
                title=title,
                page_num=0,  # HTML doesn't have pages
                level=level,
            )

            # Find the appropriate parent for this node based on its level
            parent = self._find_parent_for_level(self.root_node, level)
            parent.add_child(node)

            # Extract content for this section
            node.content = self._extract_section_content(heading_tag, headers, i)
            node.end_page = 0  # HTML is treated as a single page

        return self.root_node

    def _extract_headers(self) -> List[Tuple[Tag, int, str]]:
        """
        Extract heading elements from HTML.

        Returns:
            List of tuples with (heading_tag, header_level, header_title)
        """
        headers = []
        heading_tags = self.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        for tag in heading_tags:
            # Get header level from tag name (h1 -> 1, h2 -> 2, etc.)
            level = int(tag.name[1])
            title = tag.get_text(strip=True)

            if title:  # Only include headings with text content
                headers.append((tag, level, title))

        return headers

    def _find_parent_for_level(self, node: TOCNode, target_level: int) -> TOCNode:
        """
        Find the appropriate parent node for a node with the given level.

        Args:
            node: Current node to start search from
            target_level: The level of the node we want to find a parent for

        Returns:
            The appropriate parent node
        """
        # If this is a level 1 header, its parent is the root node
        if target_level == 1:
            return self.root_node

        # If current node is at the level just above our target, it's our parent
        if node.level == target_level - 1:
            return node

        # If node has children, check the last child first (most recent node at that level)
        if node.children:
            last_child = node.children[-1]
            # If the last child's level is less than our target level, it could be our parent
            if last_child.level < target_level:
                return self._find_parent_for_level(last_child, target_level)

        # If we're here, we need to move up the tree
        if node.parent:
            return self._find_parent_for_level(node.parent, target_level)

        # Fallback to root node if no appropriate parent is found
        return self.root_node

    def _extract_section_content(
        self,
        current_heading: Tag,
        all_headings: List[Tuple[Tag, int, str]],
        current_index: int,
    ) -> str:
        """
        Extract content for a section between this heading and the next one.

        Args:
            current_heading: The current heading tag
            all_headings: List of all headings
            current_index: Index of the current heading in the all_headings list

        Returns:
            The extracted content as a string
        """
        content = []

        # Add the heading itself to the content
        content.append(self._get_element_text(current_heading))

        # Start with the element after the heading
        element = current_heading.next_sibling

        # If there's another heading after this one
        next_heading = None
        if current_index < len(all_headings) - 1:
            next_heading = all_headings[current_index + 1][0]

        # Collect all elements until we hit the next heading
        while element and element != next_heading:
            if isinstance(element, Tag):
                # Skip if this element contains the next heading
                if next_heading and element.find(
                    next_heading.name, string=next_heading.get_text(strip=True)
                ):
                    element = element.next_sibling
                    continue

                # Skip nested headings of same or higher level
                if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    element_level = int(element.name[1])
                    current_level = int(current_heading.name[1])
                    if element_level <= current_level:
                        element = element.next_sibling
                        continue

                content.append(self._get_element_text(element))
            elif isinstance(element, NavigableString) and element.strip():
                content.append(element.strip())

            element = element.next_sibling

        return "\n".join([c for c in content if c])

    def _get_element_text(self, element) -> str:
        """Extract clean text from an HTML element"""
        if isinstance(element, NavigableString):
            return element.strip()

        # Get text from the tag, preserving some structural elements
        if element.name in ["p", "div", "section", "article"]:
            return element.get_text("\n", strip=True)
        elif element.name in ["li", "dt", "dd"]:
            return "• " + element.get_text(strip=True)
        elif element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return element.get_text(strip=True)
        else:
            return element.get_text(" ", strip=True)

    def close(self) -> None:
        """Clean up resources"""
        self.soup = None
        self._document_loaded = False
