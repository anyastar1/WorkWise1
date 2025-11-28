"""
Главный файл приложения WorkWise
"""

import os
from flask import Flask, g
from database import initialize_database
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, SECRET_KEY
from api.ollama_client import check_ollama_available, is_api_configured

# Создаём приложение Flask
app = Flask(__name__, static_folder="static")
app.secret_key = SECRET_KEY

# Конфигурация загрузки файлов
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Создаём папку для загрузок если не существует
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Проверяем доступность Ollama при старте
check_ollama_available()
if is_api_configured():
    from config import OLLAMA_BASE_URL, OLLAMA_MODEL

    print(f"✅ Ollama API настроен: {OLLAMA_BASE_URL}, модель: {OLLAMA_MODEL}")
else:
    from config import OLLAMA_BASE_URL

    print("⚠️  ВНИМАНИЕ: Ollama сервер недоступен при старте!")
    print(f"   Проверьте доступность сервера по адресу: {OLLAMA_BASE_URL}")
    print("   Приложение будет работать, но запросы к API могут не выполняться.")

# Импортируем маршруты
from routes import auth, main, upload

# Регистрируем маршруты
app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)
app.register_blueprint(upload.bp)


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
    print("=" * 60 + "\n")
    app.run(debug=True, port=5001)
