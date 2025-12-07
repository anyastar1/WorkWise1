"""
Основные маршруты приложения
"""

from flask import Blueprint, render_template, redirect, url_for, g
from database import Document
from utils.auth_helpers import get_current_user, require_login

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@require_login
def dashboard():
    """Приветственная страница с загрузкой документов"""
    db = g.db_session
    user = get_current_user(db)
    
    # Получаем документы пользователя
    documents = db.query(Document).filter_by(user_id=user.id).order_by(
        Document.created_at.desc()
    ).all()
    
    return render_template("dashboard.html", user=user, documents=documents)
