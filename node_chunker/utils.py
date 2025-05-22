"""
Utility functions for document chunking operations.
"""
import logging
import os
import tempfile
from typing import Optional

import requests

logger = logging.getLogger(__name__)

def download_temp_file(url: str, suffix: Optional[str] = None) -> str:
    """
    Download content from a URL to a temporary file.
    
    Args:
        url: The URL to download from
        suffix: Optional file suffix (e.g., '.pdf', '.docx')
        
    Returns:
        Path to the temporary file
        
    Raises:
        ValueError: If the download fails
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return temp_path
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        logger.error(f"Error downloading from {url}: {str(e)}")
        raise ValueError(f"Failed to download file: {str(e)}")

def read_file_content(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read content from a file with proper error handling.
    
    Args:
        file_path: Path to the file
        encoding: Character encoding (default utf-8)
        
    Returns:
        Content of the file as string
        
    Raises:
        ValueError: If the file cannot be read
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        raise ValueError(f"Failed to read file {file_path}: {str(e)}")
