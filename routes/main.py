"""
Основные маршруты приложения
"""

from flask import Blueprint, redirect, url_for, render_template, request, flash, g, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
from pathlib import Path
from utils.auth_helpers import require_login, get_current_user
from database import Document, Page, PageStatus
from utils.document_processor import process_document
from utils.page_processor import get_page_processor

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
        
        flash("Документ успешно загружен", "success")
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
    
    # Запускаем обработку страниц через Ollama при переходе на страницу документа
    # Проверяем, есть ли страницы в статусе "queued" (еще не обрабатывались)
    pages = sorted(document.pages, key=lambda p: p.page_number)
    queued_pages = [p for p in pages if p.status == PageStatus.QUEUED.value]
    
    if queued_pages:
        # Запускаем обработку только для страниц в очереди
        processor = get_page_processor()
        print(f"[DEBUG] Запуск обработки {len(queued_pages)} страниц для документа {document_id}")
        
        for page in queued_pages:
            image_path = os.path.join("uploads", page.image_path)
            if os.path.exists(image_path):
                print(f"[DEBUG] Добавление страницы {page.page_number} в очередь обработки")
                processor.add_page_task(page.id, image_path, page.page_number)
            else:
                print(f"[WARNING] Изображение страницы {page.page_number} не найдено: {image_path}")
    
    return render_template("document_view.html", document=document, pages=pages, user=user)


@bp.route("/uploads/<path:filename>")
@require_login
def uploaded_file(filename):
    """Отдача загруженных файлов"""
    return send_from_directory(UPLOAD_FOLDER, filename)


@bp.route("/api/document/<int:document_id>/status")
@require_login
def document_status(document_id):
    """API для получения статуса обработки документа"""
    user = get_current_user(g.db_session)
    db = g.db_session
    
    document = db.get(Document, document_id)
    
    if not document:
        return jsonify({"error": "Документ не найден"}), 404
    
    # Проверка прав доступа
    if document.user_id != user.id:
        return jsonify({"error": "Нет доступа"}), 403
    
    # Получаем статусы страниц
    pages = sorted(document.pages, key=lambda p: p.page_number)
    pages_status = [
        {
            "page_id": p.id,
            "page_number": p.page_number,
            "status": p.status,
            "error": p.processing_error
        }
        for p in pages
    ]
    
    # Подсчитываем статистику
    total = len(pages)
    queued = sum(1 for p in pages if p.status == PageStatus.QUEUED.value)
    processing = sum(1 for p in pages if p.status == PageStatus.PROCESSING.value)
    completed = sum(1 for p in pages if p.status == PageStatus.COMPLETED.value)
    errors = sum(1 for p in pages if p.status == PageStatus.ERROR.value)
    
    return jsonify({
        "document_id": document_id,
        "all_pages_processed": document.all_pages_processed,
        "gost_check_completed": document.gost_check_completed,
        "pages": pages_status,
        "statistics": {
            "total": total,
            "queued": queued,
            "processing": processing,
            "completed": completed,
            "errors": errors
        }
    })


@bp.route("/api/document/<int:document_id>/page/<int:page_id>/retry", methods=["POST"])
@require_login
def retry_page_processing(document_id, page_id):
    """API для повторной обработки страницы"""
    user = get_current_user(g.db_session)
    db = g.db_session
    
    document = db.get(Document, document_id)
    
    if not document:
        return jsonify({"error": "Документ не найден"}), 404
    
    # Проверка прав доступа
    if document.user_id != user.id:
        return jsonify({"error": "Нет доступа"}), 403
    
    # Находим страницу
    page = db.get(Page, page_id)
    
    if not page:
        return jsonify({"error": "Страница не найдена"}), 404
    
    # Проверяем, что страница принадлежит документу
    if page.document_id != document_id:
        return jsonify({"error": "Страница не принадлежит документу"}), 400
    
    # Проверяем, что страница в статусе ошибки
    if page.status != PageStatus.ERROR.value:
        return jsonify({"error": f"Страница не в статусе ошибки (текущий статус: {page.status})"}), 400
    
    # Проверяем существование изображения
    image_path = os.path.join("uploads", page.image_path)
    if not os.path.exists(image_path):
        return jsonify({"error": f"Изображение страницы не найдено: {image_path}"}), 404
    
    try:
        # Сбрасываем статус страницы на "в очереди"
        page.status = PageStatus.QUEUED.value
        page.processing_error = None
        db.commit()
        
        # Добавляем страницу в очередь обработки
        processor = get_page_processor()
        processor.add_page_task(page.id, image_path, page.page_number)
        
        print(f"[INFO] Страница {page.page_number} (ID: {page.id}) добавлена в очередь для повторной обработки")
        
        return jsonify({
            "success": True,
            "message": f"Страница {page.page_number} добавлена в очередь обработки",
            "page_id": page.id,
            "page_number": page.page_number
        })
    
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Ошибка при повторной обработке страницы {page_id}: {e}")
        return jsonify({"error": f"Ошибка при добавлении страницы в очередь: {str(e)}"}), 500


@bp.route("/document/<int:document_id>/report")
@require_login
def view_gost_report(document_id):
    """Страница отчета о соответствии ГОСТу"""
    import json
    import os
    from utils.gost_visualizer import visualize_gost_errors
    
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
    
    # Проверяем, есть ли отчет
    if not document.gost_check_completed:
        flash("Проверка на соответствие ГОСТу еще не завершена", "error")
        return redirect(url_for("main.view_document", document_id=document_id))
    
    # Получаем отчет из БД
    from database import GOSTReport
    gost_report = db.query(GOSTReport).filter_by(document_id=document_id).first()
    
    if not gost_report:
        flash("Отчет не найден в базе данных", "error")
        return redirect(url_for("main.view_document", document_id=document_id))
    
    # Проверяем, что текст отчета не пустой
    if not gost_report.report_text or gost_report.report_text.strip() == "":
        flash("Текст отчета пуст", "error")
        return redirect(url_for("main.view_document", document_id=document_id))
    
    print(f"[DEBUG] Загрузка отчета для документа {document_id}, длина текста: {len(gost_report.report_text)}")
    
    # Пытаемся распарсить JSON
    gost_data = None
    try:
        gost_data = json.loads(gost_report.report_text)
        print(f"[DEBUG] JSON успешно распарсен, score: {gost_data.get('score')}, страниц: {len(gost_data.get('pages', []))}")
    except json.JSONDecodeError:
        print(f"[WARNING] Не удалось распарсить JSON, используем старый формат")
        gost_data = None
    
    # Если JSON успешно распарсен, создаем визуализированные изображения
    pages_with_visualization = []
    if gost_data and 'pages' in gost_data:
        pages = sorted(document.pages, key=lambda p: p.page_number)
        pages_data = gost_data.get('pages', [])
        
        # Создаем словарь для быстрого поиска данных по номеру страницы
        pages_data_dict = {pg_data.get('page'): pg_data for pg_data in pages_data}
        
        for page in pages:
            # Находим данные для этой страницы
            page_gost_data = pages_data_dict.get(page.page_number)
            
            # Если данных нет, создаем пустую запись
            if not page_gost_data:
                page_gost_data = {
                    'page': page.page_number,
                    'gosterror': '',
                    'howtofix': '',
                    'positionX': 0,
                    'positionY': 0,
                    'width': 0,
                    'height': 0
                }
            
            # Если есть ошибка, проверяем наличие визуализированного изображения
            visualized_image = None
            if page_gost_data.get('gosterror', '').strip():
                image_path = os.path.join("uploads", page.image_path)
                if os.path.exists(image_path):
                    # Создаем путь для визуализированного изображения
                    base_dir = os.path.dirname(image_path)
                    base_name = os.path.basename(image_path)
                    name, ext = os.path.splitext(base_name)
                    vis_path = os.path.join(base_dir, f"{name}_gost{ext}")
                    
                    # Проверяем, существует ли уже визуализированное изображение
                    if os.path.exists(vis_path):
                        # Используем существующее изображение
                        visualized_image = os.path.relpath(vis_path, "uploads")
                    else:
                        # Создаем визуализацию только если её еще нет
                        try:
                            visualize_gost_errors(image_path, [page_gost_data], vis_path)
                            # Сохраняем относительный путь для использования в шаблоне
                            visualized_image = os.path.relpath(vis_path, "uploads")
                        except Exception as e:
                            print(f"[ERROR] Ошибка создания визуализации для страницы {page.page_number}: {e}")
            
            pages_with_visualization.append({
                'page_number': page.page_number,
                'visualized_image': visualized_image,
                'gost_data': page_gost_data
            })
    
    return render_template(
        "gost_report.html", 
        document=document, 
        report=gost_report, 
        user=user,
        gost_data=gost_data,
        pages_with_visualization=pages_with_visualization
    )


def allowed_file(filename):
    """Проверка допустимого расширения файла"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
