"""
Document Analysis CLI Tool.

Command-line interface for parsing and exporting documents.
"""

import argparse
import sys
from pathlib import Path

from src.parsers import ParserFactory
from src.exporters.llm_exporter import LLMExporter


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Document Analysis Tool - Extract structured data from PDF/DOCX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse PDF to JSON
  docanalyze document.pdf -f json -o output.json
  
  # Parse with coordinates in text format
  docanalyze document.pdf -f text --coords -o output.txt
  
  # Parse DOCX to Markdown
  docanalyze document.docx -f markdown -o output.md
  
  # Get chunks for RAG
  docanalyze document.pdf -f chunks --chunk-size 500 -o chunks.json
"""
    )
    
    parser.add_argument(
        'input', 
        type=Path, 
        help='Input PDF or DOCX file'
    )
    parser.add_argument(
        '-o', '--output', 
        type=Path, 
        help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '-f', '--format', 
        choices=['json', 'text', 'markdown', 'chunks', 'sections'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--coords', 
        action='store_true', 
        help='Include coordinates in text output'
    )
    parser.add_argument(
        '--styles', 
        action='store_true',
        help='Include style information in text output'
    )
    parser.add_argument(
        '--no-block-types',
        action='store_true',
        help='Exclude block type markers in text output'
    )
    parser.add_argument(
        '--compact', 
        action='store_true',
        help='Use compact JSON format'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=500,
        help='Maximum chunk size for RAG chunks (default: 500)'
    )
    parser.add_argument(
        '--overlap',
        type=int,
        default=50,
        help='Overlap between chunks (default: 50)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Check input file exists
    if not args.input.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # Check supported format
    ext = args.input.suffix.lower()
    if ext not in ParserFactory.supported_formats():
        print(f"Error: Unsupported format: {ext}", file=sys.stderr)
        print(f"Supported formats: {', '.join(ParserFactory.supported_formats())}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Processing: {args.input}", file=sys.stderr)
    
    try:
        # Parse document
        document = ParserFactory.parse(args.input)
        
        if args.verbose:
            print(f"Pages: {document.metadata.total_pages}", file=sys.stderr)
            print(f"Blocks: {document.total_blocks}", file=sys.stderr)
        
        # Export to desired format
        if args.format == 'json':
            output = LLMExporter.to_json(document, compact=args.compact)
        elif args.format == 'text':
            output = LLMExporter.to_structured_text(
                document, 
                include_coords=args.coords,
                include_styles=args.styles,
                include_block_types=not args.no_block_types
            )
        elif args.format == 'markdown':
            output = LLMExporter.to_markdown(document)
        elif args.format == 'chunks':
            import json
            chunks = LLMExporter.to_retrieval_chunks(
                document,
                max_chunk_size=args.chunk_size,
                overlap=args.overlap
            )
            output = json.dumps(chunks, ensure_ascii=False, indent=2)
        elif args.format == 'sections':
            import json
            sections = LLMExporter.to_semantic_sections(document)
            output = json.dumps(sections, ensure_ascii=False, indent=2)
        
        # Output
        if args.output:
            args.output.write_text(output, encoding='utf-8')
            if args.verbose:
                print(f"Output written to: {args.output}", file=sys.stderr)
        else:
            print(output)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
