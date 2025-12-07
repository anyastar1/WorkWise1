"""
Document models for the Document Analysis System.

Contains dataclasses for representing parsed documents with full
information about positioning, styles, and text formatting.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum


class DocumentType(Enum):
    """Type of document."""
    PDF = "pdf"
    DOCX = "docx"


class TextBlockType(Enum):
    """Type of text block."""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE_CELL = "table_cell"
    CAPTION = "caption"
    FOOTER = "footer"
    HEADER = "header"


@dataclass
class BoundingBox:
    """
    Bounding box coordinates for a text element relative to page.
    
    Attributes:
        x0: Left boundary (from left edge of page)
        y0: Top boundary (from top of page)
        x1: Right boundary
        y1: Bottom boundary
    """
    x0: float
    y0: float
    x1: float
    y1: float
    
    @property
    def width(self) -> float:
        """Width of the bounding box."""
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        """Height of the bounding box."""
        return self.y1 - self.y0
    
    @property
    def center(self) -> Tuple[float, float]:
        """Center point of the bounding box."""
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)
    
    @property
    def area(self) -> float:
        """Area of the bounding box."""
        return self.width * self.height
    
    def contains(self, other: "BoundingBox") -> bool:
        """Check if this bbox contains another bbox."""
        return (self.x0 <= other.x0 and 
                self.y0 <= other.y0 and 
                self.x1 >= other.x1 and 
                self.y1 >= other.y1)
    
    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this bbox overlaps with another bbox."""
        return (self.x0 < other.x1 and 
                self.x1 > other.x0 and 
                self.y0 < other.y1 and 
                self.y1 > other.y0)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2)
        }


@dataclass
class TextStyle:
    """
    Style characteristics of text.
    
    Attributes:
        font_name: Font name
        font_size: Font size in pt
        font_weight: Weight (normal, bold)
        font_style: Style (normal, italic)
        color: Color in HEX format
        background_color: Background color in HEX format
        is_underline: Whether text is underlined
        is_strikethrough: Whether text has strikethrough
        line_spacing: Line spacing
        letter_spacing: Letter spacing
    """
    font_name: str
    font_size: float
    font_weight: str = "normal"
    font_style: str = "normal"
    color: str = "#000000"
    background_color: Optional[str] = None
    is_underline: bool = False
    is_strikethrough: bool = False
    line_spacing: Optional[float] = None
    letter_spacing: Optional[float] = None
    
    @property
    def is_bold(self) -> bool:
        """Check if text is bold."""
        return self.font_weight == "bold"
    
    @property
    def is_italic(self) -> bool:
        """Check if text is italic."""
        return self.font_style == "italic"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "font_name": self.font_name,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "font_style": self.font_style,
            "color": self.color,
            "background_color": self.background_color,
            "is_underline": self.is_underline,
            "is_strikethrough": self.is_strikethrough,
            "line_spacing": self.line_spacing,
            "letter_spacing": self.letter_spacing
        }


@dataclass
class TextSpan:
    """
    Minimal unit of text with uniform style.
    
    Attributes:
        text: The text content
        style: Text style
        bbox: Bounding box
    """
    text: str
    style: TextStyle
    bbox: BoundingBox
    
    def __len__(self) -> int:
        """Return length of text."""
        return len(self.text)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "style": self.style.to_dict(),
            "bbox": self.bbox.to_dict()
        }


@dataclass
class TextLine:
    """
    Line of text (may contain multiple spans with different styles).
    
    Attributes:
        spans: List of text spans
        bbox: Bounding box for the line
        baseline_y: Y-coordinate of baseline
    """
    spans: List[TextSpan]
    bbox: BoundingBox
    baseline_y: Optional[float] = None
    
    @property
    def text(self) -> str:
        """Full text of the line."""
        return "".join(span.text for span in self.spans)
    
    @property
    def char_count(self) -> int:
        """Total character count."""
        return sum(len(span.text) for span in self.spans)
    
    @property
    def dominant_style(self) -> Optional[TextStyle]:
        """Dominant style (by text length)."""
        if not self.spans:
            return None
        return max(self.spans, key=lambda s: len(s.text)).style
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "spans": [span.to_dict() for span in self.spans],
            "bbox": self.bbox.to_dict(),
            "baseline_y": self.baseline_y
        }


@dataclass
class TextBlock:
    """
    Text block (paragraph, heading, etc.).
    
    Attributes:
        block_id: Unique identifier
        block_type: Type of block
        lines: List of text lines
        bbox: Bounding box
        page_number: Page number
        reading_order: Reading order on page
        semantic_level: Heading level (1-6) if heading
    """
    block_id: str
    block_type: TextBlockType
    lines: List[TextLine]
    bbox: BoundingBox
    page_number: int
    reading_order: int
    semantic_level: Optional[int] = None
    
    @property
    def text(self) -> str:
        """Full text of the block."""
        return "\n".join(line.text for line in self.lines)
    
    @property
    def line_count(self) -> int:
        """Number of lines in the block."""
        return len(self.lines)
    
    @property
    def avg_line_spacing(self) -> Optional[float]:
        """Average line spacing."""
        if len(self.lines) < 2:
            return None
        spacings = []
        for i in range(1, len(self.lines)):
            spacing = self.lines[i].bbox.y0 - self.lines[i-1].bbox.y1
            spacings.append(spacing)
        return sum(spacings) / len(spacings)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "block_id": self.block_id,
            "block_type": self.block_type.value,
            "text": self.text,
            "lines": [line.to_dict() for line in self.lines],
            "bbox": self.bbox.to_dict(),
            "page_number": self.page_number,
            "reading_order": self.reading_order,
            "semantic_level": self.semantic_level,
            "line_count": self.line_count,
            "avg_line_spacing": self.avg_line_spacing
        }


@dataclass
class PageInfo:
    """
    Page information.
    
    Attributes:
        page_number: Page number (1-indexed)
        width: Page width in pt
        height: Page height in pt
        rotation: Page rotation in degrees
    """
    page_number: int
    width: float
    height: float
    rotation: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_number": self.page_number,
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "rotation": self.rotation
        }


@dataclass
class DocumentPage:
    """
    Document page.
    
    Attributes:
        info: Page information
        blocks: List of text blocks
    """
    info: PageInfo
    blocks: List[TextBlock] = field(default_factory=list)
    
    @property
    def block_count(self) -> int:
        """Number of blocks on the page."""
        return len(self.blocks)
    
    def get_blocks_by_type(self, block_type: TextBlockType) -> List[TextBlock]:
        """Get all blocks of a specific type."""
        return [b for b in self.blocks if b.block_type == block_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "info": self.info.to_dict(),
            "blocks": [block.to_dict() for block in self.blocks]
        }


@dataclass
class DocumentMetadata:
    """
    Document metadata.
    
    Attributes:
        filename: File name
        document_type: Document type (PDF/DOCX)
        total_pages: Total number of pages
        file_size_bytes: File size in bytes
        title: Document title
        author: Document author
        creation_date: Creation date
        modification_date: Modification date
        content_hash: Content hash
    """
    filename: str
    document_type: DocumentType
    total_pages: int
    file_size_bytes: int
    title: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    content_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "document_type": self.document_type.value,
            "total_pages": self.total_pages,
            "file_size_bytes": self.file_size_bytes,
            "title": self.title,
            "author": self.author,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "content_hash": self.content_hash
        }


@dataclass
class ParsedDocument:
    """
    Fully parsed document.
    
    Attributes:
        metadata: Document metadata
        pages: List of document pages
    """
    metadata: DocumentMetadata
    pages: List[DocumentPage]
    
    @property
    def total_blocks(self) -> int:
        """Total number of blocks in the document."""
        return sum(len(page.blocks) for page in self.pages)
    
    @property
    def full_text(self) -> str:
        """Full text of the document."""
        texts = []
        for page in self.pages:
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                texts.append(block.text)
        return "\n\n".join(texts)
    
    def get_blocks_by_type(self, block_type: TextBlockType) -> List[TextBlock]:
        """Get all blocks of a specific type across all pages."""
        result = []
        for page in self.pages:
            result.extend([b for b in page.blocks if b.block_type == block_type])
        return result
    
    def get_headings(self) -> List[TextBlock]:
        """Get all heading blocks."""
        return self.get_blocks_by_type(TextBlockType.HEADING)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "pages": [page.to_dict() for page in self.pages],
            "summary": {
                "total_blocks": self.total_blocks,
                "total_pages": len(self.pages)
            }
        }
    
    def to_llm_context(self, 
                       include_coordinates: bool = True,
                       max_length: Optional[int] = None) -> str:
        """
        Export to LLM-optimized format.
        
        Args:
            include_coordinates: Include position coordinates
            max_length: Maximum output length (truncates with "...")
            
        Returns:
            Structured text optimized for LLM processing
        """
        output = []
        output.append(f"# Document: {self.metadata.filename}")
        output.append(f"Type: {self.metadata.document_type.value.upper()}")
        output.append(f"Pages: {self.metadata.total_pages}")
        output.append("---\n")
        
        for page in self.pages:
            output.append(f"## Page {page.info.page_number}")
            
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                prefix = ""
                if block.block_type == TextBlockType.HEADING:
                    level = block.semantic_level or 1
                    prefix = "#" * (level + 2) + " "
                elif block.block_type == TextBlockType.LIST_ITEM:
                    prefix = "• "
                
                if include_coordinates:
                    bbox = block.bbox
                    coord_info = f"[pos: ({bbox.x0:.0f},{bbox.y0:.0f})-({bbox.x1:.0f},{bbox.y1:.0f})]"
                    output.append(f"{prefix}{block.text} {coord_info}")
                else:
                    output.append(f"{prefix}{block.text}")
                
                output.append("")
        
        result = "\n".join(output)
        
        if max_length and len(result) > max_length:
            return result[:max_length - 3] + "..."
        
        return result
