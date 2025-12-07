"""
Base parser class for document parsers.

Defines the abstract interface that all document parsers must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Union

from src.models.document import ParsedDocument


class BaseParser(ABC):
    """
    Abstract base class for document parsers.
    
    All document parsers (PDF, DOCX, etc.) must inherit from this class
    and implement the required methods.
    """
    
    @abstractmethod
    def parse(self, source: Union[str, Path, BinaryIO]) -> ParsedDocument:
        """
        Parse a document from file or stream.
        
        Args:
            source: Path to file or binary stream
            
        Returns:
            ParsedDocument with extracted content
        """
        pass
    
    @abstractmethod
    def supports_format(self, filepath: Union[str, Path]) -> bool:
        """
        Check if this parser supports the given file format.
        
        Args:
            filepath: Path to the file
            
        Returns:
            True if format is supported, False otherwise
        """
        pass
