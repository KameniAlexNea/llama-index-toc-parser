# Node Chunker

A Python package for hierarchical document chunking based on Table of Contents or headers. Creates structured `TextNode` chunks for use with LlamaIndex.

## Overview

The `node_chunker` package provides tools to intelligently split documents into semantically meaningful chunks by using their table of contents or header structure. The resulting hierarchy preserves the document's structure and creates parent-child relationships between chunks.

## Key Features

- **Multi-Format Support**: Process PDF, Markdown, HTML, Word documents, Jupyter Notebooks, and reStructuredText
- **PDF Chunking**: Leverages the table of contents to create hierarchical chunks
- **Markdown Chunking**: Uses headers to create structured document chunks
- **HTML Chunking**: Extracts structure from HTML heading tags (h1-h6)
- **Word Document Chunking**: Uses heading styles to structure content
- **Jupyter Notebook Chunking**: Builds structure from markdown cell headers
- **RST Chunking**: Creates chunks based on reStructuredText section structure
- **Hierarchical Structure**: Maintains parent-child relationships between document sections
- **LlamaIndex Integration**: Creates TextNodes with appropriate metadata and relationships
- **URL Support**: Download and process documents directly from URLs
- **Metadata Preservation**: Retains page numbers, section titles, and hierarchical context paths
- **Modular Installation**: Install only the dependencies you need for specific document formats

## Installation

The package name is `node-chunker` and will soon be available on PyPI.

### GitHub Installation

```bash
pip install git+https://github.com/KameniAlexNea/llama-index-toc-parser.git@main
```

### Coming Soon: PyPI Installation

Once available on PyPI, you'll be able to install with:

```bash
pip install node-chunker
```

### Install with Specific Format Support

```bash
# Install only PDF and Markdown support
pip install "node-chunker[pdf,md]"

# Install HTML and Word document support
pip install "node-chunker[html,docx]"

# Install all format support
pip install "node-chunker[all]"
```

## Usage

### Basic Usage

```python
from node_chunker.chunks import chunk_document_by_toc_to_text_nodes
from node_chunker.chunks import DocumentFormat

# Process a PDF document (auto-detected by file extension)
pdf_nodes = chunk_document_by_toc_to_text_nodes("path/to/document.pdf")

# Process a Markdown document
markdown_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/document.md", 
    format_type=DocumentFormat.MARKDOWN
)

# Process an HTML document
html_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/document.html", 
    format_type=DocumentFormat.HTML
)

# Process a Word document
docx_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/document.docx", 
    format_type=DocumentFormat.DOCX
)

# Process a Jupyter notebook
jupyter_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/notebook.ipynb", 
    format_type=DocumentFormat.JUPYTER
)

# Process a reStructuredText document
rst_nodes = chunk_document_by_toc_to_text_nodes(
    "path/to/document.rst", 
    format_type=DocumentFormat.RST
)

# Process a PDF from a URL
url_nodes = chunk_document_by_toc_to_text_nodes(
    "https://example.com/document.pdf", 
    is_url=True
)

# Process raw markdown text
markdown_text = "# Title\nContent\n## Section\nMore content"
text_nodes = chunk_document_by_toc_to_text_nodes(
    markdown_text, 
    format_type=DocumentFormat.MARKDOWN
)
```

### Format Selection

You can explicitly specify which document format to use:

```python
from node_chunker.chunks import chunk_document_by_toc_to_text_nodes, DocumentFormat

# Use the DocumentFormat enum to specify format
nodes = chunk_document_by_toc_to_text_nodes(
    "content.txt",  # Content that's actually markdown
    format_type=DocumentFormat.MARKDOWN
)

# You can also use strings to specify the format
nodes = chunk_document_by_toc_to_text_nodes(
    "content.txt",
    format_type="md"
)

# Check which formats are available with your current dependencies
from node_chunker.chunks import get_supported_formats
available_formats = get_supported_formats()
print(f"Available formats: {available_formats}")
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
from node_chunker.md_chunking import MarkdownTOCChunker

with open("document.md", "r") as f:
    markdown_text = f.read()

chunker = MarkdownTOCChunker(markdown_text, source_display_name="document.md")
text_nodes = chunker.get_text_nodes()
```

### HTMLTOCChunker

Chunks HTML documents based on heading tags:

```python
from node_chunker.html_chunking import HTMLTOCChunker

with open("document.html", "r") as f:
    html_content = f.read()

chunker = HTMLTOCChunker(html_content, source_display_name="document.html")
text_nodes = chunker.get_text_nodes()
```

### DOCXTOCChunker

Chunks Word documents based on heading styles:

```python
from node_chunker.docx_chunking import DOCXTOCChunker

chunker = DOCXTOCChunker(docx_path="document.docx", source_display_name="document.docx")
text_nodes = chunker.get_text_nodes()
```

### JupyterNotebookTOCChunker

Chunks Jupyter notebooks based on markdown cell headers:

```python
from node_chunker.jupyter_chunking import JupyterNotebookTOCChunker

chunker = JupyterNotebookTOCChunker(notebook_path="notebook.ipynb", source_display_name="notebook.ipynb")
text_nodes = chunker.get_text_nodes()
```

### RSTTOCChunker

Chunks reStructuredText documents based on section structure:

```python
from node_chunker.rst_chunking import RSTTOCChunker

with open("document.rst", "r") as f:
    rst_content = f.read()

chunker = RSTTOCChunker(rst_content, source_display_name="document.rst")
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

- Python 3.10+
- llama-index-core
- requests

Format-specific dependencies:
- PDF: PyMuPDF (fitz)
- HTML: BeautifulSoup4
- Word: python-docx
- Jupyter: nbformat
- RST: docutils

## Development

To set up the development environment:

```bash
git clone https://github.com/KameniAlexNea/llama-index-toc-parser.git
cd llama-index-toc-parser
pip install -e ".[dev,all]"
```

Run tests with:

```bash
tox
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
