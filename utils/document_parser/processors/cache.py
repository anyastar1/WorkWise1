"""
Document caching system.

Provides caching for parsed documents to avoid re-parsing
unchanged files.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from src.models.document import (
    ParsedDocument,
    DocumentMetadata,
    DocumentPage,
    PageInfo,
    TextBlock,
    TextBlockType,
    TextLine,
    TextSpan,
    TextStyle,
    BoundingBox,
    DocumentType,
)


logger = logging.getLogger(__name__)


class DocumentCache:
    """
    File-based cache for parsed documents.
    
    Caches parsed documents as JSON files to avoid re-parsing.
    Uses file path and modification time for cache key generation.
    """
    
    def __init__(
        self,
        cache_dir: str = ".doc_cache",
        max_size_mb: float = 100.0,
    ):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        
        logger.debug(f"Document cache initialized at {self.cache_dir}")
    
    def _get_cache_key(self, filepath: Path) -> str:
        """Generate cache key from file path and metadata."""
        filepath = filepath.resolve()
        
        try:
            stat = filepath.stat()
            key_data = f"{filepath}:{stat.st_size}:{stat.st_mtime}"
        except OSError:
            key_data = str(filepath)
        
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, filepath: Path) -> Path:
        """Get cache file path for a document."""
        key = self._get_cache_key(filepath)
        return self.cache_dir / f"{key}.json"
    
    def get(self, filepath: Path) -> Optional[ParsedDocument]:
        """
        Get cached document if available.
        
        Args:
            filepath: Original document path
            
        Returns:
            ParsedDocument or None if not cached
        """
        cache_path = self._get_cache_path(filepath)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Failed to load cache for {filepath}: {e}")
            # Remove corrupted cache file
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None
    
    def set(self, filepath: Path, document: ParsedDocument) -> bool:
        """
        Cache a parsed document.
        
        Args:
            filepath: Original document path
            document: Parsed document to cache
            
        Returns:
            True if cached successfully
        """
        cache_path = self._get_cache_path(filepath)
        
        try:
            # Check cache size and clean if necessary
            self._ensure_cache_size()
            
            data = document.to_dict()
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            logger.debug(f"Cached document: {filepath}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to cache {filepath}: {e}")
            return False
    
    def invalidate(self, filepath: Path) -> bool:
        """
        Remove cached document.
        
        Args:
            filepath: Original document path
            
        Returns:
            True if cache entry was removed
        """
        cache_path = self._get_cache_path(filepath)
        
        if cache_path.exists():
            try:
                cache_path.unlink()
                return True
            except OSError:
                pass
        
        return False
    
    def clear(self) -> int:
        """
        Clear all cached documents.
        
        Returns:
            Number of cache entries removed
        """
        count = 0
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        
        logger.info(f"Cleared {count} cache entries")
        return count
    
    def _ensure_cache_size(self) -> None:
        """Remove old cache entries if size limit exceeded."""
        cache_files = list(self.cache_dir.glob("*.json"))
        
        if not cache_files:
            return
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in cache_files)
        
        if total_size <= self.max_size_bytes:
            return
        
        # Sort by modification time (oldest first)
        cache_files.sort(key=lambda f: f.stat().st_mtime)
        
        # Remove oldest files until under limit
        for cache_file in cache_files:
            if total_size <= self.max_size_bytes * 0.8:  # 80% threshold
                break
            
            file_size = cache_file.stat().st_size
            try:
                cache_file.unlink()
                total_size -= file_size
                logger.debug(f"Removed old cache entry: {cache_file.name}")
            except OSError:
                pass
    
    def _deserialize(self, data: Dict[str, Any]) -> ParsedDocument:
        """Deserialize document from dictionary."""
        # Deserialize metadata
        meta_data = data.get("metadata", {})
        metadata = DocumentMetadata(
            filename=meta_data.get("filename", "unknown"),
            document_type=DocumentType(meta_data.get("document_type", "pdf")),
            total_pages=meta_data.get("total_pages", 0),
            file_size_bytes=meta_data.get("file_size_bytes", 0),
            title=meta_data.get("title"),
            author=meta_data.get("author"),
            creation_date=meta_data.get("creation_date"),
            modification_date=meta_data.get("modification_date"),
            content_hash=meta_data.get("content_hash"),
        )
        
        # Deserialize pages
        pages = []
        for page_data in data.get("pages", []):
            page = self._deserialize_page(page_data)
            pages.append(page)
        
        return ParsedDocument(metadata=metadata, pages=pages)
    
    def _deserialize_page(self, data: Dict[str, Any]) -> DocumentPage:
        """Deserialize a page from dictionary."""
        info_data = data.get("info", {})
        info = PageInfo(
            page_number=info_data.get("page_number", 1),
            width=info_data.get("width", 595.0),
            height=info_data.get("height", 842.0),
            rotation=info_data.get("rotation", 0),
        )
        
        blocks = []
        for block_data in data.get("blocks", []):
            block = self._deserialize_block(block_data)
            blocks.append(block)
        
        return DocumentPage(info=info, blocks=blocks)
    
    def _deserialize_block(self, data: Dict[str, Any]) -> TextBlock:
        """Deserialize a text block from dictionary."""
        bbox_data = data.get("bbox", {})
        bbox = BoundingBox(
            x0=bbox_data.get("x0", 0),
            y0=bbox_data.get("y0", 0),
            x1=bbox_data.get("x1", 0),
            y1=bbox_data.get("y1", 0),
        )
        
        lines = []
        for line_data in data.get("lines", []):
            line = self._deserialize_line(line_data)
            lines.append(line)
        
        return TextBlock(
            block_id=data.get("block_id", ""),
            block_type=TextBlockType(data.get("block_type", "paragraph")),
            lines=lines,
            bbox=bbox,
            page_number=data.get("page_number", 1),
            reading_order=data.get("reading_order", 0),
            semantic_level=data.get("semantic_level"),
        )
    
    def _deserialize_line(self, data: Dict[str, Any]) -> TextLine:
        """Deserialize a text line from dictionary."""
        bbox_data = data.get("bbox", {})
        bbox = BoundingBox(
            x0=bbox_data.get("x0", 0),
            y0=bbox_data.get("y0", 0),
            x1=bbox_data.get("x1", 0),
            y1=bbox_data.get("y1", 0),
        )
        
        spans = []
        for span_data in data.get("spans", []):
            span = self._deserialize_span(span_data)
            spans.append(span)
        
        return TextLine(
            spans=spans,
            bbox=bbox,
            baseline_y=data.get("baseline_y"),
        )
    
    def _deserialize_span(self, data: Dict[str, Any]) -> TextSpan:
        """Deserialize a text span from dictionary."""
        style_data = data.get("style", {})
        style = TextStyle(
            font_name=style_data.get("font_name", "unknown"),
            font_size=style_data.get("font_size", 12.0),
            font_weight=style_data.get("font_weight", "normal"),
            font_style=style_data.get("font_style", "normal"),
            color=style_data.get("color", "#000000"),
            background_color=style_data.get("background_color"),
            is_underline=style_data.get("is_underline", False),
            is_strikethrough=style_data.get("is_strikethrough", False),
            line_spacing=style_data.get("line_spacing"),
            letter_spacing=style_data.get("letter_spacing"),
        )
        
        bbox_data = data.get("bbox", {})
        bbox = BoundingBox(
            x0=bbox_data.get("x0", 0),
            y0=bbox_data.get("y0", 0),
            x1=bbox_data.get("x1", 0),
            y1=bbox_data.get("y1", 0),
        )
        
        return TextSpan(
            text=data.get("text", ""),
            style=style,
            bbox=bbox,
        )


class MemoryCache:
    """
    In-memory cache for parsed documents.
    
    Faster than file-based cache but limited by memory.
    """
    
    def __init__(self, max_items: int = 100):
        """
        Initialize memory cache.
        
        Args:
            max_items: Maximum number of cached documents
        """
        self.max_items = max_items
        self._cache: Dict[str, ParsedDocument] = {}
        self._access_order: List[str] = []
    
    def _get_key(self, filepath: Path) -> str:
        """Generate cache key."""
        filepath = filepath.resolve()
        try:
            stat = filepath.stat()
            return f"{filepath}:{stat.st_mtime}"
        except OSError:
            return str(filepath)
    
    def get(self, filepath: Path) -> Optional[ParsedDocument]:
        """Get cached document."""
        key = self._get_key(filepath)
        
        if key in self._cache:
            # Update access order (LRU)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        
        return None
    
    def set(self, filepath: Path, document: ParsedDocument) -> None:
        """Cache document."""
        key = self._get_key(filepath)
        
        # Remove oldest if at capacity
        while len(self._cache) >= self.max_items:
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]
        
        self._cache[key] = document
        self._access_order.append(key)
    
    def clear(self) -> int:
        """Clear cache."""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        return count
