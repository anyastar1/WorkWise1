"""
Маршруты для работы с документами.
"""

import os
import json
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, g, jsonify, send_from_directory,
    current_app
)
from werkzeug.utils import secure_filename

from database import Document, DocumentPage, DocumentError
from utils.auth_helpers import get_current_user, require_login
from services.document_processor import DocumentProcessor
from services.error_renderer import ErrorRenderer
from rules.engine import RulesEngine

bp = Blueprint("documents", __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/upload", methods=["GET", "POST"])
@require_login
def upload():
    """Страница загрузки документа"""
    user = get_current_user(g.db_session)
    
    if request.method == "POST":
        # Проверяем наличие файла
        if 'document' not in request.files:
            flash("Файл не выбран", "error")
            return redirect(request.url)
        
        file = request.files['document']
        
        if file.filename == '':
            flash("Файл не выбран", "error")
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash("Недопустимый формат файла. Разрешены: PDF, DOCX", "error")
            return redirect(request.url)
        
        # Сохраняем временный файл
        filename = secure_filename(file.filename)
        temp_dir = os.path.join(current_app.root_path, 'uploads', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        try:
            # Обрабатываем документ
            processor = DocumentProcessor(
                uploads_dir=os.path.join(current_app.root_path, 'uploads')
            )
            document = processor.process_document(temp_path, user.id)
            
            flash("Документ успешно загружен!", "success")
            return redirect(url_for('documents.view', doc_id=document.id))
            
        except Exception as e:
            flash(f"Ошибка обработки документа: {str(e)}", "error")
            return redirect(request.url)
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    return render_template("upload.html", user=user)


@bp.route("/document/<int:doc_id>")
@require_login
def view(doc_id):
    """Просмотр документа"""
    user = get_current_user(g.db_session)
    
    document = g.db_session.query(Document).filter_by(
        id=doc_id, user_id=user.id
    ).first()
    
    if not document:
        flash("Документ не найден", "error")
        return redirect(url_for('main.dashboard'))
    
    # Получаем страницы с ошибками
    pages_data = []
    for page in document.pages:
        page_errors = [e for e in document.errors if e.page_id == page.id]
        pages_data.append({
            'page': page,
            'errors': page_errors,
            'image_url': get_page_image_url(page),
            'errors_image_url': get_page_errors_image_url(page) if page.image_with_errors_path else None
        })
    
    return render_template(
        "document_view.html",
        user=user,
        document=document,
        pages_data=pages_data
    )


@bp.route("/document/<int:doc_id>/check", methods=["POST"])
@require_login
def check_document(doc_id):
    """Проверка документа по правилам"""
    user = get_current_user(g.db_session)
    
    document = g.db_session.query(Document).filter_by(
        id=doc_id, user_id=user.id
    ).first()
    
    if not document:
        return jsonify({'success': False, 'error': 'Документ не найден'}), 404
    
    try:
        # Создаём движок правил
        engine = RulesEngine.create_default_engine()
        
        # Проверяем документ (передаём сессию)
        result = engine.check_document(document, session=g.db_session)
        
        if not result['success']:
            return jsonify({
                'success': False, 
                'error': result.get('error', 'Ошибка проверки')
            }), 400
        
        # Перезагружаем документ для получения обновлённых данных
        g.db_session.refresh(document)
        
        # Рендерим ошибки на изображениях
        if document.errors:
            renderer = ErrorRenderer()
            renderer.render_all_pages(document)
        
        # Сохраняем пути к изображениям с ошибками
        g.db_session.commit()
        
        return jsonify({
            'success': True,
            'rating': result.get('rating', 0),
            'total_errors': result.get('total_errors', 0),
            'redirect': url_for('documents.view', doc_id=doc_id)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route("/document/<int:doc_id>/delete", methods=["POST"])
@require_login
def delete_document(doc_id):
    """Удаление документа"""
    user = get_current_user(g.db_session)
    
    document = g.db_session.query(Document).filter_by(
        id=doc_id, user_id=user.id
    ).first()
    
    if not document:
        flash("Документ не найден", "error")
        return redirect(url_for('main.dashboard'))
    
    try:
        # Удаляем файлы
        import shutil
        doc_folder = os.path.dirname(document.images_folder)
        if os.path.exists(doc_folder):
            shutil.rmtree(doc_folder)
        
        # Удаляем из БД
        g.db_session.delete(document)
        g.db_session.commit()
        
        flash("Документ удалён", "success")
    except Exception as e:
        flash(f"Ошибка удаления: {str(e)}", "error")
    
    return redirect(url_for('main.dashboard'))


@bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Отдача загруженных файлов"""
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    return send_from_directory(uploads_dir, filename)


# Вспомогательные функции
def get_page_image_url(page: DocumentPage) -> str:
    """Получить URL изображения страницы"""
    # Получаем относительный путь от uploads/
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    rel_path = os.path.relpath(page.image_path, uploads_dir)
    return url_for('documents.serve_upload', filename=rel_path)


def get_page_errors_image_url(page: DocumentPage) -> str:
    """Получить URL изображения страницы с ошибками"""
    if not page.image_with_errors_path:
        return None
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    rel_path = os.path.relpath(page.image_with_errors_path, uploads_dir)
    return url_for('documents.serve_upload', filename=rel_path)
