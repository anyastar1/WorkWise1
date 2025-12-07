"""
Сервис рисования ошибок на изображениях страниц.

Использует Pillow для отрисовки прямоугольников ошибок и номеров.
"""

import os
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from database import Document, DocumentPage, DocumentError


class ErrorRenderer:
    """
    Рендерер ошибок на изображениях страниц документа.
    
    Отрисовывает красные прямоугольники вокруг областей с ошибками
    и добавляет номера ошибок.
    """
    
    # Цвета для разных уровней серьезности
    SEVERITY_COLORS = {
        'error': (255, 0, 0),      # Красный
        'warning': (255, 165, 0),  # Оранжевый
        'info': (0, 100, 255)      # Синий
    }
    
    # Толщина линий
    LINE_WIDTH = 3
    
    # Размер шрифта для номера ошибки
    FONT_SIZE = 20
    
    def __init__(self, dpi: int = 150):
        """
        Args:
            dpi: Разрешение изображений (для масштабирования координат)
        """
        self.dpi = dpi
        self.scale_factor = dpi / 72.0  # Координаты в PDF в 72 dpi
        
        # Пытаемся загрузить шрифт
        self._font = None
        try:
            # Попробуем стандартные шрифты
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
            for path in font_paths:
                if os.path.exists(path):
                    self._font = ImageFont.truetype(path, self.FONT_SIZE)
                    break
        except:
            pass
        
        if self._font is None:
            self._font = ImageFont.load_default()
    
    def render_errors_on_page(self, 
                              page: DocumentPage, 
                              errors: List[DocumentError],
                              output_path: Optional[str] = None) -> str:
        """
        Отрисовка ошибок на изображении страницы.
        
        Args:
            page: Модель страницы документа
            errors: Список ошибок для этой страницы
            output_path: Путь для сохранения (если None - генерируется автоматически)
            
        Returns:
            str: Путь к изображению с ошибками
        """
        # Загружаем исходное изображение
        image = Image.open(page.image_path)
        draw = ImageDraw.Draw(image)
        
        # Рисуем каждую ошибку
        for error in errors:
            if error.bbox_x0 is not None:
                self._draw_error(draw, error)
        
        # Определяем путь для сохранения
        if output_path is None:
            # Создаём папку errors рядом с pages
            pages_dir = os.path.dirname(page.image_path)
            errors_dir = os.path.join(os.path.dirname(pages_dir), "errors")
            os.makedirs(errors_dir, exist_ok=True)
            
            filename = os.path.basename(page.image_path)
            output_path = os.path.join(errors_dir, f"errors_{filename}")
        
        # Сохраняем
        image.save(output_path)
        return output_path
    
    def _draw_error(self, draw: ImageDraw.Draw, error: DocumentError):
        """Отрисовка одной ошибки"""
        # Масштабируем координаты
        x0 = error.bbox_x0 * self.scale_factor
        y0 = error.bbox_y0 * self.scale_factor
        x1 = error.bbox_x1 * self.scale_factor
        y1 = error.bbox_y1 * self.scale_factor
        
        # Получаем цвет
        color = self.SEVERITY_COLORS.get(error.severity, self.SEVERITY_COLORS['warning'])
        
        # Рисуем прямоугольник
        for i in range(self.LINE_WIDTH):
            draw.rectangle(
                [(x0 - i, y0 - i), (x1 + i, y1 + i)],
                outline=color
            )
        
        # Рисуем номер ошибки
        label = str(error.error_number)
        
        # Фон для номера
        label_x = x0 - 5
        label_y = y0 - self.FONT_SIZE - 5
        
        # Размер текста
        bbox = draw.textbbox((label_x, label_y), label, font=self._font)
        padding = 3
        
        # Прямоугольник-фон для номера
        draw.rectangle(
            [(bbox[0] - padding, bbox[1] - padding),
             (bbox[2] + padding, bbox[3] + padding)],
            fill=color
        )
        
        # Текст номера
        draw.text(
            (label_x, label_y),
            label,
            fill=(255, 255, 255),
            font=self._font
        )
    
    def render_all_pages(self, document: Document) -> List[str]:
        """
        Отрисовка ошибок на всех страницах документа.
        
        Args:
            document: Модель документа
            
        Returns:
            list: Список путей к изображениям с ошибками
        """
        result_paths = []
        
        # Группируем ошибки по страницам
        errors_by_page = {}
        for error in document.errors:
            page_id = error.page_id
            if page_id not in errors_by_page:
                errors_by_page[page_id] = []
            errors_by_page[page_id].append(error)
        
        # Рендерим каждую страницу
        for page in document.pages:
            page_errors = errors_by_page.get(page.id, [])
            
            if page_errors:
                output_path = self.render_errors_on_page(page, page_errors)
                page.image_with_errors_path = output_path
                result_paths.append(output_path)
            else:
                # Если ошибок нет, просто копируем оригинал
                result_paths.append(page.image_path)
        
        return result_paths
    
    @staticmethod
    def get_scale_factor(dpi: int = 150) -> float:
        """Получить коэффициент масштабирования"""
        return dpi / 72.0
