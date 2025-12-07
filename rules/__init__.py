"""
Система правил проверки документов.

Правила подключаются как модули. Каждое правило должно наследоваться
от базового класса BaseRule и реализовывать метод check().
"""

from .base import BaseRule, RuleError, RuleResult
from .engine import RulesEngine

__all__ = ['BaseRule', 'RuleError', 'RuleResult', 'RulesEngine']
