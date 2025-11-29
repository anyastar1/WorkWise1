"""
Главный файл приложения WorkWise
"""

from flask import Flask, g
from database import initialize_database
from config import SECRET_KEY

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
    print("=" * 60 + "\n")
    app.run(debug=True, port=5001)
