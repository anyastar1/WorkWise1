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
            print(f"Ошибка парсинга документа: {e}")
            return None, None
    
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
