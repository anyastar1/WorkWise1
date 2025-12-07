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
    
    print(f"[VIEW] Document {doc_id}: is_checked={document.is_checked}, errors={len(document.errors)}")
    
    # Получаем страницы с ошибками
    pages_data = []
    for page in document.pages:
        page_errors = [e for e in document.errors if e.page_id == page.id]
        
        errors_url = None
        if page.image_with_errors_path:
            print(f"[VIEW] Page {page.page_number}: image_with_errors_path={page.image_with_errors_path}")
            if os.path.exists(page.image_with_errors_path):
                errors_url = get_page_errors_image_url(page)
                print(f"[VIEW] Page {page.page_number}: errors_url={errors_url}")
            else:
                print(f"[VIEW] Page {page.page_number}: ERROR file not found!")
        else:
            print(f"[VIEW] Page {page.page_number}: no image_with_errors_path")
        
        pages_data.append({
            'page': page,
            'errors': page_errors,
            'image_url': get_page_image_url(page),
            'errors_image_url': errors_url
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
        
        # Коммитим чтобы ошибки сохранились
        g.db_session.commit()
        
        # Перезагружаем документ для получения обновлённых данных
        g.db_session.expire_all()
        document = g.db_session.query(Document).filter_by(id=doc_id).first()
        
        # Загружаем ошибки явно
        errors = g.db_session.query(DocumentError).filter_by(document_id=doc_id).all()
        
        print(f"[DEBUG] Document {doc_id}: found {len(errors)} errors")
        
        # Рендерим ошибки на изображениях
        if errors:
            renderer = ErrorRenderer()
            
            # Группируем ошибки по страницам
            errors_by_page = {}
            for error in errors:
                if error.page_id not in errors_by_page:
                    errors_by_page[error.page_id] = []
                errors_by_page[error.page_id].append(error)
            
            # Рендерим каждую страницу
            for page in document.pages:
                page_errors = errors_by_page.get(page.id, [])
                print(f"[DEBUG] Page {page.page_number}: {len(page_errors)} errors")
                
                if page_errors:
                    # Проверяем что есть координаты хотя бы у одной ошибки
                    errors_with_bbox = [e for e in page_errors if e.bbox_x0 is not None]
                    print(f"[DEBUG] Page {page.page_number}: {len(errors_with_bbox)} errors with bbox")
                    
                    if errors_with_bbox:
                        output_path = renderer.render_errors_on_page(page, page_errors)
                        page.image_with_errors_path = output_path
                        print(f"[DEBUG] Rendered errors to: {output_path}")
        
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


@bp.route("/document/<int:doc_id>/reparse", methods=["POST"])
@require_login
def reparse_document(doc_id):
    """Повторный парсинг структуры документа"""
    user = get_current_user(g.db_session)
    
    document = g.db_session.query(Document).filter_by(
        id=doc_id, user_id=user.id
    ).first()
    
    if not document:
        flash("Документ не найден", "error")
        return redirect(url_for('main.dashboard'))
    
    try:
        doc_folder = os.path.dirname(document.images_folder)
        processor = DocumentProcessor(
            uploads_dir=os.path.join(current_app.root_path, 'uploads')
        )
        
        # Ищем оригинальный файл
        original_path = None
        for ext in ['.pdf', '.docx']:
            candidate = os.path.join(doc_folder, f"original{ext}")
            if os.path.exists(candidate):
                original_path = candidate
                break
        
        if not original_path:
            # Ищем любой PDF/DOCX в папке
            for f in os.listdir(doc_folder):
                if f.endswith(('.pdf', '.docx')):
                    original_path = os.path.join(doc_folder, f)
                    break
        
        if original_path and os.path.exists(original_path):
            structure, markdown = processor._parse_document_structure(original_path)
            document.structure_json = structure
            document.structure_markdown = markdown
            flash("Документ успешно пере-парсен!", "success")
        else:
            # Fallback: создаём минимальную структуру
            structure, markdown = processor._create_minimal_structure(document.original_filename)
            document.structure_json = structure
            document.structure_markdown = markdown
            flash("Создана минимальная структура (оригинальный файл не найден)", "warning")
        
        # Сбрасываем статус проверки
        document.is_checked = False
        document.rating = None
        
        # Удаляем старые ошибки
        g.db_session.query(DocumentError).filter_by(document_id=document.id).delete()
        
        g.db_session.commit()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Ошибка: {str(e)}", "error")
    
    return redirect(url_for('documents.view', doc_id=doc_id))


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
