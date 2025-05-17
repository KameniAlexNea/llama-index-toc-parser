import os
import unittest

from node_chunker.chunks import chunk_document_by_toc_to_text_nodes


class TestIntegration(unittest.TestCase):
    def setUp(self):
        # Create test directory and files
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_files")
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Track files created during tests for cleanup
        self.test_files_to_cleanup = []

        # Create a markdown test file
        self.test_markdown = """# Test Document
This is a test document.

## Section 1
This is section 1.

### Subsection 1.1
This is subsection 1.1.

## Section 2
This is section 2.
"""
        self.markdown_path = os.path.join(self.test_dir, "integration_test.md")
        with open(self.markdown_path, "w") as f:
            f.write(self.test_markdown)
        
        # Add to cleanup list
        self.test_files_to_cleanup.append(self.markdown_path)
    
    def tearDown(self):
        """Clean up any files created during tests"""
        for file_path in self.test_files_to_cleanup:
            if os.path.exists(file_path):
                os.remove(file_path)

    def test_markdown_integration(self):
        """Test integration of markdown chunking with command line arguments"""
        # Test with the convenience function
        text_nodes = chunk_document_by_toc_to_text_nodes(
            self.markdown_path, is_markdown=True
        )

        # Basic verification
        self.assertEqual(len(text_nodes), 4)  # 4 sections

        # Check that all sections are present
        titles = [node.metadata["title"] for node in text_nodes]
        self.assertIn("Test Document", titles)
        self.assertIn("Section 1", titles)
        self.assertIn("Subsection 1.1", titles)
        self.assertIn("Section 2", titles)

        # Check context paths
        for node in text_nodes:
            if node.metadata["title"] == "Subsection 1.1":
                self.assertEqual(
                    node.metadata["context"],
                    "Test Document > Section 1 > Subsection 1.1",
                )

    def test_markdown_text_integration(self):
        """Test integration with raw markdown text instead of a file"""
        # Test with raw markdown text
        text_nodes = chunk_document_by_toc_to_text_nodes(
            self.test_markdown, is_markdown=True
        )

        # Basic verification
        self.assertEqual(len(text_nodes), 4)  # 4 sections

        # Check context metadata for nested sections
        for node in text_nodes:
            if node.metadata["title"] == "Section 1":
                self.assertEqual(node.metadata["context"], "Test Document > Section 1")
            elif node.metadata["title"] == "Section 2":
                self.assertEqual(node.metadata["context"], "Test Document > Section 2")

    def test_cli_argument_handling(self):
        """Test CLI argument parsing in main.py"""
        # Import the main module - this would be your example/main.py
        try:
            from example.main import parser as arg_parser
        except ImportError:
            self.skipTest("example/main.py not available or doesn't export parser")

        # Test argument parsing
        args = arg_parser.parse_args([self.markdown_path, "--markdown"])
        self.assertEqual(args.source, self.markdown_path)
        self.assertTrue(args.markdown)
        self.assertFalse(args.url)

        args = arg_parser.parse_args([self.markdown_path, "--url"])
        self.assertEqual(args.source, self.markdown_path)
        self.assertFalse(args.markdown)
        self.assertTrue(args.url)

        args = arg_parser.parse_args([self.markdown_path, "--verbose"])
        self.assertEqual(args.source, self.markdown_path)
        self.assertTrue(args.verbose)


if __name__ == "__main__":
    unittest.main()
