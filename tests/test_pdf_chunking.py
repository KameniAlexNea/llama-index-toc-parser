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
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = []
        mock_doc.page_count = 3

        mock_pages_list = []
        for i in range(mock_doc.page_count):
            mock_page_obj = MagicMock(name=f"Page_{i}")
            
            # Define the side_effect function for this specific page's get_text
            def create_get_text_side_effect(page_idx_closure):
                def get_text_side_effect_impl(*args, **kwargs):
                    page_content_text = f"Content of page {page_idx_closure + 1}"
                    if args and args[0] == "dict":
                        return {
                            "blocks": [{
                                "type": 0, "bbox": [10, 10, 500, 100], # Example bbox
                                "lines": [{"spans": [{"text": page_content_text}]}]
                            }],
                            "width": 600, "height": 800 # Example page dimensions
                        }
                    else:
                        # This branch is hit by the loop in build_toc_tree for no-TOC case
                        return page_content_text 
                return get_text_side_effect_impl

            mock_page_obj.get_text.side_effect = create_get_text_side_effect(i)
            mock_pages_list.append(mock_page_obj)

        mock_doc.load_page.side_effect = lambda page_idx: mock_pages_list[page_idx]
        mock_open.return_value = mock_doc

        chunker = PDFTOCChunker(
            pdf_path=self.temp_pdf_path, source_display_name="test_no_toc.pdf"
        )
        text_nodes = chunker.get_text_nodes()

        self.assertEqual(len(text_nodes), 1)
        self.assertEqual(text_nodes[0].metadata["title"], "Document Root")
        self.assertEqual(text_nodes[0].metadata["level"], 0)
        self.assertEqual(text_nodes[0].metadata["start_page_idx"], 0)
        self.assertEqual(text_nodes[0].metadata["end_page_idx"], 2)  # 0-based indexing

        # Check content includes all pages
        expected_content = "Content of page 1\nContent of page 2\nContent of page 3\n"
        self.assertEqual(text_nodes[0].text.strip(), expected_content.strip())


    @patch("fitz.open")
    def test_hierarchical_pdf(self, mock_open):
        """Test chunking a PDF with a hierarchical TOC structure"""
        mock_doc = MagicMock()
        mock_doc.page_count = 10
        mock_toc = [
            [1, "Chapter 1", 1],
            [2, "Section 1.1", 2],
            [3, "Subsection 1.1.1", 3],
            [2, "Section 1.2", 4],
            [1, "Chapter 2", 5],
            [2, "Section 2.1", 6],
        ]
        mock_doc.get_toc.return_value = mock_toc

        mock_pages_list = []
        for i in range(mock_doc.page_count):
            mock_page_obj = MagicMock(name=f"Page_{i}")
            titles_on_this_page_i = [item[1] for item in mock_toc if item[2] - 1 == i]

            def create_get_text_side_effect(page_idx_closure, titles_on_page_closure):
                def get_text_side_effect_impl(*args, **kwargs):
                    page_text_for_content = f"Content of page {page_idx_closure + 1}"
                    if titles_on_page_closure:
                        page_text_for_content += " " + " ".join(titles_on_page_closure)
                    
                    if args and args[0] == "dict":
                        blocks_for_dict = []
                        y_val = 10.0
                        # Add blocks for titles to be found by _find_heading_y_position
                        for title_text in titles_on_page_closure:
                            blocks_for_dict.append({
                                "type": 0, "bbox": [10, y_val, 500, y_val + 10],
                                "lines": [{"spans": [{"text": title_text}]}]
                            })
                            y_val += 20
                        # Add a generic block for content extraction by _extract_content
                        blocks_for_dict.append({
                            "type": 0, "bbox": [10, y_val, 500, y_val + 100],
                            "lines": [{"spans": [{"text": f"Some other text on page {page_idx_closure + 1}"}]}]
                        })
                        return {"blocks": blocks_for_dict, "width": 600, "height": 800}
                    else:
                        return page_text_for_content + "\n"
                return get_text_side_effect_impl

            mock_page_obj.get_text.side_effect = create_get_text_side_effect(i, titles_on_this_page_i)
            mock_pages_list.append(mock_page_obj)
        
        mock_doc.load_page.side_effect = lambda page_idx: mock_pages_list[page_idx]
        mock_open.return_value = mock_doc

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
        mock_doc = MagicMock()
        mock_doc.page_count = 5
        mock_toc = [[1, "Chapter 1", 1], [2, "Section 1.1", 2], [1, "Chapter 2", 3]]
        mock_doc.get_toc.return_value = mock_toc

        mock_pages_list = []
        for i in range(mock_doc.page_count):
            mock_page_obj = MagicMock(name=f"Page_{i}")
            titles_on_this_page_i = [item[1] for item in mock_toc if item[2] - 1 == i]

            def create_get_text_side_effect(page_idx_closure, titles_on_page_closure):
                def get_text_side_effect_impl(*args, **kwargs):
                    page_text_for_content = f"Content of page {page_idx_closure + 1}"
                    if titles_on_page_closure:
                        page_text_for_content += " " + " ".join(titles_on_page_closure)

                    if args and args[0] == "dict":
                        blocks_for_dict = []
                        y_val = 10.0
                        for title_text in titles_on_page_closure:
                            blocks_for_dict.append({
                                "type": 0, "bbox": [10, y_val, 500, y_val + 10],
                                "lines": [{"spans": [{"text": title_text}]}]
                            })
                            y_val += 20
                        blocks_for_dict.append({
                            "type": 0, "bbox": [10, y_val, 500, y_val + 100],
                            "lines": [{"spans": [{"text": f"Some other text on page {page_idx_closure + 1}"}]}]
                        })
                        return {"blocks": blocks_for_dict, "width": 600, "height": 800}
                    else:
                        return page_text_for_content + "\n"
                return get_text_side_effect_impl
            
            mock_page_obj.get_text.side_effect = create_get_text_side_effect(i, titles_on_this_page_i)
            mock_pages_list.append(mock_page_obj)

        mock_doc.load_page.side_effect = lambda page_idx: mock_pages_list[page_idx]
        mock_open.return_value = mock_doc

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
        mock_doc = MagicMock()
        mock_doc.page_count = 5
        mock_toc = [
            [1, "Chapter 1", 1],  # spans pages 1-2 (idx 0-1)
            [1, "Chapter 2", 3],  # spans pages 3-5 (idx 2-4)
        ]
        mock_doc.get_toc.return_value = mock_toc

        mock_pages_list = []
        for i in range(mock_doc.page_count):
            mock_page_obj = MagicMock(name=f"Page_{i}")
            titles_on_this_page_i = [item[1] for item in mock_toc if item[2] - 1 == i]

            def create_get_text_side_effect(page_idx_closure, titles_on_page_closure):
                def get_text_side_effect_impl(*args, **kwargs):
                    # For _extract_content, we need to provide the basic page content.
                    # The titles themselves are usually part of this content.
                    page_text_for_content = f"Content of page {page_idx_closure + 1}"
                    # If a title is on this page, _find_heading_y_position needs to find it.
                    # _extract_content will then grab text around it.
                    
                    if args and args[0] == "dict":
                        blocks_for_dict = []
                        y_val = 10.0 
                        # Simulate titles for _find_heading_y_position
                        for title_text in titles_on_page_closure:
                            blocks_for_dict.append({
                                "type": 0, "bbox": [10, y_val, 500, y_val + 10], # y for title
                                "lines": [{"spans": [{"text": title_text}]}]
                            })
                            y_val += 20
                        # Simulate main content for _extract_content
                        blocks_for_dict.append({
                            "type": 0, "bbox": [10, y_val, 500, y_val + 100], # y for main content
                            "lines": [{"spans": [{"text": f"Content of page {page_idx_closure + 1}"}]}]
                        })
                        return {"blocks": blocks_for_dict, "width": 600, "height": 800}
                    else:
                        # Fallback, though _extract_content uses "dict"
                        return f"Content of page {page_idx_closure + 1}\n" 
                return get_text_side_effect_impl

            mock_page_obj.get_text.side_effect = create_get_text_side_effect(i, titles_on_this_page_i)
            mock_pages_list.append(mock_page_obj)

        mock_doc.load_page.side_effect = lambda page_idx: mock_pages_list[page_idx]
        mock_open.return_value = mock_doc

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
        # The mock for get_text("dict",...) returns "Content of page X" as one of the blocks.
        # _extract_content joins these.
        self.assertEqual(chapter1.text.strip(), "Chapter 1\nContent of page 1\nContent of page 2")
        self.assertEqual(
            chapter2.text.strip(), "Chapter 2\nContent of page 3\nContent of page 4\nContent of page 5"
        )

    def test_integration(self):
        """Test the PDF chunking with the convenience function (actual PDF file)"""
        # Skip this test if no test PDF is available
        test_pdf_path = os.path.join(self.test_dir, "test.pdf")
        if not os.path.exists(test_pdf_path):
            self.skipTest("No test PDF available - skipping integration test")

        # Test using convenience function
        from node_chunker.chunks import (
            chunk_document_by_toc_to_text_nodes,
        )

        text_nodes = chunk_document_by_toc_to_text_nodes(
            test_pdf_path,
        )

        # Basic verification that we got some nodes
        self.assertGreater(len(text_nodes), 0)

        # Check file metadata
        for node in text_nodes:
            self.assertEqual(node.metadata["file_name"], "test.pdf")


if __name__ == "__main__":
    unittest.main()
