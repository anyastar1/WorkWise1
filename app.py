"""
Айкор - Главный файл приложения
Система проверки оформления документов
"""

import os
from flask import Flask, g
from database import get_session, initialize_database

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.urandom(24)

    # Настройки загрузки файлов
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
    
    # Важно: UPLOAD_FOLDER должен быть в рабочей директории пользователя, а не внутри exe
    app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

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

    return app

app = create_app()

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True, port=5001)

