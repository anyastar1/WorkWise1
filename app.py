"""
Главный файл приложения WorkWise
"""

import logging
from flask import Flask, g
from database import initialize_database
from config import SECRET_KEY

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workwise.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Создаём приложение Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY

# Импортируем маршруты
from routes import auth, main

# Регистрируем маршруты
app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)


# Обработчики запросов для БД
@app.before_request
def before_request():
    """Создаёт сессию БД для каждого запроса."""
    from database import get_session

    g.db_session = get_session()


@app.teardown_request
def teardown_request(exception):
    """Закрывает сессию БД после запроса."""
    db_session = g.pop("db_session", None)
    if db_session:
        db_session.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Запуск WorkWise Application")
    print("=" * 60)
    initialize_database()
    
    # Инициализируем процессор страниц
    print("Инициализация процессора страниц...")
    from utils.page_processor import get_page_processor
    processor = get_page_processor()
    print("Процессор страниц запущен")
    
    print("=" * 60 + "\n")
    app.run(debug=True, port=5001)
