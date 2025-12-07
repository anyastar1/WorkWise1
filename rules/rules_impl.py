"""
Реализация правил проверки документов.

Каждое правило проверяет определенный аспект оформления документа
согласно заданным параметрам.
"""

import re
from typing import List, Optional, Set
from .base import BaseRule, RuleResult, RuleError


class BoundsRule(BaseRule):
    """
    Правило 5: Проверка выхода текстовых блоков за границы документа.
    
    Проверяет, что все текстовые блоки находятся в пределах страницы.
    """
    
    name = "Проверка границ документа"
    code = "bounds_check"
    description = "Проверяет, не выходят ли текстовые блоки за границы страницы"
    weight = 1.0
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        for page in document_structure.get('pages', []):
            page_info = page.get('info', {})
            page_num = page_info.get('page_number', 0)
            page_width = page_info.get('width', 595)
            page_height = page_info.get('height', 842)
            
            for block in page.get('blocks', []):
                bbox = block.get('bbox', {})
                x0 = bbox.get('x0', 0)
                y0 = bbox.get('y0', 0)
                x1 = bbox.get('x1', 0)
                y1 = bbox.get('y1', 0)
                
                issues = []
                if x0 < 0:
                    issues.append(f"выходит за левую границу ({x0:.1f})")
                if y0 < 0:
                    issues.append(f"выходит за верхнюю границу ({y0:.1f})")
                if x1 > page_width:
                    issues.append(f"выходит за правую границу ({x1:.1f} > {page_width:.1f})")
                if y1 > page_height:
                    issues.append(f"выходит за нижнюю границу ({y1:.1f} > {page_height:.1f})")
                
                if issues:
                    errors.append(RuleError(
                        page_number=page_num,
                        message=f"Текстовый блок {', '.join(issues)}",
                        severity="error",
                        bbox=(x0, y0, x1, y1),
                        block_id=block.get('block_id')
                    ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors
        )


class FontRule(BaseRule):
    """
    Правило 6: Проверка шрифта текстовых блоков.
    
    Проверяет вхождение шрифтов в разрешенный список (с поддержкой regex).
    """
    
    name = "Проверка шрифта"
    code = "font_check"
    description = "Проверяет, что шрифт входит в список разрешенных"
    weight = 0.8
    
    def __init__(self, allowed_fonts: List[str] = None):
        """
        Args:
            allowed_fonts: Список разрешенных шрифтов (поддерживает regex)
                          Пример: ["Times New Roman", "Arial", "Times.*"]
        """
        self.allowed_fonts = allowed_fonts or [
            r"Times.*",
            r"Arial.*",
            r"Calibri.*",
            r"PT.*",
            r"Liberation.*"
        ]
        self._patterns = [re.compile(f, re.IGNORECASE) for f in self.allowed_fonts]
    
    def _is_font_allowed(self, font_name: str) -> bool:
        """Проверка, разрешен ли шрифт"""
        for pattern in self._patterns:
            if pattern.search(font_name):
                return True
        return False
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        checked_fonts: Set[str] = set()
        
        for page in document_structure.get('pages', []):
            page_num = page.get('info', {}).get('page_number', 0)
            
            for block in page.get('blocks', []):
                bbox = block.get('bbox', {})
                
                for span in self.get_all_spans(block):
                    style = span.get('style', {})
                    font_name = style.get('font_name', 'unknown')
                    
                    # Проверяем каждый уникальный шрифт один раз на странице
                    key = f"{page_num}_{font_name}"
                    if key in checked_fonts:
                        continue
                    checked_fonts.add(key)
                    
                    if not self._is_font_allowed(font_name):
                        span_bbox = span.get('bbox', bbox)
                        errors.append(RuleError(
                            page_number=page_num,
                            message=f"Недопустимый шрифт: '{font_name}'. Разрешены: {', '.join(self.allowed_fonts)}",
                            severity="warning",
                            bbox=(span_bbox.get('x0'), span_bbox.get('y0'),
                                  span_bbox.get('x1'), span_bbox.get('y1')),
                            block_id=block.get('block_id'),
                            extra_data={'font_name': font_name}
                        ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors
        )


class FontSizeRule(BaseRule):
    """
    Правило 7: Проверка размера текста.
    
    Проверяет, что размер шрифта находится в заданном диапазоне.
    """
    
    name = "Проверка размера шрифта"
    code = "font_size_check"
    description = "Проверяет размер шрифта в заданном диапазоне"
    weight = 0.7
    
    def __init__(self, min_size: float = 13.5, max_size: float = 14.5):
        """
        Args:
            min_size: Минимальный размер шрифта в pt
            max_size: Максимальный размер шрифта в pt
        """
        self.min_size = min_size
        self.max_size = max_size
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        for page in document_structure.get('pages', []):
            page_num = page.get('info', {}).get('page_number', 0)
            
            for block in page.get('blocks', []):
                # Пропускаем заголовки - у них может быть другой размер
                if block.get('block_type') == 'heading':
                    continue
                
                bbox = block.get('bbox', {})
                
                for span in self.get_all_spans(block):
                    style = span.get('style', {})
                    font_size = style.get('font_size', 12)
                    
                    if font_size < self.min_size or font_size > self.max_size:
                        span_bbox = span.get('bbox', bbox)
                        errors.append(RuleError(
                            page_number=page_num,
                            message=f"Размер шрифта {font_size:.1f}pt вне диапазона {self.min_size}-{self.max_size}pt",
                            severity="warning",
                            bbox=(span_bbox.get('x0'), span_bbox.get('y0'),
                                  span_bbox.get('x1'), span_bbox.get('y1')),
                            block_id=block.get('block_id'),
                            extra_data={'font_size': font_size}
                        ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors,
            stats={'min_size': self.min_size, 'max_size': self.max_size}
        )


class ColorRule(BaseRule):
    """
    Правило 8: Проверка цвета текста.
    
    Проверяет, что цвет текста входит в допустимый набор цветов.
    """
    
    name = "Проверка цвета текста"
    code = "color_check"
    description = "Проверяет, что цвет текста допустим"
    weight = 0.5
    
    def __init__(self, allowed_colors: List[str] = None):
        """
        Args:
            allowed_colors: Список разрешенных цветов в HEX формате
                           Пример: ["#000000", "#333333"]
        """
        self.allowed_colors = [c.upper() for c in (allowed_colors or ["#000000"])]
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        for page in document_structure.get('pages', []):
            page_num = page.get('info', {}).get('page_number', 0)
            
            for block in page.get('blocks', []):
                bbox = block.get('bbox', {})
                
                for span in self.get_all_spans(block):
                    style = span.get('style', {})
                    color = style.get('color', '#000000').upper()
                    
                    if color not in self.allowed_colors:
                        span_bbox = span.get('bbox', bbox)
                        errors.append(RuleError(
                            page_number=page_num,
                            message=f"Недопустимый цвет текста: {color}. Разрешены: {', '.join(self.allowed_colors)}",
                            severity="info",
                            bbox=(span_bbox.get('x0'), span_bbox.get('y0'),
                                  span_bbox.get('x1'), span_bbox.get('y1')),
                            block_id=block.get('block_id'),
                            extra_data={'color': color}
                        ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors
        )


class LineSpacingRule(BaseRule):
    """
    Правило 9: Проверка межстрочного интервала.
    
    Проверяет, что межстрочный интервал находится в заданном диапазоне.
    """
    
    name = "Проверка межстрочного интервала"
    code = "line_spacing_check"
    description = "Проверяет межстрочный интервал"
    weight = 0.6
    
    def __init__(self, min_spacing: float = 1.2, max_spacing: float = 1.5):
        """
        Args:
            min_spacing: Минимальный межстрочный интервал
            max_spacing: Максимальный межстрочный интервал
        """
        self.min_spacing = min_spacing
        self.max_spacing = max_spacing
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        for page in document_structure.get('pages', []):
            page_num = page.get('info', {}).get('page_number', 0)
            
            for block in page.get('blocks', []):
                avg_spacing = block.get('avg_line_spacing')
                
                if avg_spacing is None:
                    continue
                
                # Нормализуем интервал относительно размера шрифта
                # Типичный шрифт 14pt, интервал 1.5 = 21pt между строками
                spans = self.get_all_spans(block)
                if not spans:
                    continue
                
                avg_font_size = sum(s.get('style', {}).get('font_size', 14) for s in spans) / len(spans)
                normalized_spacing = avg_spacing / avg_font_size if avg_font_size > 0 else 0
                
                if normalized_spacing < self.min_spacing or normalized_spacing > self.max_spacing:
                    bbox = block.get('bbox', {})
                    errors.append(RuleError(
                        page_number=page_num,
                        message=f"Межстрочный интервал {normalized_spacing:.2f} вне диапазона {self.min_spacing}-{self.max_spacing}",
                        severity="warning",
                        bbox=(bbox.get('x0'), bbox.get('y0'),
                              bbox.get('x1'), bbox.get('y1')),
                        block_id=block.get('block_id'),
                        extra_data={'line_spacing': normalized_spacing}
                    ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors
        )


class MarginsRule(BaseRule):
    """
    Правило 10: Проверка полей документа.
    
    Проверяет, что текст не выходит за разрешенные поля.
    """
    
    name = "Проверка полей документа"
    code = "margins_check"
    description = "Проверяет соблюдение полей документа"
    weight = 0.9
    
    def __init__(self, 
                 margin_left: float = 85,      # ~30mm при 72dpi
                 margin_right: float = 42,     # ~15mm
                 margin_top: float = 57,       # ~20mm
                 margin_bottom: float = 57):   # ~20mm
        """
        Args:
            margin_left: Левое поле в pt (по умолчанию 30мм)
            margin_right: Правое поле в pt (по умолчанию 15мм)
            margin_top: Верхнее поле в pt (по умолчанию 20мм)
            margin_bottom: Нижнее поле в pt (по умолчанию 20мм)
        """
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        for page in document_structure.get('pages', []):
            page_info = page.get('info', {})
            page_num = page_info.get('page_number', 0)
            page_width = page_info.get('width', 595)
            page_height = page_info.get('height', 842)
            
            # Границы контентной области
            content_left = self.margin_left
            content_right = page_width - self.margin_right
            content_top = self.margin_top
            content_bottom = page_height - self.margin_bottom
            
            for block in page.get('blocks', []):
                # Пропускаем колонтитулы
                block_type = block.get('block_type', '')
                if block_type in ('header', 'footer'):
                    continue
                
                bbox = block.get('bbox', {})
                x0 = bbox.get('x0', 0)
                y0 = bbox.get('y0', 0)
                x1 = bbox.get('x1', 0)
                y1 = bbox.get('y1', 0)
                
                issues = []
                if x0 < content_left - 2:  # Небольшой допуск
                    issues.append(f"выходит за левое поле")
                if x1 > content_right + 2:
                    issues.append(f"выходит за правое поле")
                if y0 < content_top - 2:
                    issues.append(f"выходит за верхнее поле")
                if y1 > content_bottom + 2:
                    issues.append(f"выходит за нижнее поле")
                
                if issues:
                    errors.append(RuleError(
                        page_number=page_num,
                        message=f"Текст {', '.join(issues)}",
                        severity="warning",
                        bbox=(x0, y0, x1, y1),
                        block_id=block.get('block_id')
                    ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors,
            stats={
                'margin_left': self.margin_left,
                'margin_right': self.margin_right,
                'margin_top': self.margin_top,
                'margin_bottom': self.margin_bottom
            }
        )


class HeadingRule(BaseRule):
    """
    Правило 11: Проверка заголовка на странице.
    
    Проверяет наличие и расположение заголовка.
    """
    
    name = "Проверка заголовка"
    code = "heading_check"
    description = "Проверяет наличие и расположение заголовка"
    weight = 0.7
    
    def __init__(self,
                 expected_y_min: float = 50,
                 expected_y_max: float = 150,
                 allowed_y_min: float = 40,
                 allowed_y_max: float = 200,
                 check_first_page_only: bool = False):
        """
        Args:
            expected_y_min: Ожидаемая минимальная Y-координата заголовка
            expected_y_max: Ожидаемая максимальная Y-координата заголовка
            allowed_y_min: Допустимая минимальная Y-координата
            allowed_y_max: Допустимая максимальная Y-координата
            check_first_page_only: Проверять только первую страницу
        """
        self.expected_y_min = expected_y_min
        self.expected_y_max = expected_y_max
        self.allowed_y_min = allowed_y_min
        self.allowed_y_max = allowed_y_max
        self.check_first_page_only = check_first_page_only
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        
        pages = document_structure.get('pages', [])
        pages_to_check = pages[:1] if self.check_first_page_only else pages
        
        for page in pages_to_check:
            page_num = page.get('info', {}).get('page_number', 0)
            
            # Находим заголовки на странице
            headings = [b for b in page.get('blocks', []) 
                       if b.get('block_type') == 'heading']
            
            if not headings:
                # На первой странице заголовок обязателен
                if page_num == 1:
                    errors.append(RuleError(
                        page_number=page_num,
                        message="На первой странице отсутствует заголовок",
                        severity="warning"
                    ))
                continue
            
            # Проверяем первый заголовок (главный)
            main_heading = headings[0]
            bbox = main_heading.get('bbox', {})
            y0 = bbox.get('y0', 0)
            
            if y0 < self.allowed_y_min or y0 > self.allowed_y_max:
                errors.append(RuleError(
                    page_number=page_num,
                    message=f"Заголовок находится вне допустимой зоны (Y={y0:.0f}, допустимо {self.allowed_y_min}-{self.allowed_y_max})",
                    severity="error",
                    bbox=(bbox.get('x0'), bbox.get('y0'),
                          bbox.get('x1'), bbox.get('y1')),
                    block_id=main_heading.get('block_id')
                ))
            elif y0 < self.expected_y_min or y0 > self.expected_y_max:
                errors.append(RuleError(
                    page_number=page_num,
                    message=f"Заголовок не в ожидаемой позиции (Y={y0:.0f}, ожидалось {self.expected_y_min}-{self.expected_y_max})",
                    severity="info",
                    bbox=(bbox.get('x0'), bbox.get('y0'),
                          bbox.get('x1'), bbox.get('y1')),
                    block_id=main_heading.get('block_id')
                ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors
        )


class PageNumberRule(BaseRule):
    """
    Правило 12: Проверка нумерации страниц.
    
    Проверяет наличие и корректность нумерации страниц.
    """
    
    name = "Проверка нумерации страниц"
    code = "page_number_check"
    description = "Проверяет нумерацию страниц"
    weight = 0.8
    
    def __init__(self,
                 start_page: int = 1,
                 start_number: int = 1,
                 position: str = "bottom",  # 'bottom' или 'top'
                 position_y_min: float = 780,
                 position_y_max: float = 842,
                 tolerance: float = 20):
        """
        Args:
            start_page: Страница, с которой начинается нумерация
            start_number: Начальный номер
            position: Расположение ('bottom' или 'top')
            position_y_min: Минимальная Y-координата номера
            position_y_max: Максимальная Y-координата номера
            tolerance: Допустимое отклонение по Y
        """
        self.start_page = start_page
        self.start_number = start_number
        self.position = position
        self.position_y_min = position_y_min
        self.position_y_max = position_y_max
        self.tolerance = tolerance
    
    def _find_page_number(self, blocks: List[dict]) -> Optional[dict]:
        """Найти блок с номером страницы"""
        for block in blocks:
            text = block.get('text', '').strip()
            bbox = block.get('bbox', {})
            y0 = bbox.get('y0', 0)
            
            # Проверяем позицию
            if not (self.position_y_min - self.tolerance <= y0 <= self.position_y_max + self.tolerance):
                continue
            
            # Проверяем, что текст - число
            if text.isdigit():
                return block
        
        return None
    
    def check(self, document_structure: dict) -> RuleResult:
        errors = []
        pages = document_structure.get('pages', [])
        
        for page in pages:
            page_num = page.get('info', {}).get('page_number', 0)
            
            # Пропускаем страницы до начала нумерации
            if page_num < self.start_page:
                continue
            
            expected_number = self.start_number + (page_num - self.start_page)
            
            # Ищем номер страницы
            blocks = page.get('blocks', [])
            number_block = self._find_page_number(blocks)
            
            if number_block is None:
                errors.append(RuleError(
                    page_number=page_num,
                    message=f"Отсутствует номер страницы (ожидался {expected_number})",
                    severity="error"
                ))
                continue
            
            # Проверяем номер
            found_number = int(number_block.get('text', '0').strip())
            if found_number != expected_number:
                bbox = number_block.get('bbox', {})
                errors.append(RuleError(
                    page_number=page_num,
                    message=f"Неверный номер страницы: {found_number}, ожидался {expected_number}",
                    severity="error",
                    bbox=(bbox.get('x0'), bbox.get('y0'),
                          bbox.get('x1'), bbox.get('y1')),
                    block_id=number_block.get('block_id')
                ))
        
        return RuleResult(
            rule_name=self.name,
            rule_code=self.code,
            passed=len(errors) == 0,
            errors=errors,
            stats={
                'start_page': self.start_page,
                'start_number': self.start_number
            }
        )
