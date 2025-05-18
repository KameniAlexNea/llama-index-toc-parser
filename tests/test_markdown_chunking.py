import os
import unittest

from llama_index.core.schema import NodeRelationship

from node_chunker.markdown_chunking import MarkdownTOCChunker


class TestMarkdownChunking(unittest.TestCase):
    def setUp(self):
        # Create test directory if it doesn't exist
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_files")
        os.makedirs(self.test_dir, exist_ok=True)

        # Track files created during tests for cleanup
        self.test_files_to_cleanup = []

        # Sample markdown with a hierarchical structure
        self.hierarchical_markdown = """# Top Level Heading
This is top level content.

## Second Level Heading 1
This is second level content for heading 1.

### Third Level Heading 1.1
This is third level content for heading 1.1.

## Second Level Heading 2
This is second level content for heading 2.

# Another Top Level Heading
This is another top level section.
"""
        # Simple markdown with no headers
        self.no_headers_markdown = """This is just plain text content.
It has multiple lines but no headers.
It should be parsed as a single chunk.
"""
        # Complex markdown with mixed heading styles
        self.mixed_markdown = """# Top Level
Content

## Section 1
Content 1

Second Level Header
------------------
Content 2

### Subsection
Nested content

## Section 2
Final content
"""

    def tearDown(self):
        """Clean up any files created during tests"""
        for file_path in self.test_files_to_cleanup:
            if os.path.exists(file_path):
                os.remove(file_path)

    def test_no_headers(self):
        """Test chunking a markdown document with no headers"""
        chunker = MarkdownTOCChunker(self.no_headers_markdown, "test_no_headers.md")
        text_nodes = chunker.get_text_nodes()

        # Should be one node containing all content
        self.assertEqual(len(text_nodes), 1)
        self.assertEqual(text_nodes[0].text, self.no_headers_markdown)
        self.assertEqual(text_nodes[0].metadata["title"], "Document Root")
        self.assertEqual(text_nodes[0].metadata["level"], 0)
        # No context path for Document Root
        self.assertNotIn("context", text_nodes[0].metadata)

    def test_hierarchical_structure(self):
        """Test chunking a markdown document with a hierarchical structure"""
        chunker = MarkdownTOCChunker(self.hierarchical_markdown, "test_hierarchy.md")
        text_nodes = chunker.get_text_nodes()

        # Get nodes by title for easier testing
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}

        # Check number of nodes (5 headers plus possibly Document Root)
        self.assertGreaterEqual(len(text_nodes), 5)

        # Check titles
        self.assertIn("Top Level Heading", nodes_by_title)
        self.assertIn("Second Level Heading 1", nodes_by_title)
        self.assertIn("Third Level Heading 1.1", nodes_by_title)
        self.assertIn("Second Level Heading 2", nodes_by_title)
        self.assertIn("Another Top Level Heading", nodes_by_title)

        # Check levels
        self.assertEqual(nodes_by_title["Top Level Heading"].metadata["level"], 1)
        self.assertEqual(nodes_by_title["Second Level Heading 1"].metadata["level"], 2)
        self.assertEqual(nodes_by_title["Third Level Heading 1.1"].metadata["level"], 3)

        # Check context paths
        self.assertEqual(
            nodes_by_title["Top Level Heading"].metadata["context"], "Top Level Heading"
        )
        self.assertEqual(
            nodes_by_title["Second Level Heading 1"].metadata["context"],
            "Top Level Heading > Second Level Heading 1",
        )
        self.assertEqual(
            nodes_by_title["Third Level Heading 1.1"].metadata["context"],
            "Top Level Heading > Second Level Heading 1 > Third Level Heading 1.1",
        )

    def test_relationships(self):
        """Test that node relationships are correctly established"""
        chunker = MarkdownTOCChunker(
            self.hierarchical_markdown, "test_relationships.md"
        )
        text_nodes = chunker.get_text_nodes()

        # Create dictionaries for lookup
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}
        nodes_by_id = {node.id_: node for node in text_nodes}

        # Check parent-child relationships
        top_level = nodes_by_title["Top Level Heading"]
        second_level_1 = nodes_by_title["Second Level Heading 1"]
        third_level = nodes_by_title["Third Level Heading 1.1"]

        # Check that Second Level has Top Level as parent
        self.assertIn(NodeRelationship.PARENT, second_level_1.relationships)
        parent_id = second_level_1.relationships[NodeRelationship.PARENT].node_id
        parent_node = nodes_by_id[parent_id]
        self.assertEqual(parent_node.metadata["title"], "Top Level Heading")

        # Check that Top Level has Second Level as child
        self.assertIn(NodeRelationship.CHILD, top_level.relationships)
        child_ids = [r.node_id for r in top_level.relationships[NodeRelationship.CHILD]]
        self.assertTrue(
            any(
                nodes_by_id[cid].metadata["title"] == "Second Level Heading 1"
                for cid in child_ids
            )
        )

        # Check that Third Level has Second Level as parent
        self.assertIn(NodeRelationship.PARENT, third_level.relationships)
        parent_id = third_level.relationships[NodeRelationship.PARENT].node_id
        parent_node = nodes_by_id[parent_id]
        self.assertEqual(parent_node.metadata["title"], "Second Level Heading 1")

    def test_mixed_headers(self):
        """Test chunking a markdown document with mixed heading styles"""
        chunker = MarkdownTOCChunker(self.mixed_markdown, "test_mixed.md")
        text_nodes = chunker.get_text_nodes()

        # Get nodes by title
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}

        # Check that all headers were detected, including Setext style
        self.assertIn("Top Level", nodes_by_title)
        self.assertIn("Section 1", nodes_by_title)
        self.assertIn("Second Level Header", nodes_by_title)
        self.assertIn("Subsection", nodes_by_title)
        self.assertIn("Section 2", nodes_by_title)

        # Check levels for Setext style headers
        self.assertEqual(nodes_by_title["Second Level Header"].metadata["level"], 2)

        # Check context for Setext style headers
        self.assertEqual(
            nodes_by_title["Second Level Header"].metadata["context"],
            "Top Level > Second Level Header",
        )

    def test_file_based_chunking(self):
        """Test chunking from a markdown file"""
        # Create a test markdown file
        test_file_path = os.path.join(self.test_dir, "test_markdown.md")
        with open(test_file_path, "w") as f:
            f.write(self.hierarchical_markdown)

        # Add to cleanup list
        self.test_files_to_cleanup.append(test_file_path)

        # Test using convenience function
        from node_chunker.chunks import chunk_document_by_toc_to_text_nodes

        text_nodes = chunk_document_by_toc_to_text_nodes(
            test_file_path, is_markdown=True
        )

        # Verify results
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}
        self.assertIn("Top Level Heading", nodes_by_title)
        self.assertIn("Second Level Heading 1", nodes_by_title)

        # Check file metadata
        for node in text_nodes:
            self.assertEqual(node.metadata["file_name"], "test_markdown.md")


if __name__ == "__main__":
    unittest.main()
