"""
Основные маршруты приложения
"""

from flask import Blueprint, render_template, redirect, url_for, g
from utils.auth_helpers import get_current_user, require_login

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@require_login
def dashboard():
    """Простая приветственная страница после авторизации"""
    db = g.db_session
    user = get_current_user(db)
    return render_template("dashboard.html", user=user)
