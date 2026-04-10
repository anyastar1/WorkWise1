import os
import sys
import webbrowser
from threading import Timer
from app import app, initialize_database

def open_browser():
    """Открывает браузер по умолчанию через 2 секунды после запуска сервера."""
    webbrowser.open("http://127.0.0.1:5001")

def get_resource_path(relative_path):
    """ Получает абсолютный путь к ресурсам, работает для dev и для PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

if __name__ == "__main__":
    # Настройка путей для Flask, чтобы он видел static и templates внутри PyInstaller
    app.static_folder = get_resource_path("static")
    app.template_folder = get_resource_path("templates")
    
    # Убеждаемся, что uploads существует в текущей рабочей директории (не внутри exe)
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = uploads_dir

    print("\n" + "=" * 60)
    print("🚀 Запуск Айкор Application")
    print("=" * 60)
    
    initialize_database()
    
    print("=" * 60 + "\n")
    
    # Запускаем открытие браузера в отдельном потоке, чтобы не блокировать запуск Flask
    Timer(2, open_browser).start()
    
    app.run(debug=False, port=5001, host='127.0.0.1')
