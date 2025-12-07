"""
Сервис обработки документов.

Отвечает за:
1. Конвертацию страниц документа в изображения
2. Парсинг структуры документа в JSON/Markdown
3. Сохранение результатов в БД
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image

from database import Document, DocumentPage, get_session


class DocumentProcessor:
    """Сервис обработки документов"""
    
    UPLOADS_DIR = "uploads"
    DPI = 150  # Разрешение для конвертации в изображения
    IMAGE_FORMAT = "PNG"
    
    def __init__(self, uploads_dir: str = None):
        self.uploads_dir = uploads_dir or self.UPLOADS_DIR
        os.makedirs(self.uploads_dir, exist_ok=True)
    
    def process_document(self, file_path: str, user_id: int) -> Document:
        """
        Полная обработка документа.
        
        Args:
            file_path: Путь к загруженному файлу
            user_id: ID пользователя
            
        Returns:
            Document: Созданная запись документа
        """
        # 1. Вычисляем хеш файла
        file_hash = self._calculate_file_hash(file_path)
        
        # 2. Создаём папку для документа
        doc_folder = os.path.join(self.uploads_dir, file_hash)
        images_folder = os.path.join(doc_folder, "pages")
        os.makedirs(images_folder, exist_ok=True)
        
        # 3. Получаем информацию о файле
        file_info = self._get_file_info(file_path)
        
        # 3.1. Сохраняем копию оригинального файла
        import shutil
        original_copy_path = os.path.join(doc_folder, f"original.{file_info['type']}")
        shutil.copy2(file_path, original_copy_path)
        
        # 4. Конвертируем страницы в изображения
        page_images = self._convert_to_images(file_path, images_folder)
        
        # 5. Парсим структуру документа
        structure_json, structure_markdown = self._parse_document_structure(file_path)
        
        # 6. Сохраняем в БД
        session = get_session()
        try:
            document = Document(
                user_id=user_id,
                original_filename=file_info['filename'],
                file_hash=file_hash,
                file_size=file_info['size'],
                document_type=file_info['type'],
                images_folder=images_folder,
                structure_json=structure_json,
                structure_markdown=structure_markdown,
                total_pages=len(page_images),
                created_at=datetime.utcnow()
            )
            session.add(document)
            session.flush()
            
            # Добавляем страницы
            structure_data = json.loads(structure_json) if structure_json else {}
            pages_data = structure_data.get('pages', [])
            
            for i, (page_num, image_path) in enumerate(page_images):
                page_info = pages_data[i]['info'] if i < len(pages_data) else {}
                
                doc_page = DocumentPage(
                    document_id=document.id,
                    page_number=page_num,
                    image_path=image_path,
                    width=page_info.get('width'),
                    height=page_info.get('height')
                )
                session.add(doc_page)
            
            session.commit()
            session.refresh(document)
            return document
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Вычисление SHA-256 хеша файла"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _get_file_info(self, file_path: str) -> dict:
        """Получение информации о файле"""
        path = Path(file_path)
        return {
            'filename': path.name,
            'size': path.stat().st_size,
            'type': path.suffix.lower().lstrip('.')
        }
    
    def _convert_to_images(self, file_path: str, output_folder: str) -> list:
        """
        Конвертация страниц документа в изображения.
        
        Returns:
            list: Список кортежей (номер_страницы, путь_к_изображению)
        """
        pages = []
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            pages = self._convert_pdf_to_images(file_path, output_folder)
        elif ext == '.docx':
            # Сначала конвертируем DOCX в PDF, затем в изображения
            pdf_path = self._convert_docx_to_pdf(file_path, output_folder)
            if pdf_path:
                pages = self._convert_pdf_to_images(pdf_path, output_folder)
                # Удаляем временный PDF
                try:
                    os.remove(pdf_path)
                except:
                    pass
        
        return pages
    
    def _convert_pdf_to_images(self, pdf_path: str, output_folder: str) -> list:
        """Конвертация PDF в изображения"""
        pages = []
        doc = fitz.open(pdf_path)
        
        try:
            zoom = self.DPI / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)
                
                image_filename = f"page_{page_num + 1:04d}.png"
                image_path = os.path.join(output_folder, image_filename)
                
                pix.save(image_path)
                pages.append((page_num + 1, image_path))
                
        finally:
            doc.close()
        
        return pages
    
    def _convert_docx_to_pdf(self, docx_path: str, output_folder: str) -> Optional[str]:
        """Конвертация DOCX в PDF через LibreOffice"""
        import subprocess
        
        pdf_filename = Path(docx_path).stem + ".pdf"
        pdf_path = os.path.join(output_folder, pdf_filename)
        
        try:
            # Пробуем LibreOffice
            result = subprocess.run([
                'libreoffice', '--headless', '--convert-to', 'pdf',
                '--outdir', output_folder, docx_path
            ], capture_output=True, timeout=120)
            
            if os.path.exists(pdf_path):
                return pdf_path
        except:
            pass
        
        return None
    
    def _parse_document_structure(self, file_path: str) -> Tuple[str, str]:
        """
        Парсинг структуры документа в JSON и Markdown.
        
        Returns:
            tuple: (json_string, markdown_string)
        """
        try:
            # Импортируем парсер
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            
            from utils.document_parser.parsers import ParserFactory
            from utils.document_parser.exporters.llm_exporter import LLMExporter
            
            # Парсим документ
            document = ParserFactory.parse(file_path)
            
            # Экспортируем в JSON
            json_str = LLMExporter.to_json(document, compact=False)
            
            # Экспортируем в Markdown
            markdown_str = LLMExporter.to_markdown(document)
            
            return json_str, markdown_str
            
        except Exception as e:
            import traceback
            print(f"Ошибка парсинга через document_parser: {e}")
            traceback.print_exc()
            
            # Fallback: парсим напрямую через PyMuPDF
            return self._parse_pdf_fallback(file_path)
    
    def _parse_pdf_fallback(self, file_path: str) -> Tuple[str, str]:
        """Fallback парсинг PDF напрямую через PyMuPDF"""
        try:
            ext = Path(file_path).suffix.lower()
            if ext != '.pdf':
                # Для DOCX без document_parser создаём минимальную структуру
                return self._create_minimal_structure(file_path)
            
            doc = fitz.open(file_path)
            
            pages = []
            markdown_parts = []
            block_counter = 0
            
            for page_num, page in enumerate(doc, 1):
                page_width = page.rect.width
                page_height = page.rect.height
                
                blocks = []
                text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                
                for block_data in text_dict.get("blocks", []):
                    if block_data.get("type") != 0:  # Только текстовые блоки
                        continue
                    
                    block_counter += 1
                    block_id = f"blk_p{page_num}_{block_counter}"
                    
                    lines = []
                    full_text = []
                    
                    for line_data in block_data.get("lines", []):
                        spans = []
                        line_text = []
                        
                        for span_data in line_data.get("spans", []):
                            text = span_data.get("text", "")
                            if not text:
                                continue
                            
                            line_text.append(text)
                            
                            # Цвет
                            color_int = span_data.get("color", 0)
                            color_hex = f"#{color_int:06x}".upper()
                            
                            # Флаги стиля
                            flags = span_data.get("flags", 0)
                            is_bold = bool(flags & 16)
                            is_italic = bool(flags & 2)
                            
                            spans.append({
                                "text": text,
                                "style": {
                                    "font_name": span_data.get("font", "unknown"),
                                    "font_size": span_data.get("size", 12.0),
                                    "font_weight": "bold" if is_bold else "normal",
                                    "font_style": "italic" if is_italic else "normal",
                                    "color": color_hex,
                                    "background_color": None,
                                    "is_underline": bool(flags & 4),
                                    "is_strikethrough": bool(flags & 8),
                                    "line_spacing": None,
                                    "letter_spacing": None
                                },
                                "bbox": {
                                    "x0": round(span_data["bbox"][0], 2),
                                    "y0": round(span_data["bbox"][1], 2),
                                    "x1": round(span_data["bbox"][2], 2),
                                    "y1": round(span_data["bbox"][3], 2),
                                    "width": round(span_data["bbox"][2] - span_data["bbox"][0], 2),
                                    "height": round(span_data["bbox"][3] - span_data["bbox"][1], 2)
                                }
                            })
                        
                        if spans:
                            lines.append({
                                "text": "".join(line_text),
                                "spans": spans,
                                "bbox": {
                                    "x0": round(line_data["bbox"][0], 2),
                                    "y0": round(line_data["bbox"][1], 2),
                                    "x1": round(line_data["bbox"][2], 2),
                                    "y1": round(line_data["bbox"][3], 2),
                                    "width": round(line_data["bbox"][2] - line_data["bbox"][0], 2),
                                    "height": round(line_data["bbox"][3] - line_data["bbox"][1], 2)
                                },
                                "baseline_y": None
                            })
                            full_text.append("".join(line_text))
                    
                    if lines:
                        block_text = "\n".join(full_text)
                        
                        # Определяем тип блока
                        first_span = lines[0]["spans"][0] if lines[0]["spans"] else {}
                        font_size = first_span.get("style", {}).get("font_size", 12)
                        is_bold = first_span.get("style", {}).get("font_weight") == "bold"
                        
                        block_type = "paragraph"
                        semantic_level = None
                        if font_size > 14 or is_bold:
                            block_type = "heading"
                            semantic_level = 1 if font_size >= 18 else 2 if font_size >= 14 else 3
                        
                        blocks.append({
                            "block_id": block_id,
                            "block_type": block_type,
                            "text": block_text,
                            "lines": lines,
                            "bbox": {
                                "x0": round(block_data["bbox"][0], 2),
                                "y0": round(block_data["bbox"][1], 2),
                                "x1": round(block_data["bbox"][2], 2),
                                "y1": round(block_data["bbox"][3], 2),
                                "width": round(block_data["bbox"][2] - block_data["bbox"][0], 2),
                                "height": round(block_data["bbox"][3] - block_data["bbox"][1], 2)
                            },
                            "page_number": page_num,
                            "reading_order": len(blocks),
                            "semantic_level": semantic_level,
                            "line_count": len(lines),
                            "avg_line_spacing": None
                        })
                        
                        # Markdown
                        if block_type == "heading":
                            markdown_parts.append(f"{'#' * (semantic_level or 1)} {block_text}")
                        else:
                            markdown_parts.append(block_text)
                
                pages.append({
                    "info": {
                        "page_number": page_num,
                        "width": round(page_width, 2),
                        "height": round(page_height, 2),
                        "rotation": page.rotation
                    },
                    "blocks": blocks,
                    "block_count": len(blocks)
                })
            
            doc.close()
            
            # Формируем итоговую структуру
            structure = {
                "metadata": {
                    "filename": Path(file_path).name,
                    "document_type": "pdf",
                    "total_pages": len(pages),
                    "file_size_bytes": Path(file_path).stat().st_size,
                    "title": None,
                    "author": None,
                    "creation_date": None,
                    "modification_date": None,
                    "content_hash": None
                },
                "pages": pages,
                "summary": {
                    "total_blocks": block_counter,
                    "total_pages": len(pages)
                }
            }
            
            json_str = json.dumps(structure, ensure_ascii=False, indent=2)
            markdown_str = "\n\n".join(markdown_parts)
            
            return json_str, markdown_str
            
        except Exception as e:
            import traceback
            print(f"Ошибка fallback парсинга: {e}")
            traceback.print_exc()
            return self._create_minimal_structure(file_path)
    
    def _create_minimal_structure(self, file_path: str) -> Tuple[str, str]:
        """Создание минимальной структуры документа"""
        structure = {
            "metadata": {
                "filename": Path(file_path).name,
                "document_type": Path(file_path).suffix.lower().lstrip('.'),
                "total_pages": 1,
                "file_size_bytes": Path(file_path).stat().st_size,
                "title": None,
                "author": None,
                "creation_date": None,
                "modification_date": None,
                "content_hash": None
            },
            "pages": [{
                "info": {
                    "page_number": 1,
                    "width": 595.0,
                    "height": 842.0,
                    "rotation": 0
                },
                "blocks": [],
                "block_count": 0
            }],
            "summary": {
                "total_blocks": 0,
                "total_pages": 1
            }
        }
        
        return json.dumps(structure, ensure_ascii=False, indent=2), ""
    
    def get_document_structure(self, document: Document) -> dict:
        """Получение структуры документа как dict"""
        if document.structure_json:
            return json.loads(document.structure_json)
        return {}
    
    @staticmethod
    def get_page_image_url(page: DocumentPage) -> str:
        """Получение URL изображения страницы"""
        return f"/uploads/{os.path.basename(os.path.dirname(page.image_path))}/pages/{os.path.basename(page.image_path)}"
    
    @staticmethod
    def get_page_with_errors_url(page: DocumentPage) -> Optional[str]:
        """Получение URL изображения страницы с ошибками"""
        if page.image_with_errors_path:
            folder = os.path.basename(os.path.dirname(os.path.dirname(page.image_with_errors_path)))
            return f"/uploads/{folder}/errors/{os.path.basename(page.image_with_errors_path)}"
        return None
