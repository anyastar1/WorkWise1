"""
LLM Exporter for document export.

Exports parsed documents to formats optimized for LLM processing,
including structured text, JSON, Markdown, and RAG chunks.
"""

from typing import Dict, Any, List, Optional
import json

from ..models.document import ParsedDocument, TextBlock, TextBlockType


class LLMExporter:
    """
    Exporter for LLM-optimized document formats.
    
    Provides multiple export formats:
    - Structured text with optional coordinates and styles
    - JSON (full or compact)
    - Markdown
    - Retrieval chunks for RAG systems
    - Semantic sections
    """
    
    @staticmethod
    def to_structured_text(doc: ParsedDocument, 
                           include_coords: bool = True,
                           include_styles: bool = False,
                           include_block_types: bool = True) -> str:
        """
        Export to structured text format.
        
        Optimal for most LLM tasks.
        
        Args:
            doc: Parsed document
            include_coords: Include position coordinates
            include_styles: Include style information
            include_block_types: Include block type markers
            
        Returns:
            Structured text string
        """
        lines = []
        lines.append(f"=== DOCUMENT: {doc.metadata.filename} ===")
        lines.append(f"Format: {doc.metadata.document_type.value.upper()}")
        lines.append(f"Pages: {doc.metadata.total_pages}")
        lines.append("")
        
        for page in doc.pages:
            lines.append(f"--- PAGE {page.info.page_number} ({page.info.width:.0f}x{page.info.height:.0f}) ---")
            
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                block_line = LLMExporter._format_block(
                    block, include_coords, include_styles, include_block_types
                )
                lines.append(block_line)
            
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_block(block: TextBlock, 
                      include_coords: bool, 
                      include_styles: bool,
                      include_block_types: bool) -> str:
        """Format a single block."""
        parts = []
        
        # Block type prefix
        if include_block_types:
            type_prefix = {
                TextBlockType.HEADING: f"[H{block.semantic_level or 1}]",
                TextBlockType.LIST_ITEM: "[LI]",
                TextBlockType.PARAGRAPH: "[P]",
                TextBlockType.TABLE_CELL: "[TC]",
                TextBlockType.CAPTION: "[CAP]",
                TextBlockType.HEADER: "[HDR]",
                TextBlockType.FOOTER: "[FTR]"
            }
            parts.append(type_prefix.get(block.block_type, "[?]"))
        
        # Coordinates
        if include_coords:
            b = block.bbox
            parts.append(f"@({b.x0:.0f},{b.y0:.0f})-({b.x1:.0f},{b.y1:.0f})")
            parts.append(f"[{b.width:.0f}x{b.height:.0f}]")
        
        # Style (optional)
        if include_styles and block.lines:
            style = block.lines[0].dominant_style
            if style:
                parts.append(f"<{style.font_name},{style.font_size:.0f}pt,{style.color}>")
        
        # Text
        parts.append(block.text.replace("\n", " ↵ "))
        
        return " ".join(parts)
    
    @staticmethod
    def to_json(doc: ParsedDocument, compact: bool = False) -> str:
        """
        Export to JSON format.
        
        Full information for programmatic processing.
        
        Args:
            doc: Parsed document
            compact: Use compact JSON format (no indentation)
            
        Returns:
            JSON string
        """
        data = doc.to_dict()
        
        if compact:
            return json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def to_markdown(doc: ParsedDocument) -> str:
        """
        Export to Markdown format.
        
        Good for visual representation.
        
        Args:
            doc: Parsed document
            
        Returns:
            Markdown string
        """
        lines = []
        
        for page in doc.pages:
            if page.info.page_number > 1:
                lines.append("\n---\n")  # Page separator
            
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                if block.block_type == TextBlockType.HEADING:
                    level = block.semantic_level or 1
                    lines.append(f"{'#' * level} {block.text}")
                elif block.block_type == TextBlockType.LIST_ITEM:
                    # Clean up existing list markers
                    text = block.text.lstrip("•-–●○▪◦ ")
                    lines.append(f"- {text}")
                else:
                    lines.append(block.text)
                
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def to_retrieval_chunks(doc: ParsedDocument, 
                            max_chunk_size: int = 500,
                            overlap: int = 50,
                            include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Split into chunks for RAG systems.
        
        Each chunk contains text and metadata about position.
        
        Args:
            doc: Parsed document
            max_chunk_size: Maximum chunk size in characters
            overlap: Overlap between chunks
            include_metadata: Include position metadata
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        chunk_id = 0
        
        for page in doc.pages:
            current_chunk_text = []
            current_chunk_blocks = []
            current_size = 0
            
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                block_text = block.text
                block_size = len(block_text)
                
                if current_size + block_size > max_chunk_size and current_chunk_text:
                    # Save current chunk
                    chunk = {
                        "chunk_id": chunk_id,
                        "text": "\n".join(current_chunk_text),
                        "page": page.info.page_number,
                        "block_ids": [b.block_id for b in current_chunk_blocks],
                    }
                    
                    if include_metadata:
                        chunk["bbox"] = {
                            "x0": min(b.bbox.x0 for b in current_chunk_blocks),
                            "y0": min(b.bbox.y0 for b in current_chunk_blocks),
                            "x1": max(b.bbox.x1 for b in current_chunk_blocks),
                            "y1": max(b.bbox.y1 for b in current_chunk_blocks)
                        }
                        chunk["block_types"] = [b.block_type.value for b in current_chunk_blocks]
                    
                    chunks.append(chunk)
                    chunk_id += 1
                    
                    # Overlap: take last block
                    if overlap > 0 and current_chunk_blocks:
                        last_block = current_chunk_blocks[-1]
                        current_chunk_text = [last_block.text[-overlap:]]
                        current_chunk_blocks = [last_block]
                        current_size = len(current_chunk_text[0])
                    else:
                        current_chunk_text = []
                        current_chunk_blocks = []
                        current_size = 0
                
                current_chunk_text.append(block_text)
                current_chunk_blocks.append(block)
                current_size += block_size
            
            # Save last chunk of page
            if current_chunk_text:
                chunk = {
                    "chunk_id": chunk_id,
                    "text": "\n".join(current_chunk_text),
                    "page": page.info.page_number,
                    "block_ids": [b.block_id for b in current_chunk_blocks],
                }
                
                if include_metadata:
                    chunk["bbox"] = {
                        "x0": min(b.bbox.x0 for b in current_chunk_blocks),
                        "y0": min(b.bbox.y0 for b in current_chunk_blocks),
                        "x1": max(b.bbox.x1 for b in current_chunk_blocks),
                        "y1": max(b.bbox.y1 for b in current_chunk_blocks)
                    }
                    chunk["block_types"] = [b.block_type.value for b in current_chunk_blocks]
                
                chunks.append(chunk)
                chunk_id += 1
        
        return chunks
    
    @staticmethod
    def to_semantic_sections(doc: ParsedDocument) -> List[Dict[str, Any]]:
        """
        Split document into semantic sections based on headings.
        
        Each section starts with a heading and contains all following
        content until the next heading of same or higher level.
        
        Args:
            doc: Parsed document
            
        Returns:
            List of section dictionaries
        """
        sections = []
        current_section = None
        
        for page in doc.pages:
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                if block.block_type == TextBlockType.HEADING:
                    # Save previous section if exists
                    if current_section:
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        "heading": block.text,
                        "heading_level": block.semantic_level or 1,
                        "text": "",
                        "blocks": [],
                        "page_start": page.info.page_number,
                        "page_end": page.info.page_number,
                    }
                else:
                    # Add content to current section
                    if current_section is None:
                        # Content before first heading
                        current_section = {
                            "heading": None,
                            "heading_level": 0,
                            "text": "",
                            "blocks": [],
                            "page_start": page.info.page_number,
                            "page_end": page.info.page_number,
                        }
                    
                    if current_section["text"]:
                        current_section["text"] += "\n\n"
                    current_section["text"] += block.text
                    current_section["blocks"].append(block.block_id)
                    current_section["page_end"] = page.info.page_number
        
        # Add last section
        if current_section:
            sections.append(current_section)
        
        return sections
