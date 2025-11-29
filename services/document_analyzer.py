"""
Сервис для анализа документов
"""

import json
import os
from typing import List
from document_processor import DocumentProcessor
from api.ollama_client import (
    call_ollama_api,
    call_ollama_api_with_images,
    call_ollama_api_with_pdf,
)
from utils.helpers import clean_json_response
from utils.helpers import PYMUPDF_AVAILABLE

# Инициализация процессора документов
doc_processor = DocumentProcessor(dpi=150, max_pages=30)


def analyze_document_with_pdf(file_path: str, gost_name: str) -> dict:
    """Анализирует документ через отправку PDF файла напрямую в Ollama."""
    try:
        print(f"📄 Начинаем обработку PDF файла напрямую: {file_path}")

        # Проверяем, что файл существует и это PDF
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext != ".pdf":
            return {
                "success": False,
                "error": f"Функция analyze_document_with_pdf поддерживает только PDF файлы, получен: {file_ext}",
            }

        # Определяем тип анализа по ГОСТу
        if "7.32" in gost_name:
            return analyze_structure_from_pdf(file_path, gost_name)
        else:
            return analyze_bibliography_from_pdf(file_path, gost_name)

    except Exception as e:
        print(f"❌ Ошибка при анализе PDF файла: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


def analyze_document_with_images(file_path: str, gost_name: str) -> dict:
    """Анализирует документ через преобразование в изображения."""
    try:
        print(f"🖼️ Начинаем обработку документа через изображения: {file_path}")

        # Преобразуем документ в изображения
        images, base64_images = doc_processor.process_document(file_path)
        print(f"✅ Документ преобразован в {len(images)} изображений")

        if not base64_images:
            return {
                "success": False,
                "error": "Не удалось преобразовать документ в изображения",
            }

        # Определяем тип анализа по ГОСТу
        if "7.32" in gost_name:
            return analyze_structure_from_images(base64_images, gost_name)
        else:
            return analyze_bibliography_from_images(base64_images, gost_name)

    except Exception as e:
        print(f"❌ Ошибка при анализе документа: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


def analyze_structure_from_pdf(pdf_file_path: str, gost_name: str) -> dict:
    """Анализирует структуру документа по PDF файлу (ГОСТ 7.32-2001)."""
    system_instruction = """Ты - эксперт по оформлению научных работ согласно ГОСТ 7.32-2001. 
Анализируй PDF документ и проверяй структуру и оформление. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй PDF документ на соответствие ГОСТ 7.32-2001. 
Верни JSON с анализом структуры документа, титульного листа, содержания, введения, основной части, заключения и списка литературы."""

    try:
        response_text = call_ollama_api_with_pdf(
            prompt, system_instruction, pdf_file_path
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("structure_analysis", {})
        result.setdefault(
            "overall_compliance", {"score": 0, "level": "низкий", "summary": ""}
        )
        result.setdefault("missing_elements", [])
        result.setdefault("general_recommendations", [])

        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if "response_text" in locals() else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_bibliography_from_pdf(pdf_file_path: str, gost_name: str) -> dict:
    """Анализирует библиографические ссылки по PDF файлу (ГОСТ Р 7.0.5-2008)."""
    system_instruction = """Ты - эксперт по библиографическому оформлению согласно ГОСТ Р 7.0.5-2008. 
Анализируй PDF документ и находи все библиографические ссылки. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй PDF документ и найди все библиографические ссылки. 
Проверь каждую ссылку на соответствие ГОСТ Р 7.0.5-2008 и верни JSON с результатами."""

    try:
        response_text = call_ollama_api_with_pdf(
            prompt, system_instruction, pdf_file_path
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("total_found", 0)
        result.setdefault("correct_count", len(result.get("correct_references", [])))
        result.setdefault(
            "incorrect_count", len(result.get("incorrect_references", []))
        )
        result.setdefault("correct_references", [])
        result.setdefault("incorrect_references", [])
        result.setdefault("general_recommendations", [])

        if result["total_found"] == 0:
            result["total_found"] = result["correct_count"] + result["incorrect_count"]

        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if "response_text" in locals() else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_structure_from_images(images_base64: List[str], gost_name: str) -> dict:
    """Анализирует структуру документа по изображениям (ГОСТ 7.32-2001)."""
    # Импортируем промпты из отдельного файла или определяем здесь
    # Для краткости используем упрощённую версию
    system_instruction = """Ты - эксперт по оформлению научных работ согласно ГОСТ 7.32-2001. 
Анализируй изображения страниц документа и проверяй структуру и оформление. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй изображения страниц документа на соответствие ГОСТ 7.32-2001. 
Верни JSON с анализом структуры документа, титульного листа, содержания, введения, основной части, заключения и списка литературы."""

    try:
        response_text = call_ollama_api_with_images(
            prompt, system_instruction, [images_base64[0]]
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("structure_analysis", {})
        result.setdefault(
            "overall_compliance", {"score": 0, "level": "низкий", "summary": ""}
        )
        result.setdefault("missing_elements", [])
        result.setdefault("general_recommendations", [])

        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if "response_text" in locals() else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_bibliography_from_images(images_base64: List[str], gost_name: str) -> dict:
    """Анализирует библиографические ссылки по изображениям (ГОСТ Р 7.0.5-2008)."""
    system_instruction = """Ты - эксперт по библиографическому оформлению согласно ГОСТ Р 7.0.5-2008. 
Анализируй изображения страниц документа и находи все библиографические ссылки. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй изображения страниц документа и найди все библиографические ссылки. 
Проверь каждую ссылку на соответствие ГОСТ Р 7.0.5-2008 и верни JSON с результатами."""

    try:
        response_text = call_ollama_api_with_images(
            prompt, system_instruction, images_base64
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("total_found", 0)
        result.setdefault("correct_count", len(result.get("correct_references", [])))
        result.setdefault(
            "incorrect_count", len(result.get("incorrect_references", []))
        )
        result.setdefault("correct_references", [])
        result.setdefault("incorrect_references", [])
        result.setdefault("general_recommendations", [])

        if result["total_found"] == 0:
            result["total_found"] = result["correct_count"] + result["incorrect_count"]

        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if "response_text" in locals() else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_document_with_gost(text_content, gost_name="ГОСТ Р 7.0.5-2008"):
    """Анализирует документ и находит ошибки в библиографических ссылках согласно ГОСТ."""
    # Упрощённая версия - полные промпты можно вынести в отдельный файл
    system_instruction = """Ты - эксперт по библиографическому оформлению документов согласно ГОСТ Р 7.0.5-2008."""

    text_for_analysis = text_content[:50000]
    if len(text_content) > 50000:
        print(f"Текст обрезан с {len(text_content)} до 50000 символов")

    prompt = f"""Проанализируй текст документа и найди все библиографические ссылки. 
Проверь каждую на соответствие ГОСТ Р 7.0.5-2008.

ТЕКСТ ДОКУМЕНТА:
{text_for_analysis}

Верни JSON с найденными ссылками, разделив их на правильные и неправильные."""

    try:
        response_text = call_ollama_api(
            prompt, system_instruction, max_output_tokens=8000, temperature=0.1
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("total_found", 0)
        result.setdefault("correct_count", len(result.get("correct_references", [])))
        result.setdefault(
            "incorrect_count", len(result.get("incorrect_references", []))
        )
        result.setdefault("correct_references", [])
        result.setdefault("incorrect_references", [])
        result.setdefault("general_recommendations", [])
        result.setdefault("error", None)

        if result["total_found"] == 0:
            result["total_found"] = result["correct_count"] + result["incorrect_count"]

        result["processed_count"] = result["total_found"]
        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "total_found": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "correct_references": [],
            "incorrect_references": [],
            "general_recommendations": [],
            "processed_count": 0,
            "error": f"Ошибка парсинга ответа ИИ: {str(e)}",
            "raw_response": (
                cleaned_response[:2000] if "cleaned_response" in locals() else ""
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "total_found": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "correct_references": [],
            "incorrect_references": [],
            "general_recommendations": [],
            "processed_count": 0,
            "error": str(e),
        }


def analyze_document_structure_gost_732(text_content):
    """Анализирует документ на соответствие ГОСТ 7.32-2001."""
    system_instruction = """Ты - эксперт по оформлению научных и учебных работ согласно ГОСТ 7.32-2001."""

    text_for_analysis = text_content[:50000]
    prompt = f"""Проанализируй структуру и оформление документа на соответствие ГОСТ 7.32-2001.

ТЕКСТ ДОКУМЕНТА:
{text_for_analysis}

Верни JSON с анализом структуры документа."""

    try:
        response_text = call_ollama_api(
            prompt, system_instruction, max_output_tokens=8000, temperature=0.1
        )
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)

        result.setdefault("success", True)
        result.setdefault("document_type", "не определён")
        result.setdefault("structure_analysis", {})
        result.setdefault("formatting_analysis", {})
        result.setdefault(
            "overall_compliance", {"score": 0, "level": "низкий", "summary": ""}
        )
        result.setdefault("missing_elements", [])
        result.setdefault("corrections", [])
        result.setdefault("general_recommendations", [])
        result.setdefault("error", None)

        result["processed_count"] = len(result.get("corrections", []))
        structure = result.get("structure_analysis", {})
        found_count = sum(
            1 for key in structure if structure.get(key, {}).get("present", False)
        )
        result["total_found"] = found_count

        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "document_type": "не определён",
            "structure_analysis": {},
            "formatting_analysis": {},
            "overall_compliance": {
                "score": 0,
                "level": "низкий",
                "summary": "Ошибка анализа",
            },
            "missing_elements": [],
            "corrections": [],
            "general_recommendations": [],
            "processed_count": 0,
            "total_found": 0,
            "error": f"Ошибка парсинга ответа ИИ: {str(e)}",
            "raw_response": (
                cleaned_response[:2000] if "cleaned_response" in locals() else ""
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "document_type": "не определён",
            "structure_analysis": {},
            "formatting_analysis": {},
            "overall_compliance": {
                "score": 0,
                "level": "низкий",
                "summary": "Ошибка анализа",
            },
            "missing_elements": [],
            "corrections": [],
            "general_recommendations": [],
            "processed_count": 0,
            "total_found": 0,
            "error": str(e),
        }


def analyze_document(
    file_path: str, text_content: str, gost_id: int, db_session
) -> dict:
    """
    Главная функция анализа документа.
    Выбирает метод анализа в зависимости от типа файла и ГОСТа.
    Сначала пробует анализ через изображения, затем текстовый анализ.
    """
    from database import GOST

    gost = (
        db_session.query(GOST).filter_by(id=gost_id).one_or_none() if gost_id else None
    )
    gost_name = gost.name if gost else "ГОСТ Р 7.0.5-2008"

    file_ext = os.path.splitext(file_path)[1].lower()

    # Для PDF пробуем сначала прямой анализ PDF файла, затем через изображения
    if file_ext == ".pdf" and PYMUPDF_AVAILABLE:
        # Сначала пробуем отправить PDF напрямую (быстрее и эффективнее)
        try:
            print(f"📄 Пробуем анализ PDF файла напрямую для {file_ext}")
            result = analyze_document_with_pdf(file_path, gost_name)
            if result.get("success"):
                print(f"✅ Анализ PDF файла напрямую успешен")
                return result
            print(f"⚠️ Анализ PDF напрямую не удался, пробуем через изображения...")
        except Exception as e:
            print(f"⚠️ Ошибка анализа PDF напрямую: {e}, пробуем через изображения...")

        # Запасной вариант - анализ через изображения
        try:
            print(f"🖼️ Используем анализ через изображения для {file_ext}")
            result = analyze_document_with_images(file_path, gost_name)
            if result.get("success"):
                return result
            print(f"⚠️ Анализ через изображения не удался, пробуем текстовый анализ...")
        except Exception as e:
            print(f"⚠️ Ошибка анализа через изображения: {e}")

    # Для DOCX пробуем анализ через изображения
    elif file_ext in [".docx", ".doc"] and PYMUPDF_AVAILABLE:
        try:
            print(f"🖼️ Используем анализ через изображения для {file_ext}")
            result = analyze_document_with_images(file_path, gost_name)
            if result.get("success"):
                return result
            print(f"⚠️ Анализ через изображения не удался, пробуем текстовый анализ...")
        except Exception as e:
            print(f"⚠️ Ошибка анализа через изображения: {e}")

    # Запасной вариант - текстовый анализ
    print(f"📝 Используем текстовый анализ")
    if "7.32" in gost_name:
        return analyze_document_structure_gost_732(text_content)
    else:
        return analyze_document_with_gost(text_content, gost_name)
