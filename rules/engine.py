"""
Движок правил - управляет загрузкой и выполнением правил проверки.
"""

import os
import importlib
import json
from typing import List, Dict, Type, Any
from datetime import datetime

from .base import BaseRule, RuleResult, RuleError
from database import Document, DocumentPage, DocumentError, get_session


class RulesEngine:
    """
    Движок правил проверки документов.
    
    Загружает правила из папки rules/ и выполняет их
    для проверки документов.
    """
    
    def __init__(self):
        self._rules: List[BaseRule] = []
    
    def register_rule(self, rule: BaseRule):
        """Зарегистрировать правило"""
        self._rules.append(rule)
    
    def register_rules(self, rules: List[BaseRule]):
        """Зарегистрировать несколько правил"""
        self._rules.extend(rules)
    
    def clear_rules(self):
        """Очистить все правила"""
        self._rules = []
    
    @property
    def rules(self) -> List[BaseRule]:
        """Получить список зарегистрированных правил"""
        return self._rules
    
    def check_document(self, document: Document, session=None) -> Dict[str, Any]:
        """
        Проверить документ по всем зарегистрированным правилам.
        
        Args:
            document: Модель документа из БД
            session: SQLAlchemy сессия (опционально)
            
        Returns:
            dict: Результаты проверки с рейтингом
        """
        if not document.structure_json:
            return {
                'success': False,
                'error': 'Документ не имеет структуры JSON',
                'results': [],
                'rating': 0
            }
        
        # Парсим структуру документа
        try:
            doc_structure = json.loads(document.structure_json)
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Ошибка парсинга JSON: {e}',
                'results': [],
                'rating': 0
            }
        
        # Выполняем все правила
        all_results: List[RuleResult] = []
        all_errors: List[RuleError] = []
        
        for rule in self._rules:
            try:
                result = rule.check(doc_structure)
                all_results.append(result)
                all_errors.extend(result.errors)
            except Exception as e:
                # Ошибка в самом правиле
                import traceback
                traceback.print_exc()
                all_results.append(RuleResult(
                    rule_name=rule.name,
                    rule_code=rule.code,
                    passed=False,
                    errors=[RuleError(
                        page_number=0,
                        message=f"Ошибка выполнения правила: {str(e)}",
                        severity="error"
                    )]
                ))
        
        # Вычисляем рейтинг
        rating = self._calculate_rating(all_results)
        
        # Сохраняем результаты в БД
        self._save_errors_to_db(document, all_results, session)
        
        return {
            'success': True,
            'results': all_results,
            'total_errors': len(all_errors),
            'rating': rating
        }
    
    def _calculate_rating(self, results: List[RuleResult]) -> float:
        """
        Вычисление рейтинга документа (0-100).
        
        Формула: 100 - (сумма штрафов за ошибки)
        Штраф за ошибку = вес_правила * коэффициент_серьезности
        """
        if not results:
            return 100.0
        
        total_penalty = 0.0
        severity_multiplier = {
            'error': 3.0,
            'warning': 1.5,
            'info': 0.5
        }
        
        for result in results:
            rule = next((r for r in self._rules if r.code == result.rule_code), None)
            weight = rule.weight if rule else 1.0
            
            for error in result.errors:
                multiplier = severity_multiplier.get(error.severity, 1.0)
                total_penalty += weight * multiplier
        
        # Ограничиваем рейтинг от 0 до 100
        rating = max(0, 100 - total_penalty)
        return round(rating, 1)
    
    def _save_errors_to_db(self, document: Document, results: List[RuleResult], session=None):
        """Сохранение ошибок в базу данных"""
        own_session = session is None
        if own_session:
            session = get_session()
        
        try:
            # Удаляем старые ошибки
            session.query(DocumentError).filter_by(document_id=document.id).delete()
            
            # Получаем страницы документа - перезагружаем в текущей сессии
            from database import DocumentPage as DP
            pages_list = session.query(DP).filter_by(document_id=document.id).all()
            pages = {p.page_number: p for p in pages_list}
            
            error_number = 0
            for result in results:
                for error in result.errors:
                    error_number += 1
                    page = pages.get(error.page_number)
                    
                    if page:
                        db_error = DocumentError(
                            document_id=document.id,
                            page_id=page.id,
                            error_number=error_number,
                            rule_name=result.rule_name,
                            rule_code=result.rule_code,
                            message=error.message,
                            severity=error.severity,
                            bbox_x0=error.bbox[0] if error.bbox else None,
                            bbox_y0=error.bbox[1] if error.bbox else None,
                            bbox_x1=error.bbox[2] if error.bbox else None,
                            bbox_y1=error.bbox[3] if error.bbox else None,
                            block_id=error.block_id,
                            extra_data=error.extra_data
                        )
                        session.add(db_error)
            
            # Обновляем документ в текущей сессии
            from database import Document as Doc
            doc_to_update = session.query(Doc).get(document.id)
            if doc_to_update:
                doc_to_update.is_checked = True
                doc_to_update.check_date = datetime.utcnow()
                doc_to_update.rating = self._calculate_rating(results)
            
            if own_session:
                session.commit()
            
        except Exception as e:
            if own_session:
                session.rollback()
            raise e
        finally:
            if own_session:
                session.close()
    
    @classmethod
    def create_default_engine(cls) -> 'RulesEngine':
        """
        Создает движок с набором стандартных правил.
        """
        from .rules_impl import (
            BoundsRule,
            FontRule,
            FontSizeRule,
            ColorRule,
            LineSpacingRule,
            MarginsRule,
            HeadingRule,
            PageNumberRule
        )
        
        engine = cls()
        engine.register_rules([
            BoundsRule(),
            FontRule(),
            FontSizeRule(),
            ColorRule(),
            LineSpacingRule(),
            MarginsRule(),
            HeadingRule(),
            PageNumberRule()
        ])
        
        return engine
