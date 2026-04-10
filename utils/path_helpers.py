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
    # Проверяем PyInstaller по наличию _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        # sys.argv[0] содержит путь к оригинальному exe-файлу
        # Это работает как для --onefile, так и для --onedir
        exe_path = sys.argv[0] if sys.argv[0] else sys.executable
        return os.path.dirname(os.path.abspath(exe_path))
    # Dev режим: текущая рабочая директория (важно для uploads)
    return os.getcwd()


def get_app_root_path():
    """
    Получает путь к корню приложения (где static, templates и т.д.).
    
    В режиме PyInstaller возвращает временную директорию внутри архива.
    В режиме разработки возвращает текущую рабочую директорию.
    """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")
