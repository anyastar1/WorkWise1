"""
Основные маршруты приложения
"""

from flask import Blueprint, render_template, redirect, url_for, g
from database import User, UserUpload
from utils.auth_helpers import get_current_user, require_login, get_return_route

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@bp.route("/lk")
@bp.route("/lk-private")
@require_login
def lk_private():
    db = g.db_session
    user = get_current_user(db)
    
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
@require_login
def lk_company():
    db = g.db_session
    user = get_current_user(db)
    
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
@require_login
def settings():
    user = get_current_user(g.db_session)
    return_route = get_return_route(user)
    return render_template("settings.html", user=user, return_route=return_route)
