"""
Async document processor for batch processing.

Provides efficient parallel processing of multiple documents
using ProcessPoolExecutor for CPU-bound parsing operations.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union
import logging

from src.models.document import ParsedDocument


logger = logging.getLogger(__name__)


def _parse_single_document(
    filepath: Union[str, Path],
    parser_type: str = "auto",
) -> Tuple[str, Optional[ParsedDocument], Optional[str]]:
    """
    Parse a single document (for use in executor).
    
    Args:
        filepath: Path to document
        parser_type: 'auto', 'pdf', or 'docx'
        
    Returns:
        Tuple of (filepath, parsed_document, error_message)
    """
    from src.parsers import ParserFactory
    
    filepath = Path(filepath)
    
    try:
        doc = ParserFactory.parse(filepath)
        return (str(filepath), doc, None)
    except Exception as e:
        return (str(filepath), None, str(e))


class AsyncDocumentProcessor:
    """
    Asynchronous processor for batch document processing.
    
    Uses ProcessPoolExecutor for CPU-bound parsing operations
    to achieve true parallelism.
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_processes: bool = True,
    ):
        """
        Initialize async processor.
        
        Args:
            max_workers: Maximum number of parallel workers
            use_processes: Use ProcessPoolExecutor (True) or ThreadPoolExecutor (False)
        """
        self.max_workers = max_workers
        self.use_processes = use_processes
    
    async def process_batch(
        self,
        filepaths: List[Union[str, Path]],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Union[ParsedDocument, str]]:
        """
        Process multiple documents in parallel.
        
        Args:
            filepaths: List of file paths to process
            on_progress: Optional callback(current, total, filepath)
            
        Returns:
            Dict mapping filepath to ParsedDocument or error string
        """
        if not filepaths:
            return {}
        
        loop = asyncio.get_event_loop()
        results = {}
        total = len(filepaths)
        
        # Choose executor type
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                loop.run_in_executor(
                    executor,
                    _parse_single_document,
                    fp,
                    "auto",
                ): fp
                for fp in filepaths
            }
            
            # Process as completed
            completed = 0
            for future in asyncio.as_completed(futures.keys()):
                try:
                    filepath, doc, error = await future
                    
                    if error:
                        results[filepath] = f"Error: {error}"
                        logger.warning(f"Failed to parse {filepath}: {error}")
                    else:
                        results[filepath] = doc
                        logger.debug(f"Successfully parsed {filepath}")
                    
                    completed += 1
                    
                    if on_progress:
                        on_progress(completed, total, filepath)
                        
                except Exception as e:
                    fp = futures[future]
                    results[str(fp)] = f"Error: {str(e)}"
                    logger.error(f"Exception processing {fp}: {e}")
                    completed += 1
        
        return results
    
    async def process_directory(
        self,
        directory: Union[str, Path],
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Union[ParsedDocument, str]]:
        """
        Process all documents in a directory.
        
        Args:
            directory: Directory path
            extensions: File extensions to process (default: ['.pdf', '.docx'])
            recursive: Search subdirectories
            on_progress: Progress callback
            
        Returns:
            Dict mapping filepath to ParsedDocument or error string
        """
        directory = Path(directory)
        
        if extensions is None:
            extensions = ['.pdf', '.docx']
        
        # Normalize extensions
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        
        # Find all matching files
        filepaths = []
        pattern = "**/*" if recursive else "*"
        
        for ext in extensions:
            filepaths.extend(directory.glob(f"{pattern}{ext}"))
        
        logger.info(f"Found {len(filepaths)} documents in {directory}")
        
        return await self.process_batch(filepaths, on_progress)


class DocumentProcessor:
    """
    Synchronous document processor with caching support.
    
    Provides a simpler interface for single-document processing
    with optional caching.
    """
    
    def __init__(self, cache: Optional["DocumentCache"] = None):
        """
        Initialize processor.
        
        Args:
            cache: Optional cache instance
        """
        self.cache = cache
    
    def process(
        self,
        filepath: Union[str, Path],
        use_cache: bool = True,
    ) -> ParsedDocument:
        """
        Process a single document.
        
        Args:
            filepath: Path to document
            use_cache: Whether to use cache
            
        Returns:
            ParsedDocument
        """
        from src.parsers import ParserFactory
        
        filepath = Path(filepath)
        
        # Try cache first
        if use_cache and self.cache:
            cached = self.cache.get(filepath)
            if cached:
                logger.debug(f"Cache hit for {filepath}")
                return cached
        
        # Parse document
        doc = ParserFactory.parse(filepath)
        
        # Store in cache
        if use_cache and self.cache:
            self.cache.set(filepath, doc)
        
        return doc
    
    def process_batch(
        self,
        filepaths: List[Union[str, Path]],
        use_cache: bool = True,
    ) -> Dict[str, Union[ParsedDocument, str]]:
        """
        Process multiple documents synchronously.
        
        Args:
            filepaths: List of file paths
            use_cache: Whether to use cache
            
        Returns:
            Dict mapping filepath to ParsedDocument or error string
        """
        results = {}
        
        for fp in filepaths:
            try:
                doc = self.process(fp, use_cache=use_cache)
                results[str(fp)] = doc
            except Exception as e:
                results[str(fp)] = f"Error: {str(e)}"
        
        return results
