"""
Айкор - Главный файл приложения
Система проверки оформления документов
"""

import os
from flask import Flask, g
from database import get_session, initialize_database

app = Flask(__name__, static_folder="static")
app.secret_key = os.urandom(24)

# Настройки загрузки файлов
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")

# Создаём папку uploads
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# --- Обработчики запросов ---


@app.before_request
def before_request():
    """Создаёт сессию БД для каждого запроса."""
    g.db_session = get_session()


@app.teardown_request
def teardown_request(exception):
    """Закрывает сессию БД после запроса."""
    db_session = g.pop("db_session", None)
    if db_session:
        db_session.close()


# --- Регистрация блюпринтов (маршрутов) ---

from routes import auth, main
from routes.documents import bp as documents_bp

app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)
app.register_blueprint(documents_bp)


# --- Запуск приложения ---

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Запуск Айкор Application")
    print("=" * 60)
    initialize_database()
    print("=" * 60 + "\n")
    app.run(debug=True, port=5001)
