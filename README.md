# Node Chunker

A Python package for hierarchical document chunking based on Table of Contents or headers. Creates structured `TextNode` chunks for use with LlamaIndex.

## Overview

The `node_chunker` package provides tools to intelligently split documents (PDF and Markdown) into semantically meaningful chunks by using their table of contents or header structure. The resulting hierarchy preserves the document's structure and creates parent-child relationships between chunks.

## Key Features

- **PDF Chunking**: Leverages the table of contents to create hierarchical chunks
- **Markdown Chunking**: Uses headers to create structured document chunks
- **Hierarchical Structure**: Maintains parent-child relationships between document sections
- **LlamaIndex Integration**: Creates TextNodes with appropriate metadata and relationships
- **URL Support**: Download and process PDFs directly from URLs
- **Metadata Preservation**: Retains page numbers, section titles, and hierarchical context paths

## Installation

```bash
pip install git+git@github.com:KameniAlexNea/llama-index-toc-parser.git
```

## Usage

### Basic Usage

```python
from node_chunker.chunks import chunk_document_by_toc_to_text_nodes

# Process a PDF document
pdf_nodes = chunk_document_by_toc_to_text_nodes("path/to/document.pdf")

# Process a Markdown document
markdown_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/document.md", is_markdown=True
)

# Process a PDF from a URL
url_nodes = chunk_document_by_toc_to_text_nodes(
    "https://example.com/document.pdf", is_url=True
)

# Process raw markdown text
markdown_text = "# Title\nContent\n## Section\nMore content"
text_nodes = chunk_document_by_toc_to_text_nodes(
    markdown_text, is_markdown=True
)
```

### Working with TextNodes

The resulting `TextNode` objects contain:

- The text content from each section
- Metadata including titles, page numbers, and context paths
- Parent-child relationships between sections
- Source document references

```python
# Examine the nodes
for node in pdf_nodes:
    print(f"Title: {node.metadata['title']}")
    print(f"Level: {node.metadata['level']}")
    if 'context' in node.metadata:
        print(f"Context path: {node.metadata['context']}")
    if 'page_label' in node.metadata:
        print(f"Pages: {node.metadata['page_label']}")
    print(f"Content: {node.text[:100]}...")
    print("---")
```

### Command Line Interface

The package includes a simple CLI example in `example/main.py`:

```bash
python -m example.main --source document.pdf --verbose
python -m example.main --source document.md --markdown
python -m example.main --source https://example.com/doc.pdf --url
```

## Document Chunking Classes

### PDFTOCChunker

Chunks PDF documents based on their table of contents structure:

```python
from node_chunker.pdf_chunking import PDFTOCChunker

chunker = PDFTOCChunker(pdf_path="document.pdf", source_display_name="document.pdf")
text_nodes = chunker.get_text_nodes()
```

### MarkdownTOCChunker

Chunks Markdown documents based on header structure:

```python
from node_chunker.markdown_chunking import MarkdownTOCChunker

with open("document.md", "r") as f:
    markdown_text = f.read()

chunker = MarkdownTOCChunker(markdown_text, source_display_name="document.md")
text_nodes = chunker.get_text_nodes()
```

## Why Use Node Chunker?

Traditional document chunking approaches often split documents based on fixed token counts or arbitrary boundaries, which can break the semantic integrity of the content. `node_chunker` preserves the logical structure of documents by:

1. Respecting the author's own content organization (TOC/headers)
2. Maintaining hierarchical relationships between sections
3. Preserving metadata about document structure
4. Creating chunks that align with human understanding of the document

This structure is particularly valuable for:

- Question answering systems
- Document summarization
- Information retrieval applications
- Knowledge graph construction

## Requirements

- Python 3.9+
- llama-index-core
- PyMuPDF (fitz)
- requests

## Development

To set up the development environment:

```bash
git clone https://github.com/KameniAlexNea/llama-index-toc-parser.git
cd llama-index-toc-parser
pip install -e ".[test]"
```

Run tests with:

```bash
tox
```

## License

This project is licensed under [LICENSE] - see the LICENSE file for details.
