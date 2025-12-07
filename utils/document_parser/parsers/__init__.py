"""
Document parsers.

Provides factory for creating appropriate parser based on document format.
"""

from pathlib import Path
from typing import Union, BinaryIO, Optional

from .base import BaseParser
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from src.models.document import ParsedDocument


class ParserFactory:
    """
    Factory for creating document parsers.
    
    Automatically selects the appropriate parser based on file extension
    or format hint.
    """
    
    _parsers = {
        '.pdf': PDFParser,
        '.docx': DOCXParser
    }
    
    @classmethod
    def get_parser(cls, filepath: Union[str, Path]) -> BaseParser:
        """
        Get parser for the given file.
        
        Args:
            filepath: Path to the document file
            
        Returns:
            Appropriate parser instance
            
        Raises:
            ValueError: If format is not supported
        """
        ext = Path(filepath).suffix.lower()
        
        if ext not in cls._parsers:
            raise ValueError(f"Unsupported format: {ext}")
        
        return cls._parsers[ext]()
    
    @classmethod
    def parse(cls, 
              source: Union[str, Path, BinaryIO], 
              format_hint: Optional[str] = None) -> ParsedDocument:
        """
        Universal parsing method.
        
        Args:
            source: Path to file or byte stream
            format_hint: Format hint ('pdf' or 'docx') for stream input
            
        Returns:
            ParsedDocument with extracted content
            
        Raises:
            ValueError: If format cannot be determined
        """
        if isinstance(source, (str, Path)):
            parser = cls.get_parser(source)
        elif format_hint:
            ext = f".{format_hint.lower().strip('.')}"
            if ext not in cls._parsers:
                raise ValueError(f"Unsupported format: {format_hint}")
            parser = cls._parsers[ext]()
        else:
            raise ValueError("format_hint required for stream input")
        
        return parser.parse(source)
    
    @classmethod
    def supported_formats(cls) -> list:
        """Get list of supported file extensions."""
        return list(cls._parsers.keys())


__all__ = [
    "BaseParser",
    "PDFParser",
    "DOCXParser",
    "ParserFactory",
]
