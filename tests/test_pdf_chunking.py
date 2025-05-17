import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from llama_index.core.schema import NodeRelationship

from node_chunker.pdf_chunking import PDFTOCChunker


class TestPDFChunking(unittest.TestCase):
    def setUp(self):
        # Create a test directory
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_files")
        os.makedirs(self.test_dir, exist_ok=True)

        # Create a temp file for mock PDF
        self.temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self.temp_pdf_path = self.temp_pdf.name
        self.temp_pdf.close()

    def tearDown(self):
        # Clean up the temp file
        if os.path.exists(self.temp_pdf_path):
            os.unlink(self.temp_pdf_path)

    @patch("fitz.open")
    def test_no_toc_pdf(self, mock_open):
        """Test chunking a PDF with no table of contents"""
        # Mock PyMuPDF behavior for a PDF with no TOC
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = []
        mock_doc.page_count = 3

        # Mock page content
        mock_pages = []
        for i in range(3):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Content of page {i+1}"
            mock_pages.append(mock_page)

        mock_doc.load_page.side_effect = mock_pages
        mock_open.return_value = mock_doc

        # Create the chunker with our mocked PDF
        chunker = PDFTOCChunker(
            pdf_path=self.temp_pdf_path, source_display_name="test_no_toc.pdf"
        )
        text_nodes = chunker.get_text_nodes()

        # Should be one node with the entire document content
        self.assertEqual(len(text_nodes), 1)
        self.assertEqual(text_nodes[0].metadata["title"], "Document Root")
        self.assertEqual(text_nodes[0].metadata["level"], 0)
        self.assertEqual(text_nodes[0].metadata["start_page_idx"], 0)
        self.assertEqual(text_nodes[0].metadata["end_page_idx"], 2)  # 0-based indexing

        # Check content includes all pages
        expected_content = "Content of page 1\nContent of page 2\nContent of page 3\n"
        self.assertEqual(text_nodes[0].text, expected_content)

    @patch("fitz.open")
    def test_hierarchical_pdf(self, mock_open):
        """Test chunking a PDF with a hierarchical TOC structure"""
        # Mock PyMuPDF behavior for a PDF with hierarchical TOC
        mock_doc = MagicMock()
        mock_doc.page_count = 10

        # Create a mock TOC structure
        # PyMuPDF TOC format: [level, title, page, ...]
        mock_toc = [
            [1, "Chapter 1", 1],
            [2, "Section 1.1", 2],
            [3, "Subsection 1.1.1", 3],
            [2, "Section 1.2", 4],
            [1, "Chapter 2", 5],
            [2, "Section 2.1", 6],
        ]
        mock_doc.get_toc.return_value = mock_toc

        # Mock page content
        def mock_load_page(page_num):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Content of page {page_num+1}"
            return mock_page

        mock_doc.load_page.side_effect = mock_load_page
        mock_open.return_value = mock_doc

        # Create the chunker with our mocked PDF
        chunker = PDFTOCChunker(
            pdf_path=self.temp_pdf_path, source_display_name="test_hierarchy.pdf"
        )
        text_nodes = chunker.get_text_nodes()

        # Get nodes by title for easier testing
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}

        # Should be 6 nodes for the 6 TOC entries
        self.assertEqual(len(text_nodes), 6)

        # Check titles and levels
        self.assertIn("Chapter 1", nodes_by_title)
        self.assertIn("Section 1.1", nodes_by_title)
        self.assertIn("Subsection 1.1.1", nodes_by_title)

        self.assertEqual(nodes_by_title["Chapter 1"].metadata["level"], 1)
        self.assertEqual(nodes_by_title["Section 1.1"].metadata["level"], 2)
        self.assertEqual(nodes_by_title["Subsection 1.1.1"].metadata["level"], 3)

        # Check context paths
        self.assertEqual(nodes_by_title["Chapter 1"].metadata["context"], "Chapter 1")
        self.assertEqual(
            nodes_by_title["Section 1.1"].metadata["context"], "Chapter 1 > Section 1.1"
        )
        self.assertEqual(
            nodes_by_title["Subsection 1.1.1"].metadata["context"],
            "Chapter 1 > Section 1.1 > Subsection 1.1.1",
        )

    @patch("fitz.open")
    def test_relationships(self, mock_open):
        """Test that node relationships are correctly established in PDF chunks"""
        # Mock PyMuPDF behavior
        mock_doc = MagicMock()
        mock_doc.page_count = 5

        # Create a simple TOC structure
        mock_toc = [[1, "Chapter 1", 1], [2, "Section 1.1", 2], [1, "Chapter 2", 3]]
        mock_doc.get_toc.return_value = mock_toc

        # Mock page content
        def mock_load_page(page_num):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Content of page {page_num+1}"
            return mock_page

        mock_doc.load_page.side_effect = mock_load_page
        mock_open.return_value = mock_doc

        # Create the chunker
        chunker = PDFTOCChunker(
            pdf_path=self.temp_pdf_path, source_display_name="test_relationships.pdf"
        )
        text_nodes = chunker.get_text_nodes()

        # Create lookup dictionaries
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}
        nodes_by_id = {node.id_: node for node in text_nodes}

        # Test parent-child relationships
        chapter1 = nodes_by_title["Chapter 1"]
        section1_1 = nodes_by_title["Section 1.1"]

        # Check that Section 1.1 has Chapter 1 as parent
        self.assertIn(NodeRelationship.PARENT, section1_1.relationships)
        parent_id = section1_1.relationships[NodeRelationship.PARENT].node_id
        parent_node = nodes_by_id[parent_id]
        self.assertEqual(parent_node.metadata["title"], "Chapter 1")

        # Check that Chapter 1 has Section 1.1 as child
        self.assertIn(NodeRelationship.CHILD, chapter1.relationships)
        child_ids = [r.node_id for r in chapter1.relationships[NodeRelationship.CHILD]]
        self.assertTrue(
            any(
                nodes_by_id[cid].metadata["title"] == "Section 1.1" for cid in child_ids
            )
        )

    @patch("fitz.open")
    def test_page_extraction(self, mock_open):
        """Test that page content is correctly extracted for each node"""
        # Mock PyMuPDF behavior
        mock_doc = MagicMock()
        mock_doc.page_count = 5

        # Create a TOC structure where sections span multiple pages
        mock_toc = [
            [1, "Chapter 1", 1],  # spans pages 1-2
            [1, "Chapter 2", 3],  # spans pages 3-5
        ]
        mock_doc.get_toc.return_value = mock_toc

        # Mock page content
        def mock_load_page(page_num):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Content of page {page_num+1}"
            return mock_page

        mock_doc.load_page.side_effect = mock_load_page
        mock_open.return_value = mock_doc

        # Create the chunker
        chunker = PDFTOCChunker(
            pdf_path=self.temp_pdf_path, source_display_name="test_extraction.pdf"
        )
        text_nodes = chunker.get_text_nodes()

        # Test page ranges and content
        nodes_by_title = {node.metadata["title"]: node for node in text_nodes}

        chapter1 = nodes_by_title["Chapter 1"]
        chapter2 = nodes_by_title["Chapter 2"]

        # Check page ranges
        self.assertEqual(chapter1.metadata["start_page_idx"], 0)  # 0-based indexing
        self.assertEqual(chapter1.metadata["end_page_idx"], 1)
        self.assertEqual(chapter1.metadata["page_label"], "1-2")

        self.assertEqual(chapter2.metadata["start_page_idx"], 2)
        self.assertEqual(chapter2.metadata["end_page_idx"], 4)
        self.assertEqual(chapter2.metadata["page_label"], "3-5")

        # Check content extraction
        self.assertEqual(chapter1.text, "Content of page 1\nContent of page 2\n")
        self.assertEqual(
            chapter2.text, "Content of page 3\nContent of page 4\nContent of page 5\n"
        )

    def test_integration(self):
        """Test the PDF chunking with the convenience function (actual PDF file)"""
        # Skip this test if no test PDF is available
        test_pdf_path = os.path.join(self.test_dir, "test.pdf")
        if not os.path.exists(test_pdf_path):
            self.skipTest("No test PDF available - skipping integration test")

        # Test using convenience function
        from node_chunker.document_chunking import (
            chunk_document_by_toc_to_text_nodes,
        )

        text_nodes = chunk_document_by_toc_to_text_nodes(
            test_pdf_path, is_markdown=False
        )

        # Basic verification that we got some nodes
        self.assertGreater(len(text_nodes), 0)

        # Check file metadata
        for node in text_nodes:
            self.assertEqual(node.metadata["file_name"], "test.pdf")


if __name__ == "__main__":
    unittest.main()
