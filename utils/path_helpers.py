"""
Вспомогательные функции для работы с путями.

Работают корректно как в dev режиме, так и при запуске через PyInstaller.
"""

import os
import sys


def get_base_path():
    """
    Получает базовый путь для записи файлов (uploads и т.д.).
    
    В режиме PyInstaller возвращает директорию рядом с exe-файлом.
    В режиме разработки возвращает текущую рабочую директорию.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


def get_app_root_path():
    """
    Получает путь к корню приложения (где static, templates и т.д.).
    
    В режиме PyInstaller возвращает временную директорию внутри архива.
    В режиме разработки возвращает текущую рабочую директорию.
    """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")
