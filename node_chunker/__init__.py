import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create package logger
logger = logging.getLogger("node_chunker")

from node_chunker.chunks import (
    DocumentFormat,
    chunk_document_by_toc_to_text_nodes,
    get_supported_formats,
)

__all__ = [
    "DocumentFormat",
    "chunk_document_by_toc_to_text_nodes",
    "get_supported_formats",
]
