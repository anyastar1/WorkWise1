"""
Основные маршруты приложения
"""

from flask import Blueprint, redirect, url_for, render_template, request, flash, g, send_from_directory
from werkzeug.utils import secure_filename
import os
from pathlib import Path
from utils.auth_helpers import require_login, get_current_user
from database import Document, Page
from utils.document_processor import process_document

bp = Blueprint("main", __name__)

# Настройки загрузки файлов
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ

# Создаем директорию для загрузок
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@bp.route("/welcome")
@require_login
def welcome():
    """Страница приветствия после авторизации"""
    user = get_current_user(g.db_session)
    return render_template("welcome.html", user=user)


@bp.route("/upload", methods=["POST"])
@require_login
def upload_document():
    """Обработка загрузки документа"""
    user = get_current_user(g.db_session)
    db = g.db_session
    
    # Проверка наличия файла
    if "file" not in request.files:
        flash("Файл не выбран", "error")
        return redirect(url_for("main.welcome"))
    
    file = request.files["file"]
    operation_type = request.form.get("operation_type", "Проверить на соответствие структуры")
    
    # Проверка выбора файла
    if file.filename == "":
        flash("Файл не выбран", "error")
        return redirect(url_for("main.welcome"))
    
    # Проверка расширения файла
    if not allowed_file(file.filename):
        flash("Допустимы только PDF и DOCX", "error")
        return redirect(url_for("main.welcome"))
    
    # Проверка размера файла
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        flash("Файл слишком большой (максимум 50 МБ)", "error")
        return redirect(url_for("main.welcome"))
    
    try:
        # Обработка документа
        document = process_document(file, user.id, operation_type, db)
        
        flash("Документ успешно загружен и обработан", "success")
        return redirect(url_for("main.view_document", document_id=document.id))
    
    except Exception as e:
        db.rollback()
        flash(f"Произошла ошибка. Попробуйте ещё раз: {str(e)}", "error")
        return redirect(url_for("main.welcome"))


@bp.route("/document/<int:document_id>")
@require_login
def view_document(document_id):
    """Страница просмотра документа"""
    user = get_current_user(g.db_session)
    db = g.db_session
    
    document = db.get(Document, document_id)
    
    if not document:
        flash("Документ не найден", "error")
        return redirect(url_for("main.welcome"))
    
    # Проверка прав доступа
    if document.user_id != user.id:
        flash("У вас нет доступа к этому документу", "error")
        return redirect(url_for("main.welcome"))
    
    # Получаем страницы, отсортированные по номеру
    pages = sorted(document.pages, key=lambda p: p.page_number)
    
    return render_template("document_view.html", document=document, pages=pages, user=user)


@bp.route("/uploads/<path:filename>")
@require_login
def uploaded_file(filename):
    """Отдача загруженных файлов"""
    return send_from_directory(UPLOAD_FOLDER, filename)


def allowed_file(filename):
    """Проверка допустимого расширения файла"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
