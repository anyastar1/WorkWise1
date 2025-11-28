"""
Маршруты для загрузки и обработки файлов
"""

import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
    current_app,
)
from database import User, UserUpload, GOST
from api.ollama_client import is_api_configured
from utils.helpers import allowed_file, convert_docx_to_pdf, PYMUPDF_AVAILABLE
from services.document_analyzer import analyze_document

bp = Blueprint("upload", __name__)

# Импорт PyMuPDF для чтения PDF
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def get_current_user(db_session):
    """Получает текущего пользователя из сессии."""
    user_id = session.get("user_id")
    if user_id:
        return db_session.query(User).get(user_id)
    return None


@bp.route("/check-file", methods=["GET", "POST"])
def check_file():
    """Страница загрузки и проверки файла."""
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    db = g.db_session
    user = db.query(User).filter_by(id=session["user_id"]).one_or_none()

    if not user:
        return redirect(url_for("auth.login"))

    # Получаем доступные ГОСТы
    if user.client_type == "company":
        gosts = db.query(GOST).all()
    else:
        gosts = db.query(GOST).filter_by(client_type_for="all").all()

    # Для API предупреждения
    api_warning = None
    IS_API_CONFIGURED = is_api_configured()
    if not IS_API_CONFIGURED:
        api_warning = "API ключ не настроен"

    if request.method == "POST":
        print("📤 Получен POST запрос")
        print(f"📤 Form data keys: {list(request.form.keys())}")
        print(f"📤 Files keys: {list(request.files.keys())}")

        # ИСПРАВЛЕНО: ищем 'file_upload' вместо 'file'
        if "file_upload" not in request.files:
            flash("Файл не найден в запросе", "error")
            return redirect(request.url)

        file = request.files["file_upload"]
        print(f"📁 Файл: {file.filename}")

        if file.filename == "" or file.filename is None:
            flash("Файл не выбран", "error")
            return redirect(request.url)

        # Проверяем расширение файла
        if not allowed_file(file.filename):
            flash("Неподдерживаемый формат файла. Разрешены: .pdf, .docx", "error")
            return redirect(request.url)

        # ИСПРАВЛЕНО: получаем gost_id по правильному имени поля 'gost_select'
        gost_id = request.form.get("gost_select", type=int)
        print(f"📋 ГОСТ ID: {gost_id}")

        if not gost_id:
            flash("Выберите стандарт (ГОСТ)", "error")
            return redirect(request.url)

        # Проверка API
        if not IS_API_CONFIGURED:
            flash(
                "Ошибка: Ollama сервер недоступен. Проверьте подключение к серверу.",
                "error",
            )
            return redirect(request.url)

        # Сохраняем файл
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        original_filename = filename
        original_unique_filename = f"{uuid.uuid4()}{file_ext}"

        # Создаём папку uploads если не существует
        uploads_dir = os.path.join(current_app.root_path, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        original_file_path = os.path.join(uploads_dir, original_unique_filename)
        file.save(original_file_path)
        print(f"💾 Оригинальный файл сохранён: {original_file_path}")

        # Конвертируем DOCX в PDF перед анализом
        file_path = original_file_path
        unique_filename = original_unique_filename
        pdf_path = None

        if file_ext in [".docx", ".doc"]:
            try:
                print(f"🔄 Конвертируем {file_ext} в PDF...")
                pdf_path = convert_docx_to_pdf(original_file_path, uploads_dir)

                # Используем PDF для анализа
                file_path = pdf_path
                unique_filename = os.path.basename(pdf_path)
                file_ext = ".pdf"
                print(f"✅ Файл конвертирован в PDF: {pdf_path}")
            except Exception as e:
                print(f"❌ Ошибка конвертации DOCX в PDF: {e}")
                flash(f"Ошибка конвертации файла в PDF: {str(e)}", "error")
                # Удаляем оригинальный файл при ошибке
                try:
                    if os.path.exists(original_file_path):
                        os.remove(original_file_path)
                except:
                    pass
                return redirect(request.url)

        try:
            # Извлекаем текст из файла (теперь всегда PDF или уже был PDF)
            text_content = ""

            if file_ext == ".pdf" and PYMUPDF_AVAILABLE and fitz:
                try:
                    doc = fitz.open(file_path)
                    text_content = "\n".join([page.get_text() for page in doc])
                    doc.close()
                    print(f"✅ Текст извлечён из PDF: {len(text_content)} символов")
                except Exception as e:
                    print(f"⚠️ Ошибка чтения PDF: {e}")
            elif file_ext == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()

            # Анализируем документ (используем PDF файл)
            print(
                f"🔍 Начинаем анализ файла: {original_filename} (конвертирован в PDF: {unique_filename}), ГОСТ ID: {gost_id}"
            )
            analysis_result = analyze_document(file_path, text_content, gost_id, db)
            print(f"✅ Результат анализа: success={analysis_result.get('success')}")

            # Сохраняем результат в БД
            # Сохраняем оригинальное имя файла, но путь к PDF
            upload = UserUpload(
                filename=original_filename,  # Оригинальное имя
                file_path=unique_filename,  # Путь к PDF файлу
                user_id=user.id,
                gost_id=gost_id,
                status="Проверено" if analysis_result.get("success") else "Ошибка",
                report_json=json.dumps(
                    {"gost_processing": analysis_result}, ensure_ascii=False
                ),
                upload_date=datetime.now(),
            )
            db.add(upload)
            db.commit()

            upload_id = upload.id
            print(f"✅ Сохранено в БД, ID: {upload_id}")

            # Удаляем оригинальный DOCX файл, если был создан PDF
            if pdf_path and os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                    print(f"🗑️ Оригинальный DOCX файл удалён: {original_file_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить оригинальный файл: {e}")

            if analysis_result.get("success"):
                flash("Файл успешно обработан!", "success")
            else:
                flash(
                    f'Ошибка обработки: {analysis_result.get("error", "Неизвестная ошибка")}',
                    "error",
                )

            return redirect(url_for("upload.process_file", upload_id=upload_id))

        except Exception as e:
            print(f"❌ Ошибка при обработке файла: {e}")
            import traceback

            traceback.print_exc()

            # Удаляем временные файлы при ошибке
            try:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if os.path.exists(original_file_path):
                    os.remove(original_file_path)
            except:
                pass

            # Сохраняем с ошибкой
            upload = UserUpload(
                filename=original_filename,
                file_path=(
                    unique_filename
                    if "unique_filename" in locals()
                    else original_unique_filename
                ),
                user_id=user.id,
                gost_id=gost_id,
                status="Ошибка",
                report_json=json.dumps(
                    {"gost_processing": {"success": False, "error": str(e)}},
                    ensure_ascii=False,
                ),
                upload_date=datetime.now(),
            )
            db.add(upload)
            db.commit()
            upload_id = upload.id

            flash(f"Ошибка обработки файла: {str(e)}", "error")

            return redirect(url_for("upload.process_file", upload_id=upload_id))

    # GET запрос - показываем форму
    return_route = (
        url_for("main.lk_company")
        if user.client_type == "company"
        else url_for("main.lk_private")
    )

    return render_template(
        "check.html",
        user=user,
        gosts=gosts,
        return_route=return_route,
        api_warning=api_warning,
        is_api_configured=IS_API_CONFIGURED,
    )


@bp.route("/process-file/<int:upload_id>")
def process_file(upload_id):
    """Отображение результатов обработки файла."""
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for("auth.login"))

    upload = db.query(UserUpload).filter_by(id=upload_id).one_or_none()
    if not upload:
        return redirect(url_for("main.lk_private"))

    # Проверка прав доступа
    if upload.user_id != user.id and not (
        user.client_type == "company" and upload.user.company_id == user.company_id
    ):
        return redirect(url_for("main.lk_private"))

    gost_obj = db.query(GOST).filter_by(id=upload.gost_id).one_or_none()

    # Парсинг результата
    result = None
    if upload.report_json:
        try:
            data = json.loads(upload.report_json)
            result = data.get("gost_processing")
        except:
            pass

    return_route = (
        url_for("main.lk_company")
        if user.client_type == "company"
        else url_for("main.lk_private")
    )
    return render_template(
        "process-file.html",
        upload=upload,
        user=user,
        gost=gost_obj,
        result=result,
        return_route=return_route,
    )


@bp.route("/work-details/<int:upload_id>")
def work_details(upload_id):
    return redirect(url_for("upload.process_file", upload_id=upload_id))
