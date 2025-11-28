"""
Основные маршруты приложения
"""

from flask import Blueprint, render_template, redirect, url_for, session, g
from database import User, UserUpload

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("auth.login"))


def get_current_user(db_session):
    """Получает текущего пользователя из сессии."""
    user_id = session.get("user_id")
    if user_id:
        return db_session.query(User).get(user_id)
    return None


@bp.route("/lk")
@bp.route("/lk-private")
def lk_private():
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for("auth.login"))
    if user.client_type != "private":
        return redirect(url_for("main.lk_company"))

    uploads = (
        db.query(UserUpload)
        .filter_by(user_id=user.id)
        .order_by(UserUpload.upload_date.desc())
        .all()
    )
    return render_template("lk.html", user=user, uploads=uploads)


@bp.route("/lk-company")
def lk_company():
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for("auth.login"))
    if user.client_type != "company":
        return redirect(url_for("main.lk_private"))

    uploads = (
        db.query(UserUpload)
        .join(User)
        .filter(User.company_id == user.company_id)
        .order_by(UserUpload.upload_date.desc())
        .all()
    )
    return render_template("lk_company.html", user=user, uploads=uploads)


@bp.route("/settings")
def settings():
    user = get_current_user(g.db_session)
    if not user:
        return redirect(url_for("auth.login"))
    return_route = (
        url_for("main.lk_company")
        if user.client_type == "company"
        else url_for("main.lk_private")
    )
    return render_template("settings.html", user=user, return_route=return_route)
