# document_processor.py - Модуль для преобразования документов в изображения

import os
import io
import base64
import tempfile
import shutil
from PIL import Image
from typing import List, Tuple, Optional

# Попытка импорта библиотек для работы с PDF
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDF не установлен. Установите: pip install PyMuPDF")

try:
    from pdf2image import convert_from_path

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    print("pdf2image не установлен. Установите: pip install pdf2image")

# Для работы с DOCX
try:
    from docx import Document

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("python-docx не установлен. Установите: pip install python-docx")

# Для конвертации DOCX в PDF
try:
    from docx2pdf import convert as docx_to_pdf_convert

    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False
    print("docx2pdf не установлен. Установите: pip install docx2pdf")


class DocumentProcessor:
    """Класс для обработки документов и преобразования их в изображения."""

    def __init__(self, dpi: int = 150, max_pages: int = 50):
        """
        Инициализация процессора документов.

        Args:
            dpi: Разрешение для преобразования PDF в изображения
            max_pages: Максимальное количество страниц для обработки
        """
        self.dpi = dpi
        self.max_pages = max_pages
        self.temp_dir = None

    def _create_temp_dir(self) -> str:
        """Создаёт временную директорию для файлов."""
        if self.temp_dir is None or not os.path.exists(self.temp_dir):
            self.temp_dir = tempfile.mkdtemp(prefix="workwise_")
        return self.temp_dir

    def _cleanup_temp_dir(self):
        """Удаляет временную директорию."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"Ошибка при удалении временной директории: {e}")
            self.temp_dir = None

    def get_file_extension(self, filename: str) -> str:
        """Возвращает расширение файла в нижнем регистре."""
        return os.path.splitext(filename)[1].lower()

    def is_supported_format(self, filename: str) -> bool:
        """Проверяет, поддерживается ли формат файла."""
        ext = self.get_file_extension(filename)
        return ext in [".pdf", ". docx", ".doc"]

    def pdf_to_images_pymupdf(self, pdf_path: str) -> List[Image.Image]:
        """
        Преобразует PDF в список изображений с помощью PyMuPDF.

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Список PIL Image объектов
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF не установлен")

        images = []
        doc = fitz.open(pdf_path)

        try:
            page_count = min(len(doc), self.max_pages)

            for page_num in range(page_count):
                page = doc[page_num]

                # Увеличиваем разрешение для лучшего качества
                zoom = self.dpi / 72  # 72 - стандартное разрешение PDF
                mat = fitz.Matrix(zoom, zoom)

                # Рендерим страницу в изображение
                pix = page.get_pixmap(matrix=mat)

                # Преобразуем в PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

                print(f"Обработана страница {page_num + 1}/{page_count}")
        finally:
            doc.close()

        return images

    def pdf_to_images_pdf2image(self, pdf_path: str) -> List[Image.Image]:
        """
        Преобразует PDF в список изображений с помощью pdf2image.

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Список PIL Image объектов
        """
        if not PDF2IMAGE_AVAILABLE:
            raise ImportError("pdf2image не установлен")

        images = convert_from_path(
            pdf_path, dpi=self.dpi, first_page=1, last_page=self.max_pages
        )

        return images

    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        Преобразует PDF в список изображений.
        Использует PyMuPDF как основной метод, pdf2image как запасной.

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Список PIL Image объектов
        """
        # Сначала пробуем PyMuPDF (быстрее и не требует внешних зависимостей)
        if PYMUPDF_AVAILABLE:
            try:
                return self.pdf_to_images_pymupdf(pdf_path)
            except Exception as e:
                print(f"Ошибка PyMuPDF: {e}, пробуем pdf2image...")

        # Запасной вариант - pdf2image
        if PDF2IMAGE_AVAILABLE:
            try:
                return self.pdf_to_images_pdf2image(pdf_path)
            except Exception as e:
                print(f"Ошибка pdf2image: {e}")
                raise

        raise ImportError(
            "Не установлены библиотеки для работы с PDF.  Установите PyMuPDF или pdf2image."
        )

    def docx_to_pdf(self, docx_path: str) -> str:
        """
        Преобразует DOCX в PDF.

        Args:
            docx_path: Путь к DOCX файлу

        Returns:
            Путь к созданному PDF файлу
        """
        temp_dir = self._create_temp_dir()
        pdf_filename = os.path.splitext(os.path.basename(docx_path))[0] + ". pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        if DOCX2PDF_AVAILABLE:
            try:
                docx_to_pdf_convert(docx_path, pdf_path)
                return pdf_path
            except Exception as e:
                print(f"Ошибка docx2pdf: {e}")
                # Попробуем альтернативный метод

        # Альтернативный метод через LibreOffice (если установлен)
        try:
            import subprocess

            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_dir,
                    docx_path,
                ],
                capture_output=True,
                timeout=60,
            )

            if os.path.exists(pdf_path):
                return pdf_path
        except Exception as e:
            print(f"Ошибка LibreOffice: {e}")

        raise RuntimeError(
            "Не удалось преобразовать DOCX в PDF.  Установите docx2pdf или LibreOffice."
        )

    def docx_to_images(self, docx_path: str) -> List[Image.Image]:
        """
        Преобразует DOCX в список изображений.

        Args:
            docx_path: Путь к DOCX файлу

        Returns:
            Список PIL Image объектов
        """
        # Сначала конвертируем DOCX в PDF
        pdf_path = self.docx_to_pdf(docx_path)

        # Затем PDF в изображения
        return self.pdf_to_images(pdf_path)

    def file_to_images(self, file_path: str) -> List[Image.Image]:
        """
        Преобразует файл (PDF или DOCX) в список изображений.

        Args:
            file_path: Путь к файлу

        Returns:
            Список PIL Image объектов
        """
        ext = self.get_file_extension(file_path)

        if ext == ".pdf":
            return self.pdf_to_images(file_path)
        elif ext in [".docx", ".doc"]:
            return self.docx_to_images(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {ext}")

    def image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """
        Преобразует PIL Image в base64 строку.

        Args:
            image: PIL Image объект
            format: Формат изображения (PNG, JPEG)

        Returns:
            Base64 закодированная строка
        """
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def images_to_base64_list(
        self, images: List[Image.Image], format: str = "PNG"
    ) -> List[str]:
        """
        Преобразует список изображений в список base64 строк.

        Args:
            images: Список PIL Image объектов
            format: Формат изображений

        Returns:
            Список base64 закодированных строк
        """
        return [self.image_to_base64(img, format) for img in images]

    def process_document(self, file_path: str) -> Tuple[List[Image.Image], List[str]]:
        """
        Обрабатывает документ: преобразует в изображения и base64.

        Args:
            file_path: Путь к файлу

        Returns:
            Кортеж (список изображений, список base64 строк)
        """
        try:
            images = self.file_to_images(file_path)
            base64_images = self.images_to_base64_list(images)
            return images, base64_images
        finally:
            # Очищаем временные файлы
            self._cleanup_temp_dir()

    def extract_text_from_images(self, images: List[Image.Image]) -> str:
        """
        Извлекает текст из изображений с помощью OCR (если доступен).

        Args:
            images: Список PIL Image объектов

        Returns:
            Извлечённый текст
        """
        try:
            import pytesseract

            texts = []
            for i, img in enumerate(images):
                text = pytesseract.image_to_string(img, lang="rus+eng")
                texts.append(f"--- Страница {i + 1} ---\n{text}")

            return "\n\n".join(texts)
        except ImportError:
            print("pytesseract не установлен. OCR недоступен.")
            return ""
        except Exception as e:
            print(f"Ошибка OCR: {e}")
            return ""


# Функция-хелпер для быстрого использования
def process_document_to_images(
    file_path: str, dpi: int = 150
) -> Tuple[List[Image.Image], List[str]]:
    """
    Быстрая функция для обработки документа.

    Args:
        file_path: Путь к файлу
        dpi: Разрешение изображений

    Returns:
        Кортеж (список изображений, список base64 строк)
    """
    processor = DocumentProcessor(dpi=dpi)
    return processor.process_document(file_path)
