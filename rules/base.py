"""
Базовые классы для системы правил проверки документов.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class RuleError:
    """
    Ошибка, найденная правилом.
    
    Attributes:
        page_number: Номер страницы (1-indexed)
        message: Описание ошибки
        severity: Уровень серьезности ('error', 'warning', 'info')
        bbox: Координаты области ошибки (x0, y0, x1, y1) в pt
        block_id: ID блока из JSON-структуры (если применимо)
        extra_data: Дополнительные данные об ошибке
    """
    page_number: int
    message: str
    severity: str = "warning"
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1)
    block_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class RuleResult:
    """
    Результат проверки правила.
    
    Attributes:
        rule_name: Название правила
        rule_code: Код правила
        passed: Прошла ли проверка
        errors: Список найденных ошибок
        stats: Статистика проверки
    """
    rule_name: str
    rule_code: str
    passed: bool
    errors: List[RuleError] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)


class BaseRule(ABC):
    """
    Базовый класс для правил проверки документов.
    
    Каждое правило должно:
    1. Наследоваться от BaseRule
    2. Определить name и code
    3. Реализовать метод check()
    
    Пример создания правила:
    
    ```python
    class FontSizeRule(BaseRule):
        name = "Проверка размера шрифта"
        code = "font_size"
        
        def __init__(self, min_size: float = 12, max_size: float = 14):
            self.min_size = min_size
            self.max_size = max_size
        
        def check(self, document_structure: dict) -> RuleResult:
            errors = []
            # ... логика проверки ...
            return RuleResult(
                rule_name=self.name,
                rule_code=self.code,
                passed=len(errors) == 0,
                errors=errors
            )
    ```
    """
    
    # Название правила (для отображения пользователю)
    name: str = "Базовое правило"
    
    # Код правила (уникальный идентификатор)
    code: str = "base_rule"
    
    # Описание правила
    description: str = ""
    
    # Вес ошибки для расчета рейтинга (0.0 - 1.0)
    weight: float = 1.0
    
    @abstractmethod
    def check(self, document_structure: dict) -> RuleResult:
        """
        Проверка документа по правилу.
        
        Args:
            document_structure: Структура документа в формате JSON (dict)
                Формат соответствует SCHEMA.md из document_parser
                
        Returns:
            RuleResult с результатами проверки
        """
        pass
    
    def get_blocks(self, document_structure: dict) -> List[dict]:
        """Получить все блоки из всех страниц"""
        blocks = []
        for page in document_structure.get('pages', []):
            blocks.extend(page.get('blocks', []))
        return blocks
    
    def get_page_blocks(self, document_structure: dict, page_number: int) -> List[dict]:
        """Получить блоки конкретной страницы"""
        pages = document_structure.get('pages', [])
        for page in pages:
            if page.get('info', {}).get('page_number') == page_number:
                return page.get('blocks', [])
        return []
    
    def get_page_info(self, document_structure: dict, page_number: int) -> Optional[dict]:
        """Получить информацию о странице"""
        pages = document_structure.get('pages', [])
        for page in pages:
            if page.get('info', {}).get('page_number') == page_number:
                return page.get('info', {})
        return None
    
    def get_all_spans(self, block: dict) -> List[dict]:
        """Получить все span из блока"""
        spans = []
        for line in block.get('lines', []):
            spans.extend(line.get('spans', []))
        return spans
