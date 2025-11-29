"""
Утилиты для визуализации ошибок ГОСТ на изображениях страниц
"""

import os
import json
import logging
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def visualize_gost_errors(image_path: str, pages_data: List[Dict], output_path: Optional[str] = None) -> str:
    """
    Визуализирует ошибки ГОСТ на изображении страницы
    
    Args:
        image_path: Путь к исходному изображению страницы
        pages_data: Список данных о страницах из JSON отчета ГОСТ
        output_path: Путь для сохранения обработанного изображения (если None, создается автоматически)
    
    Returns:
        Путь к сохраненному изображению с визуализацией ошибок
    """
    try:
        # Загружаем изображение
        if not os.path.exists(image_path):
            logger.error(f"[VISUALIZER] Изображение не найдено: {image_path}")
            return image_path
        
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Получаем размеры изображения
        img_width, img_height = img.size
        
        # Ищем данные для текущей страницы
        # Определяем номер страницы из имени файла или используем первый элемент pages_data
        page_number = None
        page_data = None
        
        # Пытаемся извлечь номер страницы из имени файла
        filename = os.path.basename(image_path)
        try:
            # Формат может быть разным, например: page_1.png, page1.png, 1.png
            import re
            match = re.search(r'(\d+)', filename)
            if match:
                page_number = int(match.group(1))
        except:
            pass
        
        # Если не удалось определить из имени файла, используем первый элемент
        if page_number is None and pages_data:
            page_number = pages_data[0].get('page', 1)
        
        # Ищем данные для этой страницы
        for page_item in pages_data:
            if page_item.get('page') == page_number:
                page_data = page_item
                break
        
        # Если не нашли, используем первый элемент
        if not page_data and pages_data:
            page_data = pages_data[0]
        
        if not page_data:
            logger.warning(f"[VISUALIZER] Данные для страницы {page_number} не найдены")
            return image_path
        
        # Проверяем, есть ли ошибка на этой странице
        gosterror = page_data.get('gosterror', '').strip()
        if not gosterror:
            logger.info(f"[VISUALIZER] На странице {page_number} нет ошибок ГОСТ")
            return image_path
        
        # Получаем координаты ошибки
        position_x = float(page_data.get('positionX', 0))
        position_y = float(page_data.get('positionY', 0))
        width = float(page_data.get('width', 0))
        height = float(page_data.get('height', 0))
        
        # Если координаты нулевые, не рисуем метку
        if position_x == 0 and position_y == 0 and width == 0 and height == 0:
            logger.info(f"[VISUALIZER] Координаты ошибки нулевые для страницы {page_number}")
            return image_path
        
        # Ограничиваем координаты размерами изображения
        position_x = max(0, min(position_x, img_width))
        position_y = max(0, min(position_y, img_height))
        width = max(0, min(width, img_width - position_x))
        height = max(0, min(height, img_height - position_y))
        
        # Рисуем полупрозрачную красную метку
        # Конвертируем изображение в RGBA для работы с прозрачностью
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Создаем слой для прозрачности
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Красный цвет с прозрачностью (alpha = 128 из 255)
        error_color = (255, 0, 0, 128)
        
        # Рисуем прямоугольник
        overlay_draw.rectangle(
            [position_x, position_y, position_x + width, position_y + height],
            fill=error_color,
            outline=(255, 0, 0, 255),  # Красная рамка без прозрачности
            width=3
        )
        
        # Накладываем слой на изображение
        img = Image.alpha_composite(img, overlay).convert('RGB')
        
        # Определяем путь для сохранения
        if output_path is None:
            # Создаем путь для сохранения обработанного изображения
            base_dir = os.path.dirname(image_path)
            base_name = os.path.basename(image_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(base_dir, f"{name}_gost{ext}")
        
        # Сохраняем изображение
        img.save(output_path, quality=95)
        logger.info(f"[VISUALIZER] Изображение с визуализацией ошибок сохранено: {output_path}")
        
        return output_path
    
    except Exception as e:
        logger.error(f"[VISUALIZER] Ошибка визуализации ошибок ГОСТ: {e}")
        import traceback
        logger.error(f"[VISUALIZER] Трассировка: {traceback.format_exc()}")
        # В случае ошибки возвращаем исходный путь
        return image_path
