"""
Вспомогательные функции
"""

import os
import subprocess
import platform
from config import ALLOWED_EXTENSIONS

# Импорт библиотек для чтения документов
try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2

    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from docx2pdf import convert as docx_to_pdf_convert

    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False


def clean_json_response(text):
    """Очищает JSON ответ от markdown обёрток и лишних символов."""
    if not text:
        return "{}"

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    start_idx = text.find("{")
    if start_idx > 0:
        text = text[start_idx:]

    end_idx = text.rfind("}")
    if end_idx > 0 and end_idx < len(text) - 1:
        text = text[: end_idx + 1]

    return text.strip()


def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def check_command_available(command: str) -> bool:
    """Проверяет, доступна ли команда в системе."""
    try:
        subprocess.run(["which", command], capture_output=True, check=True, timeout=5)
        return True
    except:
        return False


def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
    """
    Конвертирует DOCX файл в PDF.
    Поддерживает различные методы конвертации для разных ОС.

    Args:
        docx_path: Путь к DOCX файлу
        output_dir: Директория для сохранения PDF

    Returns:
        Путь к созданному PDF файлу

    Raises:
        RuntimeError: Если конвертация не удалась
    """
    pdf_filename = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    system = platform.system().lower()

    print(f"🔄 Начинаем конвертацию DOCX в PDF (ОС: {system})...")

    # Метод 1: LibreOffice (работает в Linux, Windows, macOS)
    if check_command_available("libreoffice"):
        try:
            print("📄 Попытка конвертации через LibreOffice...")
            abs_docx_path = os.path.abspath(docx_path)
            abs_output_dir = os.path.abspath(output_dir)

            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--nodefault",
                    "--nolockcheck",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    abs_output_dir,
                    abs_docx_path,
                ],
                capture_output=True,
                timeout=120,
                check=False,
                text=True,
            )

            base_name = os.path.splitext(os.path.basename(docx_path))[0]
            possible_pdf = os.path.join(abs_output_dir, base_name + ".pdf")

            if os.path.exists(possible_pdf):
                if possible_pdf != pdf_path:
                    os.rename(possible_pdf, pdf_path)
                print(f"✅ DOCX конвертирован в PDF через LibreOffice: {pdf_path}")
                if result.stdout:
                    print(f"   Вывод LibreOffice: {result.stdout[:200]}")
                return pdf_path
            else:
                print(
                    f"⚠️ LibreOffice не создал файл. Код возврата: {result.returncode}"
                )
                if result.stderr:
                    print(f"   Ошибка: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print("⚠️ LibreOffice превысил время ожидания")
        except Exception as e:
            print(f"⚠️ Ошибка LibreOffice: {e}")

    # Метод 2: unoconv
    if check_command_available("unoconv"):
        try:
            print("📄 Попытка конвертации через unoconv...")
            abs_docx_path = os.path.abspath(docx_path)

            result = subprocess.run(
                ["unoconv", "-f", "pdf", "-o", pdf_path, abs_docx_path],
                capture_output=True,
                timeout=120,
                check=False,
                text=True,
            )

            if os.path.exists(pdf_path):
                print(f"✅ DOCX конвертирован в PDF через unoconv: {pdf_path}")
                return pdf_path
            else:
                print(f"⚠️ unoconv не создал файл. Код возврата: {result.returncode}")
                if result.stderr:
                    print(f"   Ошибка: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print("⚠️ unoconv превысил время ожидания")
        except Exception as e:
            print(f"⚠️ Ошибка unoconv: {e}")

    # Метод 3: pandoc
    if check_command_available("pandoc"):
        try:
            print("📄 Попытка конвертации через pandoc...")
            abs_docx_path = os.path.abspath(docx_path)

            result = subprocess.run(
                ["pandoc", abs_docx_path, "-o", pdf_path],
                capture_output=True,
                timeout=120,
                check=False,
                text=True,
            )

            if os.path.exists(pdf_path):
                print(f"✅ DOCX конвертирован в PDF через pandoc: {pdf_path}")
                return pdf_path
            else:
                print(f"⚠️ pandoc не создал файл. Код возврата: {result.returncode}")
                if result.stderr:
                    print(f"   Ошибка: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print("⚠️ pandoc превысил время ожидания")
        except Exception as e:
            print(f"⚠️ Ошибка pandoc: {e}")

    # Метод 4: docx2pdf (только для Windows/Mac)
    if DOCX2PDF_AVAILABLE and system != "linux":
        try:
            print("📄 Попытка конвертации через docx2pdf...")
            docx_to_pdf_convert(docx_path, pdf_path)
            if os.path.exists(pdf_path):
                print(f"✅ DOCX конвертирован в PDF через docx2pdf: {pdf_path}")
                return pdf_path
        except Exception as e:
            print(f"⚠️ Ошибка docx2pdf: {e}")

    # Если ничего не сработало
    error_msg = (
        "Не удалось преобразовать DOCX в PDF.\n\n"
        "Для Linux установите один из следующих инструментов:\n"
        "  - LibreOffice: sudo apt-get install libreoffice (или sudo yum install libreoffice)\n"
        "  - unoconv: sudo apt-get install unoconv (или sudo yum install unoconv)\n"
        "  - pandoc: sudo apt-get install pandoc (или sudo yum install pandoc)\n\n"
        "После установки перезапустите приложение."
    )

    print(f"❌ {error_msg}")
    raise RuntimeError(error_msg)


def read_file_content(file_path):
    """
    Читает содержимое файла (PDF или DOCX).

    Args:
        file_path: Путь к файлу

    Returns:
        str: Текст содержимого файла или None в случае ошибки
    """
    try:
        if not os.path.exists(file_path):
            print(f"❌ Файл не найден: {file_path}")
            return None

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            # Сначала пробуем PyMuPDF
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(file_path)
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text())
                    doc.close()
                    text = "\n".join(text_parts)
                    if text.strip():
                        print(f"✅ PDF прочитан через PyMuPDF: {len(text)} символов")
                        return text
                except Exception as e:
                    print(f"⚠️ Ошибка PyMuPDF: {e}")

            # Запасной вариант - PyPDF2
            if PYPDF2_AVAILABLE:
                try:
                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        if len(reader.pages) == 0:
                            print("⚠️ PDF файл не содержит страниц")
                            return None

                        text_parts = []
                        for page_num, page in enumerate(reader.pages, 1):
                            try:
                                page_text = page.extract_text()
                                if page_text:
                                    text_parts.append(page_text)
                            except Exception as e:
                                print(f"⚠️ Ошибка чтения страницы {page_num}: {e}")

                        if not text_parts:
                            print("⚠️ Не удалось извлечь текст из PDF")
                            return None

                        text = "\n".join(text_parts)
                        print(
                            f"✅ PDF прочитан через PyPDF2: {len(text)} символов, {len(reader.pages)} страниц"
                        )
                        return text

                except Exception as pdf_err:
                    print(f"❌ Ошибка чтения PDF: {pdf_err}")
                    return None

        elif ext == ".docx" and DOCX_AVAILABLE:
            try:
                doc = docx.Document(file_path)
                paragraphs = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        paragraphs.append(para.text)

                if not paragraphs:
                    print("⚠️ DOCX файл не содержит текста")
                    return None

                text = "\n".join(paragraphs)
                print(
                    f"✅ DOCX прочитан: {len(text)} символов, {len(paragraphs)} параграфов"
                )
                return text

            except Exception as docx_err:
                print(f"❌ Ошибка чтения DOCX: {docx_err}")
                return None

        else:
            print(f"⚠️ Неподдерживаемый формат файла: {ext}")
            return None

    except Exception as e:
        print(f"❌ Неожиданная ошибка чтения файла: {e}")
        import traceback

        traceback.print_exc()
        return None
