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
        print(f"[ErrorRenderer] Rendering {len(errors)} errors on page {page.page_number}")
        print(f"[ErrorRenderer] Image path: {page.image_path}")
        
        # Проверяем существование файла
        if not os.path.exists(page.image_path):
            print(f"[ErrorRenderer] ERROR: Image file not found: {page.image_path}")
            return page.image_path
        
        # Загружаем исходное изображение
        image = Image.open(page.image_path)
        draw = ImageDraw.Draw(image)
        
        print(f"[ErrorRenderer] Image size: {image.size}")
        
        # Рисуем каждую ошибку
        errors_drawn = 0
        for error in errors:
            if error.bbox_x0 is not None:
                print(f"[ErrorRenderer] Drawing error #{error.error_number}: bbox=({error.bbox_x0:.1f}, {error.bbox_y0:.1f}, {error.bbox_x1:.1f}, {error.bbox_y1:.1f})")
                self._draw_error(draw, error)
                errors_drawn += 1
            else:
                print(f"[ErrorRenderer] Skipping error #{error.error_number}: no bbox")
        
        print(f"[ErrorRenderer] Drew {errors_drawn} errors")
        
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
        print(f"[ErrorRenderer] Saved to: {output_path}")
        
        return output_path
    
    def _draw_error(self, draw: ImageDraw.Draw, error: DocumentError):
        """Отрисовка одной ошибки"""
        # Масштабируем координаты
        x0 = error.bbox_x0 * self.scale_factor
        y0 = error.bbox_y0 * self.scale_factor
        x1 = error.bbox_x1 * self.scale_factor
        y1 = error.bbox_y1 * self.scale_factor
        
        # Проверяем валидность координат
        if x1 <= x0 or y1 <= y0:
            print(f"[WARN] Invalid bbox for error {error.error_number}: ({x0}, {y0}) - ({x1}, {y1})")
            return
        
        # Получаем цвет
        color = self.SEVERITY_COLORS.get(error.severity, self.SEVERITY_COLORS['warning'])
        
        # Полупрозрачная заливка (создаём отдельный слой)
        # Рисуем прямоугольник с толстой рамкой
        for i in range(self.LINE_WIDTH + 2):
            draw.rectangle(
                [(x0 - i, y0 - i), (x1 + i, y1 + i)],
                outline=color
            )
        
        # Рисуем подчёркивание под текстом (волнистая линия)
        underline_y = y1 + 2
        wave_height = 3
        step = 4
        points = []
        x = x0
        up = True
        while x <= x1:
            points.append((x, underline_y + (0 if up else wave_height)))
            x += step
            up = not up
        
        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([points[i], points[i + 1]], fill=color, width=2)
        
        # Рисуем номер ошибки в кружке
        label = str(error.error_number)
        
        # Позиция метки - слева сверху от блока
        label_x = max(5, x0 - 5)
        label_y = max(5, y0 - self.FONT_SIZE - 10)
        
        # Размер текста
        try:
            bbox = draw.textbbox((label_x, label_y), label, font=self._font)
        except:
            # Fallback для старых версий Pillow
            text_width = len(label) * 10
            text_height = self.FONT_SIZE
            bbox = (label_x, label_y, label_x + text_width, label_y + text_height)
        
        padding = 5
        
        # Круглый фон для номера
        circle_x = label_x + (bbox[2] - bbox[0]) // 2
        circle_y = label_y + (bbox[3] - bbox[1]) // 2
        radius = max((bbox[2] - bbox[0]) // 2, (bbox[3] - bbox[1]) // 2) + padding
        
        draw.ellipse(
            [(circle_x - radius, circle_y - radius),
             (circle_x + radius, circle_y + radius)],
            fill=color,
            outline=(255, 255, 255),
            width=2
        )
        
        # Текст номера
        draw.text(
            (label_x, label_y),
            label,
            fill=(255, 255, 255),
            font=self._font
        )
        
        # Линия от номера к области ошибки
        draw.line(
            [(circle_x, circle_y + radius), (x0, y0)],
            fill=color,
            width=2
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
