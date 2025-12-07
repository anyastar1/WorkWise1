"""
PDF Parser using PyMuPDF.

Extracts text with full information about positioning and styles
from PDF documents.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Union, BinaryIO, List, Dict, Optional
import hashlib

from .base import BaseParser
from src.models.document import (
    ParsedDocument,
    DocumentMetadata,
    DocumentType,
    DocumentPage,
    PageInfo,
    TextBlock,
    TextBlockType,
    TextLine,
    TextSpan,
    TextStyle,
    BoundingBox,
)
from src.utils.color_utils import int_to_hex


class PDFParser(BaseParser):
    """
    PDF document parser based on PyMuPDF.
    
    Extracts text with full information about positioning and styles.
    Provides accurate bounding boxes for all text elements.
    """
    
    def __init__(self, dpi: int = 72):
        """
        Initialize PDF parser.
        
        Args:
            dpi: Resolution for coordinate calculations (default 72)
        """
        self.dpi = dpi
        self._block_counter = 0
    
    def parse(self, source: Union[str, Path, BinaryIO]) -> ParsedDocument:
        """
        Parse a PDF document.
        
        Args:
            source: Path to PDF file or binary stream
            
        Returns:
            ParsedDocument with extracted content
        """
        self._block_counter = 0
        
        if isinstance(source, (str, Path)):
            doc = fitz.open(source)
        else:
            doc = fitz.open(stream=source.read(), filetype="pdf")
        
        try:
            metadata = self._extract_metadata(doc, source)
            pages = [self._parse_page(page, page_num) 
                     for page_num, page in enumerate(doc, 1)]
            return ParsedDocument(metadata=metadata, pages=pages)
        finally:
            doc.close()
    
    def _extract_metadata(self, doc: fitz.Document, source) -> DocumentMetadata:
        """Extract document metadata."""
        meta = doc.metadata or {}
        filepath = Path(source) if isinstance(source, (str, Path)) else None
        
        # Calculate content hash
        content_hash = None
        if filepath and filepath.exists():
            with open(filepath, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        
        return DocumentMetadata(
            filename=filepath.name if filepath else "unknown.pdf",
            document_type=DocumentType.PDF,
            total_pages=len(doc),
            file_size_bytes=filepath.stat().st_size if filepath and filepath.exists() else 0,
            title=meta.get("title"),
            author=meta.get("author"),
            creation_date=meta.get("creationDate"),
            modification_date=meta.get("modDate"),
            content_hash=content_hash
        )
    
    def _parse_page(self, page: fitz.Page, page_num: int) -> DocumentPage:
        """Parse a single page."""
        page_info = PageInfo(
            page_number=page_num,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation
        )
        
        # Extract text blocks with full information
        blocks = self._extract_blocks(page, page_num)
        
        return DocumentPage(info=page_info, blocks=blocks)
    
    def _extract_blocks(self, page: fitz.Page, page_num: int) -> List[TextBlock]:
        """
        Extract text blocks using dict extraction.
        
        Returns blocks in reading order.
        """
        # "dict" provides the most detailed information
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        blocks = []
        reading_order = 0
        
        for block_data in text_dict.get("blocks", []):
            if block_data.get("type") != 0:  # Text blocks only
                continue
            
            block = self._parse_block(block_data, page_num, reading_order)
            if block and block.text.strip():
                blocks.append(block)
                reading_order += 1
        
        # Sort by reading order (top-to-bottom, left-to-right)
        blocks = self._sort_by_reading_order(blocks, page.rect.width)
        
        # Update reading_order after sorting
        for i, block in enumerate(blocks):
            block.reading_order = i
        
        return blocks
    
    def _parse_block(self, block_data: Dict, page_num: int, order: int) -> Optional[TextBlock]:
        """Parse a single block."""
        self._block_counter += 1
        block_id = f"blk_p{page_num}_{self._block_counter}"
        
        bbox = BoundingBox(
            x0=block_data["bbox"][0],
            y0=block_data["bbox"][1],
            x1=block_data["bbox"][2],
            y1=block_data["bbox"][3]
        )
        
        lines = []
        for line_data in block_data.get("lines", []):
            line = self._parse_line(line_data)
            if line:
                lines.append(line)
        
        if not lines:
            return None
        
        # Determine block type based on style
        block_type = self._detect_block_type(lines)
        
        return TextBlock(
            block_id=block_id,
            block_type=block_type,
            lines=lines,
            bbox=bbox,
            page_number=page_num,
            reading_order=order,
            semantic_level=self._detect_heading_level(lines) if block_type == TextBlockType.HEADING else None
        )
    
    def _parse_line(self, line_data: Dict) -> Optional[TextLine]:
        """Parse a line with spans."""
        spans = []
        
        for span_data in line_data.get("spans", []):
            span = self._parse_span(span_data)
            if span:
                spans.append(span)
        
        if not spans:
            return None
        
        bbox = BoundingBox(
            x0=line_data["bbox"][0],
            y0=line_data["bbox"][1],
            x1=line_data["bbox"][2],
            y1=line_data["bbox"][3]
        )
        
        return TextLine(
            spans=spans,
            bbox=bbox,
            baseline_y=line_data.get("baseline")
        )
    
    def _parse_span(self, span_data: Dict) -> Optional[TextSpan]:
        """Parse a span (text with uniform style)."""
        text = span_data.get("text", "")
        if not text:
            return None
        
        # Extract color (PyMuPDF returns int)
        color_int = span_data.get("color", 0)
        color_hex = int_to_hex(color_int)
        
        # Determine weight and style from flags
        flags = span_data.get("flags", 0)
        is_bold = bool(flags & 2 ** 4)  # bit 4 = bold
        is_italic = bool(flags & 2 ** 1)  # bit 1 = italic
        
        style = TextStyle(
            font_name=span_data.get("font", "unknown"),
            font_size=span_data.get("size", 12.0),
            font_weight="bold" if is_bold else "normal",
            font_style="italic" if is_italic else "normal",
            color=color_hex,
            is_underline=bool(flags & 2 ** 2),  # bit 2 = underline
            is_strikethrough=bool(flags & 2 ** 3)  # bit 3 = strikethrough
        )
        
        bbox = BoundingBox(
            x0=span_data["bbox"][0],
            y0=span_data["bbox"][1],
            x1=span_data["bbox"][2],
            y1=span_data["bbox"][3]
        )
        
        return TextSpan(text=text, style=style, bbox=bbox)
    
    def _detect_block_type(self, lines: List[TextLine]) -> TextBlockType:
        """Heuristic block type detection."""
        if not lines:
            return TextBlockType.PARAGRAPH
        
        # Check first line
        first_line = lines[0]
        if not first_line.spans:
            return TextBlockType.PARAGRAPH
        
        dominant_style = first_line.dominant_style
        if not dominant_style:
            return TextBlockType.PARAGRAPH
        
        # Large font size or bold = heading
        if dominant_style.font_size > 14 or dominant_style.font_weight == "bold":
            return TextBlockType.HEADING
        
        # List marker
        text = first_line.text.strip()
        if text.startswith(("•", "-", "–", "◦", "▪", "●", "○")) or \
           (len(text) > 2 and text[0].isdigit() and text[1] in ".)"): 
            return TextBlockType.LIST_ITEM
        
        return TextBlockType.PARAGRAPH
    
    def _detect_heading_level(self, lines: List[TextLine]) -> int:
        """Determine heading level by font size."""
        if not lines or not lines[0].spans:
            return 1
        
        size = lines[0].dominant_style.font_size if lines[0].dominant_style else 12
        
        if size >= 24:
            return 1
        elif size >= 18:
            return 2
        elif size >= 14:
            return 3
        else:
            return 4
    
    def _sort_by_reading_order(self, blocks: List[TextBlock], page_width: float) -> List[TextBlock]:
        """
        Sort blocks by reading order.
        
        Handles multi-column layouts.
        """
        if not blocks:
            return blocks
        
        # Detect columns (rough heuristic)
        mid_x = page_width / 2
        left_blocks = [b for b in blocks if b.bbox.center[0] < mid_x]
        right_blocks = [b for b in blocks if b.bbox.center[0] >= mid_x]
        
        # If clear column separation
        if left_blocks and right_blocks:
            left_xs = [b.bbox.x1 for b in left_blocks]
            right_xs = [b.bbox.x0 for b in right_blocks]
            
            if max(left_xs) < min(right_xs) - 20:  # Gap between columns
                left_sorted = sorted(left_blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
                right_sorted = sorted(right_blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
                return left_sorted + right_sorted
        
        # Normal top-to-bottom sorting
        return sorted(blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
    
    def supports_format(self, filepath: Union[str, Path]) -> bool:
        """Check if PDF format is supported."""
        return str(filepath).lower().endswith('.pdf')
