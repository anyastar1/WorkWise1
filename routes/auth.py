"""
Маршруты для аутентификации
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
)
from database import User, KeyCompany
from utils.auth_helpers import validate_user_exists, validate_company_key

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    db = g.db_session
    if request.method == "POST":
        login_input = request.form.get("login")
        password = request.form.get("password")
        client_type = request.form.get("client_type")
        company_key = request.form.get("company_key")

        user = (
            db.query(User)
            .filter_by(login=login_input, client_type=client_type)
            .one_or_none()
        )

        if user and user.check_password(password):
            valid = True
            if client_type == "company":
                key_obj = (
                    db.query(KeyCompany)
                    .filter_by(
                        key_value=company_key,
                        company_id=user.company_id,
                        is_active=True,
                    )
                    .one_or_none()
                )
                if not key_obj:
                    valid = False

            if valid:
                session["user_id"] = user.id
                session["client_type"] = user.client_type
                flash(f"Добро пожаловать, {user.login}!", "success")
                return redirect(url_for("main.welcome"))
            else:
                flash("Неверный ключ компании.", "error")
        else:
            flash("Неверный логин или пароль.", "error")

    return render_template("login.html")


@bp.route("/registration", methods=["GET", "POST"])
def registration():
    db = g.db_session
    if request.method == "POST":
        login_input = request.form.get("login")
        email = request.form.get("email")
        password = request.form.get("password")
        client_type = request.form.get("client_type")
        activity_type = request.form.get("activity_type")
        company_key = request.form.get("company_key")

        # Проверка существования пользователя
        login_exists, email_exists = validate_user_exists(db, login=login_input, email=email)
        
        if login_exists:
            flash("Логин занят.", "error")
            return redirect(url_for("auth.registration"))
        if email_exists:
            flash("Email занят.", "error")
            return redirect(url_for("auth.registration"))

        # Проверка ключа компании
        company_id = None
        if client_type == "company":
            key_obj = validate_company_key(db, company_key)
            if not key_obj:
                flash("Неверный ключ компании.", "error")
                return redirect(url_for("auth.registration"))
            company_id = key_obj.company_id

        user = User(
            login=login_input,
            email=email,
            client_type=client_type,
            activity_type=activity_type,
            company_id=company_id,
        )
        user.set_password(password)

        try:
            db.add(user)
            db.commit()
            flash("Аккаунт создан! Теперь войдите.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.rollback()
            flash(f"Ошибка: {e}", "error")
            return redirect(url_for("auth.registration"))

    return render_template("registration.html")


@bp.route("/password-recovery", methods=["GET", "POST"])
def password_recovery():
    return render_template("password-recovery.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
