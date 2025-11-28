import os
import uuid
import json
from typing import List
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from database import get_session, User, KeyCompany, initialize_database, UserUpload, GOST
from datetime import datetime

# Импорт обработчика документов
from document_processor import DocumentProcessor, process_document_to_images

# Импорт из новых модулей
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, SECRET_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL
from api.ollama_client import call_ollama_api, call_ollama_api_with_images, check_ollama_available, is_api_configured
from utils.helpers import clean_json_response, allowed_file, convert_docx_to_pdf, read_file_content, PYMUPDF_AVAILABLE
from services.document_analyzer import analyze_document, analyze_document_with_images

# Импорт библиотек для чтения документов
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️ python-docx не установлен. Установите: pip install python-docx")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("⚠️ PyPDF2 не установлен.  Установите: pip install PyPDF2")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️ PyMuPDF не установлен. Установите: pip install PyMuPDF")

try:
    from docx2pdf import convert as docx_to_pdf_convert
    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False
    print("⚠️ docx2pdf не установлен. Установите: pip install docx2pdf")

app = Flask(__name__, static_folder='static')
app.secret_key = SECRET_KEY

# ============================================================================
# FILE UPLOAD CONFIGURATION
# ============================================================================

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Инициализация процессора документов
doc_processor = DocumentProcessor(dpi=150, max_pages=30)

# Проверяем доступность при старте (не блокируем запуск)
IS_API_CONFIGURED = check_ollama_available()

if IS_API_CONFIGURED:
    print(f"✅ Ollama API настроен: {OLLAMA_BASE_URL}, модель: {OLLAMA_MODEL}")
else:
    print("⚠️  ВНИМАНИЕ: Ollama сервер недоступен при старте!")
    print(f"   Проверьте доступность сервера по адресу: {OLLAMA_BASE_URL}")
    print("   Приложение будет работать, но запросы к API могут не выполняться.")

# ============================================================================
# OLLAMA API FUNCTIONS (импортированы из api.ollama_client)
# ============================================================================
# Функции call_ollama_api и call_ollama_api_with_images импортированы выше

# ============================================================================
# DOCUMENT ANALYSIS FUNCTIONS (импортированы из services.document_analyzer)
# ============================================================================
# Функции анализа документов импортированы выше

# ============================================================================
# FILE PROCESSING FUNCTIONS (импортированы из utils.helpers)
# ============================================================================
# Функции обработки файлов импортированы выше 
    
    Args:
        prompt: Текст запроса пользователя
        system_instruction: Системная инструкция (опционально)
        max_output_tokens: Максимальное количество токенов в ответе (игнорируется для Ollama)
        temperature: Температура генерации (0.0-1.0)
    
    Returns:
        str: Ответ от API
    """
    if not IS_API_CONFIGURED:
        raise ValueError("Ollama сервер недоступен. Проверьте подключение к серверу.")
    
    # Формируем промпт с системной инструкцией
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n{prompt}"
    
    # Структура запроса для Ollama API
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens if max_output_tokens else 4000
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    api_url = f"{OLLAMA_BASE_URL}/api/generate"
    
    # Подробное логирование запроса
    print("\n" + "="*80)
    print("📤 ЗАПРОС К OLLAMA API")
    print("="*80)
    print(f"🔗 URL: {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📝 Длина промпта: {len(prompt)} символов")
    if system_instruction:
        print(f"⚙️  Длина системной инструкции: {len(system_instruction)} символов")
    print(f"📊 Длина полного промпта: {len(full_prompt)} символов")
    print(f"🌡️  Temperature: {temperature}")
    print(f"🔢 Max tokens: {max_output_tokens}")
    print(f"⏰ Время начала запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Показываем первые 200 символов промпта для отладки
    preview = full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
    print(f"📄 Превью промпта: {preview}")
    print("-"*80)
    
    start_time = time.time()
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=300  # Увеличенный таймаут для больших запросов
        )
        
        elapsed_time = time.time() - start_time
        
        # Подробное логирование ответа
        print("\n" + "="*80)
        print("📥 ОТВЕТ ОТ OLLAMA API")
        print("="*80)
        print(f"📊 HTTP статус: {response.status_code}")
        print(f"⏱️  Время выполнения: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)")
        print(f"📏 Размер ответа: {len(response.content)} байт")
        
        if response.status_code != 200:
            error_msg = f"Ошибка Ollama API (код {response.status_code})"
            try:
                error_data = response.json()
                print(f"❌ Ошибка в JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                if 'error' in error_data:
                    error_msg = f"Ошибка Ollama: {error_data['error']}"
            except:
                error_text = response.text[:500]
                print(f"❌ Текст ошибки: {error_text}")
                error_msg = f"Ошибка Ollama API: {error_text}"
            print("="*80 + "\n")
            raise ValueError(error_msg)
        
        data = response.json()
        
        # Логируем метаданные из ответа
        print(f"📦 Ключи в ответе: {list(data.keys())}")
        
        if 'model' in data:
            print(f"🤖 Модель в ответе: {data['model']}")
        if 'created_at' in data:
            print(f"🕐 Создано: {data['created_at']}")
        if 'done' in data:
            print(f"✅ Завершено: {data['done']}")
        if 'total_duration' in data:
            print(f"⏱️  Общее время (от Ollama): {data['total_duration']/1e9:.2f} секунд")
        if 'load_duration' in data:
            print(f"⏳ Время загрузки модели: {data['load_duration']/1e9:.2f} секунд")
        if 'prompt_eval_count' in data:
            print(f"📝 Токенов в промпте: {data['prompt_eval_count']}")
        if 'eval_count' in data:
            print(f"📤 Токенов в ответе: {data['eval_count']}")
        if 'eval_duration' in data:
            print(f"⏱️  Время генерации: {data['eval_duration']/1e9:.2f} секунд")
        
        if 'response' in data:
            content = data['response']
            if content:
                print(f"✅ Длина ответа: {len(content)} символов")
                print(f"📄 Первые 300 символов ответа:")
                print("-"*80)
                print(content[:300] + ("..." if len(content) > 300 else ""))
                print("-"*80)
                if len(content) > 300:
                    print(f"📄 Последние 200 символов ответа:")
                    print("-"*80)
                    print("..." + content[-200:])
                    print("-"*80)
                print("="*80 + "\n")
                return content
            else:
                print("❌ Пустой ответ от API")
                print("="*80 + "\n")
                raise ValueError("Пустой ответ от API")
        else:
            print(f"❌ Неожиданный формат ответа. Полный ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            print("="*80 + "\n")
            raise ValueError(f"Неожиданный формат ответа: {data}")
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ Превышено время ожидания ({elapsed_time:.2f} секунд)")
        print("="*80 + "\n")
        raise ValueError("Превышено время ожидания ответа от Ollama API.")
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка подключения: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("="*80 + "\n")
        raise ValueError(f"Ошибка подключения к Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка парсинга JSON: {str(e)}")
        print(f"📄 Первые 500 символов ответа: {response.text[:500]}")
        print("="*80 + "\n")
        raise ValueError("Некорректный JSON ответ от Ollama API")
    except ValueError as e:
        raise
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Неожиданная ошибка: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("="*80 + "\n")
        raise ValueError(f"Ошибка при вызове Ollama API: {str(e)}")


def call_ollama_api_with_images(prompt: str, system_instruction: str, 
                                images_base64: List[str], 
                                max_output_tokens: int = 8000,
                                temperature: float = 0.1) -> str:
    """
    Вызывает Ollama API с изображениями. 
    
    Args:
        prompt: Текстовый промпт
        system_instruction: Системная инструкция
        images_base64: Список base64 закодированных изображений (без префикса data:image/png;base64,)
        max_output_tokens: Максимальное количество токенов в ответе
        temperature: Температура генерации
        
    Returns:
        Ответ от API
    """
    if not IS_API_CONFIGURED:
        raise ValueError("Ollama сервер недоступен. Проверьте подключение к серверу.")
    
    # Формируем промпт с системной инструкцией
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n{prompt}"
    
    # Очищаем base64 строки от префикса если есть
    cleaned_images = []
    for img_base64 in images_base64:
        # Убираем префикс data:image/png;base64, если есть
        if ',' in img_base64:
            img_base64 = img_base64.split(',', 1)[1]
        cleaned_images.append(img_base64)
    
    # Ограничиваем количество изображений (максимум 10 для стабильности)
    max_images = min(len(cleaned_images), 10)
    images_to_send = cleaned_images[:max_images]
    
    # Вычисляем размер изображений
    total_image_size = sum(len(img) for img in images_to_send)
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "images": images_to_send,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens if max_output_tokens else 8000
        }
    }
    
    headers = {"Content-Type": "application/json"}
    api_url = f"{OLLAMA_BASE_URL}/api/generate"
    
    # Подробное логирование запроса
    print("\n" + "="*80)
    print("📤 ЗАПРОС К OLLAMA API (С ИЗОБРАЖЕНИЯМИ)")
    print("="*80)
    print(f"🔗 URL: {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📝 Длина промпта: {len(prompt)} символов")
    if system_instruction:
        print(f"⚙️  Длина системной инструкции: {len(system_instruction)} символов")
    print(f"📊 Длина полного промпта: {len(full_prompt)} символов")
    print(f"🖼️  Количество изображений: {max_images} (из {len(images_base64)} переданных)")
    print(f"📦 Общий размер изображений (base64): {total_image_size:,} символов ({total_image_size/1024/1024:.2f} MB)")
    for i, img in enumerate(images_to_send[:3], 1):  # Показываем размер первых 3 изображений
        print(f"   Изображение {i}: {len(img):,} символов ({len(img)/1024:.2f} KB)")
    if len(images_to_send) > 3:
        print(f"   ... и ещё {len(images_to_send) - 3} изображений")
    print(f"🌡️  Temperature: {temperature}")
    print(f"🔢 Max tokens: {max_output_tokens}")
    print(f"⏰ Время начала запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Показываем первые 200 символов промпта для отладки
    preview = full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
    print(f"📄 Превью промпта: {preview}")
    print("-"*80)
    
    start_time = time.time()
    
    try:
        print(f"📤 Отправка запроса с изображениями в Ollama...")
        response = requests.post(api_url, headers=headers, json=payload, timeout=600)  # Увеличенный таймаут для изображений
        
        elapsed_time = time.time() - start_time
        
        # Подробное логирование ответа
        print("\n" + "="*80)
        print("📥 ОТВЕТ ОТ OLLAMA API (С ИЗОБРАЖЕНИЯМИ)")
        print("="*80)
        print(f"📊 HTTP статус: {response.status_code}")
        print(f"⏱️  Время выполнения: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)")
        print(f"📏 Размер ответа: {len(response.content)} байт")
        
        if response.status_code != 200:
            error_msg = f"Ошибка Ollama API (код {response.status_code})"
            try:
                error_data = response.json()
                print(f"❌ Ошибка в JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                if 'error' in error_data:
                    error_msg = f"Ошибка Ollama: {error_data['error']}"
            except:
                error_text = response.text[:500]
                print(f"❌ Текст ошибки: {error_text}")
                error_msg = f"Ошибка Ollama API: {error_text}"
            print("="*80 + "\n")
            raise ValueError(error_msg)
        
        data = response.json()
        
        # Логируем метаданные из ответа
        print(f"📦 Ключи в ответе: {list(data.keys())}")
        
        if 'model' in data:
            print(f"🤖 Модель в ответе: {data['model']}")
        if 'created_at' in data:
            print(f"🕐 Создано: {data['created_at']}")
        if 'done' in data:
            print(f"✅ Завершено: {data['done']}")
        if 'total_duration' in data:
            print(f"⏱️  Общее время (от Ollama): {data['total_duration']/1e9:.2f} секунд")
        if 'load_duration' in data:
            print(f"⏳ Время загрузки модели: {data['load_duration']/1e9:.2f} секунд")
        if 'prompt_eval_count' in data:
            print(f"📝 Токенов в промпте: {data['prompt_eval_count']}")
        if 'eval_count' in data:
            print(f"📤 Токенов в ответе: {data['eval_count']}")
        if 'eval_duration' in data:
            print(f"⏱️  Время генерации: {data['eval_duration']/1e9:.2f} секунд")
        
        if 'response' in data:
            content = data['response']
            print(f"✅ Длина ответа: {len(content)} символов")
            print(f"📄 Первые 300 символов ответа:")
            print("-"*80)
            print(content[:300] + ("..." if len(content) > 300 else ""))
            print("-"*80)
            if len(content) > 300:
                print(f"📄 Последние 200 символов ответа:")
                print("-"*80)
                print("..." + content[-200:])
                print("-"*80)
            print("="*80 + "\n")
            return content
        else:
            print(f"❌ Неожиданный формат ответа. Полный ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            print("="*80 + "\n")
            raise ValueError(f"Неожиданный формат ответа: {data}")
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ Превышено время ожидания ({elapsed_time:.2f} секунд)")
        print("="*80 + "\n")
        raise ValueError("Превышено время ожидания ответа от Ollama API.")
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка подключения: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("="*80 + "\n")
        raise ValueError(f"Ошибка подключения к Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка парсинга JSON: {str(e)}")
        print(f"📄 Первые 500 символов ответа: {response.text[:500]}")
        print("="*80 + "\n")
        raise ValueError("Некорректный JSON ответ от Ollama API")
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Неожиданная ошибка: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("="*80 + "\n")
        raise ValueError(f"Ошибка обработки ответа: {e}")


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
    
    start_idx = text.find('{')
    if start_idx > 0:
        text = text[start_idx:]
    
    end_idx = text.rfind('}')
    if end_idx > 0 and end_idx < len(text) - 1:
        text = text[:end_idx + 1]
    
    return text. strip()


# ============================================================================
# DOCUMENT ANALYSIS WITH IMAGES
# ============================================================================

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
                "error": "Не удалось преобразовать документ в изображения"
            }
        
        # Определяем тип анализа по ГОСТу
        if "7. 32" in gost_name:
            return analyze_structure_from_images(base64_images, gost_name)
        else:
            return analyze_bibliography_from_images(base64_images, gost_name)
            
    except Exception as e:
        print(f"❌ Ошибка при анализе документа: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def analyze_structure_from_images(images_base64: List[str], gost_name: str) -> dict:
    """Анализирует структуру документа по изображениям (ГОСТ 7.32-2001)."""
    system_instruction = """Ты - эксперт по оформлению научных работ согласно ГОСТ 7.32-2001. 
Анализируй изображения страниц документа и проверяй структуру и оформление. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй изображения страниц документа на соответствие ГОСТ 7.32-2001. 

ТРЕБОВАНИЯ ДЛЯ ПРОВЕРКИ:

1.  ТИТУЛЬНЫЙ ЛИСТ:
   - Наименование организации (вуза)
   - Кафедра/факультет
   - Тип документа (РЕФЕРАТ, КУРСОВАЯ РАБОТА и т.д.)
   - Тема работы
   - Сведения об авторе (ФИО, группа, курс)
   - Сведения о руководителе (должность, ФИО)
   - Город и год

2. СОДЕРЖАНИЕ (ОГЛАВЛЕНИЕ):
   - Наличие всех разделов с номерами страниц

3. ВВЕДЕНИЕ:
   - Актуальность темы
   - Цель работы
   - Задачи работы
   - Объект и предмет исследования
   - Методы исследования

4. ОСНОВНАЯ ЧАСТЬ:
   - Наличие разделов и подразделов
   - Нумерация разделов

5. ЗАКЛЮЧЕНИЕ:
   - Выводы по работе

6. СПИСОК ЛИТЕРАТУРЫ:
   - Наличие и количество источников

7. ОФОРМЛЕНИЕ:
   - Шрифт (должен быть Times New Roman, 14 пт)
   - Поля документа
   - Нумерация страниц
   - Оформление заголовков

Верни JSON:
{
    "success": true,
    "document_type": "тип документа",
    "structure_analysis": {
        "title_page": {
            "present": true/false,
            "has_organization": true/false,
            "has_department": true/false,
            "has_document_type": true/false,
            "has_topic": true/false,
            "has_author": true/false,
            "has_supervisor": true/false,
            "has_city_year": true/false,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        },
        "table_of_contents": {
            "present": true/false,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        },
        "introduction": {
            "present": true/false,
            "has_relevance": true/false,
            "has_goal": true/false,
            "has_tasks": true/false,
            "has_object_subject": true/false,
            "has_methods": true/false,
            "has_structure_description": true/false,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        },
        "main_body": {
            "present": true/false,
            "sections_count": 0,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        },
        "conclusion": {
            "present": true/false,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        },
        "references": {
            "present": true/false,
            "count": 0,
            "errors": ["ошибки"],
            "recommendations": ["рекомендации"]
        }
    },
    "formatting_analysis": {
        "font_correct": true/false,
        "margins_correct": true/false,
        "page_numbers": true/false,
        "headings_correct": true/false,
        "errors": ["ошибки форматирования"],
        "recommendations": ["рекомендации"]
    },
    "overall_compliance": {
        "score": 0-100,
        "level": "высокий/средний/низкий",
        "summary": "общее заключение"
    },
    "missing_elements": ["отсутствующие элементы"],
    "general_recommendations": ["общие рекомендации"]
}"""

    try:
        response_text = call_ollama_api_with_images(prompt, system_instruction, images_base64)
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)
        
        # Нормализация
        result. setdefault('success', True)
        result.setdefault('structure_analysis', {})
        result. setdefault('overall_compliance', {'score': 0, 'level': 'низкий', 'summary': ''})
        result.setdefault('missing_elements', [])
        result.setdefault('general_recommendations', [])
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if 'response_text' in locals() else ""
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_bibliography_from_images(images_base64: List[str], gost_name: str) -> dict:
    """Анализирует библиографические ссылки по изображениям (ГОСТ Р 7.0.5-2008)."""
    system_instruction = """Ты - эксперт по библиографическому оформлению согласно ГОСТ Р 7.0.5-2008. 
Анализируй изображения страниц документа и находи все библиографические ссылки. 
Отвечай ТОЛЬКО валидным JSON без markdown разметки."""

    prompt = """Проанализируй изображения страниц документа и найди все библиографические ссылки. 

ПРАВИЛА ОФОРМЛЕНИЯ ПО ГОСТ Р 7.0. 5-2008:

1. КНИГА 1-3 автора:
   Фамилия И.  О. Название книги.  Город: Издательство, Год.  Объем с. 
   Пример: Иванов А. А. Основы программирования. М.: Наука, 2020.  300 с.

2. СТАТЬЯ ИЗ ЖУРНАЛА:
   Фамилия И. О.  Название статьи // Название журнала.  Год. № Номер.  С.  страницы.
   Пример: Петров Б. Б.  Новые технологии // Вестник науки. 2021. № 5. С. 10-15.

3. ЭЛЕКТРОННЫЙ РЕСУРС:
   Название: [сайт].  URL: адрес (дата обращения: ДД.ММ.ГГГГ). 

4. КЛЮЧЕВЫЕ ПРАВИЛА:
   - Фамилия И.  О. (с пробелом между инициалами)
   - Двойной слеш // перед названием журнала
   - С. для страниц (прописная), с. для объёма (строчная)
   - Города: М.  (Москва), СПб. (Санкт-Петербург)

Найди ВСЕ ссылки в списке литературы и проверь каждую. 

Верни JSON:
{
    "success": true,
    "total_found": 0,
    "correct_count": 0,
    "incorrect_count": 0,
    "correct_references": [
        {
            "number": 1,
            "text": "текст ссылки",
            "type": "книга/статья/электронный ресурс"
        }
    ],
    "incorrect_references": [
        {
            "number": 2,
            "original": "исходный текст",
            "type": "тип источника",
            "errors": [
                {
                    "description": "описание ошибки",
                    "wrong_fragment": "что неправильно",
                    "should_be": "как должно быть"
                }
            ],
            "corrected": "исправленный вариант"
        }
    ],
    "general_recommendations": ["рекомендации"]
}"""

    try:
        response_text = call_ollama_api_with_images(prompt, system_instruction, images_base64)
        cleaned_response = clean_json_response(response_text)
        result = json.loads(cleaned_response)
        
        # Нормализация
        result.setdefault('success', True)
        result.setdefault('total_found', 0)
        result.setdefault('correct_count', len(result. get('correct_references', [])))
        result.setdefault('incorrect_count', len(result.get('incorrect_references', [])))
        result.setdefault('correct_references', [])
        result.setdefault('incorrect_references', [])
        result.setdefault('general_recommendations', [])
        
        if result['total_found'] == 0:
            result['total_found'] = result['correct_count'] + result['incorrect_count']
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга ответа: {e}",
            "raw_response": response_text[:2000] if 'response_text' in locals() else ""
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# TEXT-BASED DOCUMENT ANALYSIS (FALLBACK)
# ============================================================================

def analyze_document_with_gost(text_content, gost_name="ГОСТ Р 7.0.5-2008"):
    """
    Анализирует документ и находит ошибки в библиографических ссылках согласно ГОСТ. 
    Разделяет ссылки на корректные и некорректные. 
    """
    system_instruction = """Ты - эксперт по библиографическому оформлению документов согласно российскому стандарту ГОСТ Р 7.0.5-2008. 
Твоя задача - найти все библиографические ссылки в документе, проверить каждую на соответствие стандарту,
и чётко разделить их на правильно оформленные и неправильно оформленные. 

ВАЖНО:
1. Отвечай ТОЛЬКО валидным JSON без markdown разметки, комментариев или пояснений
2. Каждую ссылку проверяй отдельно и относи к соответствующей категории
3.  Для неправильных ссылок ОБЯЗАТЕЛЬНО указывай конкретные ошибки и исправленный вариант"""

    text_for_analysis = text_content[:50000]
    if len(text_content) > 50000:
        print(f"Текст обрезан с {len(text_content)} до 50000 символов")

    prompt = f"""Проанализируй текст документа и найди в нём все библиографические ссылки. 

ТЕКСТ ДОКУМЕНТА:
{text_for_analysis}

---

ПРАВИЛА ОФОРМЛЕНИЯ ПО ГОСТ Р 7. 0.5-2008:

1.  ОБЩИЕ ПОЛОЖЕНИЯ:
   - Библиографическая ссылка содержит сведения о цитируемом, рассматриваемом или упоминаемом документе
   - Знак «.  — » между областями описания можно заменить на точку (.)
   - Обязательно сокращение слов по соответствующим ГОСТам
   - Указывается либо общий объем документа (например, 255 с.), либо конкретные страницы (например, С. 50-55)

2. ВИДЫ ССЫЛОК ПО МЕСТУ РАСПОЛОЖЕНИЯ:

   А) Внутритекстовая - в круглых скобках прямо в тексте:
      Пример: (Фельдман Г.  Л. Биоритмология. Ростов н/Д, 1982.  80 с.)

   Б) Подстрочная (сноска) - внизу страницы с номером-индексом:
      Пример: 5 Гонтмахер Е. Социальные проблемы России // Вопросы экономики. 2011. No 2. С. 23. 

   В) Затекстовая - в пронумерованном списке в конце работы:
      Пример: 192. Астафьева Н. Е.  Теория и практика управления: монография.  М., 2011. 123 с.

3. ПРАВИЛА ОФОРМЛЕНИЯ РАЗНЫХ ИСТОЧНИКОВ:

   А) Книга 1-3 автора:
      Формат: Фамилия И. О. Название книги: вид издания.  Город, Год.  Объем с. 
      Пример: Иванов А. А., Петров Б.  Б. Название книги: монография. М., 2020. 300 с.

   Б) Книга 4 и более авторов:
      Формат: Название книги / И. О. Фамилия [и др.]. Город, Год.  Объем с. 
      Пример: Название книги / А. А. Иванов [и др.]. М., 2020. 300 с.

   В) Статья из журнала:
      Формат: Фамилия И. О. Название статьи // Название журнала.  Год. No Номер. С. страницы. 
      Пример: Сидоров В. В.  Название статьи // Название журнала. 2019. No 5. С.  10-15. 

   Г) Диссертация:
      Формат: Фамилия И. О.  Название: дис. ... канд./д-ра наук. Город, Год.  Объем с. 
      Пример: Фенухин В. И.  Этнополитические конфликты: дис. ... канд.  полит. наук. М., 2002. 231 с.

   Д) Электронный ресурс (сайт):
      Формат: Название: [сайт]. URL: адрес (дата обращения: ДД. ММ. ГГГГ). 
      Пример: Министерство образования РФ: [сайт]. URL: http://минобрнауки.рф/ (дата обращения: 25.11.2016).

   Е) Статья из электронного журнала:
      Формат: Фамилия И. О. Название статьи // Название журнала: электрон. науч. журн. Год. С. страницы.  URL: адрес (дата обращения: ДД. ММ. ГГГГ). 

   Ж) Архивные документы:
      Формат: Название архива. Ф. номер. Оп. номер. Д. номер.  Л. номера. 
      Пример: ЦГАИПД. Ф.  1728. Оп.  1. Д. 537079. Л. 1-15.

4.  ПРАВИЛА ПУНКТУАЦИИ И СОКРАЩЕНИЙ:
   - Авторы: Фамилия и инициалы с пробелом (Иванов А. А.)
   - Между инициалами пробел обязателен
   - Название издательства после двоеточия (М.: Наука)
   - Весь документ: строчная "с." (255 с.)
   - Конкретные страницы: прописная "С." (С. 50, С. 50-55)
   - Многоточие для сокращения названий с пробелами (Информационная безопасность...)
   - Города сокращаются: М. (Москва), СПб. (Санкт-Петербург), Ростов н/Д (Ростов-на-Дону)

5.  ПОВТОРНЫЕ ССЫЛКИ:
   - "Там же" - если ссылка идет сразу за первичной
   - "Указ.  соч." - если ссылки не подряд
   - Сокращение длинного названия многоточием

---

ТИПИЧНЫЕ ОШИБКИ, КОТОРЫЕ НУЖНО ИСКАТЬ:
1.  Неправильный порядок элементов описания
2.  Отсутствие обязательных элементов (год, место издания, страницы)
3. Неправильные разделители между элементами
4.  Неправильное оформление авторов (И. О. Фамилия вместо Фамилия И.  О.)
5.  Отсутствие пробела между инициалами
6.  Неправильное оформление страниц (стр. вместо С., с.)
7. Отсутствие двойного слеша (//) перед названием журнала/сборника
8.  Для электронных ресурсов: отсутствие URL и даты обращения
9. Неправильные сокращения городов и терминов
10.  Отсутствие указания вида издания (монография, учебник, дис.  и т.д.)

---

ИНСТРУКЦИИ ПО АНАЛИЗУ:

1. Найди все библиографические ссылки в тексте

2. Для КАЖДОЙ ссылки определи:
   - Соответствует ли она полностью требованиям ГОСТ Р 7. 0.5-2008
   - Если НЕ соответствует - укажи ВСЕ ошибки с конкретными примерами

3. Верни результат в формате JSON:

{{
    "success": true,
    "total_found": <общее количество найденных ссылок>,
    "correct_count": <количество правильных>,
    "incorrect_count": <количество с ошибками>,
    
    "correct_references": [
        {{
            "number": 1,
            "text": "полный текст правильно оформленной ссылки",
            "type": "книга/статья/электронный ресурс/диссертация/архивный документ",
            "note": "краткий комментарий почему ссылка корректна"
        }}
    ],
    
    "incorrect_references": [
        {{
            "number": 2,
            "original": "исходный текст ссылки с ошибками",
            "type": "книга/статья/электронный ресурс/диссертация/архивный документ",
            "errors": [
                {{
                    "description": "описание ошибки",
                    "wrong_fragment": "фрагмент с ошибкой",
                    "should_be": "как должно быть по ГОСТ"
                }}
            ],
            "corrected": "полностью исправленная ссылка по ГОСТ Р 7.0. 5-2008",
            "components": {{
                "authors": "Фамилия И.  О.",
                "title": "Название работы",
                "source": "Название журнала или издательства",
                "year": "2024",
                "volume": "Т. 5",
                "issue": "No 2", 
                "pages": "С. 15-25",
                "url": "адрес (для электронных ресурсов)",
                "access_date": "дата обращения (для электронных ресурсов)"
            }}
        }}
    ],
    
    "general_recommendations": [
        "Общая рекомендация по улучшению оформления библиографии"
    ],
    
    "error": null
}}

ЕСЛИ СПИСОК ЛИТЕРАТУРЫ НЕ НАЙДЕН:
{{
    "success": true,
    "total_found": 0,
    "correct_count": 0,
    "incorrect_count": 0,
    "correct_references": [],
    "incorrect_references": [],
    "general_recommendations": ["В документе не обнаружен список литературы или библиографические ссылки. "],
    "error": null
}}"""

    try:
        response_text = call_ollama_api(prompt, system_instruction, max_output_tokens=8000, temperature=0.1)
        cleaned_response = clean_json_response(response_text)
        
        try:
            result = json.loads(cleaned_response)
            
            if not isinstance(result, dict):
                raise ValueError("Ответ не является JSON объектом")
            
            # Нормализация структуры
            result.setdefault('success', True)
            result.setdefault('total_found', 0)
            result.setdefault('correct_count', len(result.get('correct_references', [])))
            result. setdefault('incorrect_count', len(result.get('incorrect_references', [])))
            result.setdefault('correct_references', [])
            result.setdefault('incorrect_references', [])
            result.setdefault('general_recommendations', [])
            result.setdefault('error', None)
            
            if result['total_found'] == 0:
                result['total_found'] = result['correct_count'] + result['incorrect_count']
            
            result['processed_count'] = result['total_found']
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            print(f"Первые 500 символов ответа: {cleaned_response[:500]}")
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
                "raw_response": cleaned_response[:2000]
            }
            
    except Exception as e:
        print(f"Ошибка при анализе документа: {e}")
        return {
            "success": False,
            "total_found": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "correct_references": [],
            "incorrect_references": [],
            "general_recommendations": [],
            "processed_count": 0,
            "error": str(e)
        }


def analyze_document_structure_gost_732(text_content):
    """
    Анализирует документ на соответствие ГОСТ 7.32-2001. 
    Проверяет структуру реферата, курсовой работы, отчёта.
    """
    system_instruction = """Ты - эксперт по оформлению научных и учебных работ согласно ГОСТ 7.32-2001.
Твоя задача - проверить структуру и оформление документа на соответствие стандарту. 

ВАЖНО:
1. Отвечай ТОЛЬКО валидным JSON без markdown разметки
2. Анализируй ВЕСЬ документ как единое целое
3.  Проверяй наличие всех структурных элементов
4. Указывай конкретные замечания и рекомендации"""

    text_for_analysis = text_content[:50000]

    prompt = f"""Проанализируй структуру и оформление документа на соответствие ГОСТ 7.32-2001. 

ТЕКСТ ДОКУМЕНТА:
{text_for_analysis}

---

ТРЕБОВАНИЯ ГОСТ 7.32-2001 К СТРУКТУРЕ ДОКУМЕНТА:

1.  ТИТУЛЬНЫЙ ЛИСТ должен содержать:
   - Наименование вышестоящей организации (министерство, ведомство)
   - Наименование организации (учебное заведение)
   - Наименование факультета/кафедры
   - Вид документа (РЕФЕРАТ, КУРСОВАЯ РАБОТА, ОТЧЁТ и т.д.)
   - Тема/название работы
   - Сведения об исполнителе (ФИО, группа, курс)
   - Сведения о руководителе (должность, ФИО)
   - Город и год выполнения

2. СОДЕРЖАНИЕ (ОГЛАВЛЕНИЕ):
   - Перечень всех разделов и подразделов с номерами страниц
   - Заголовок "СОДЕРЖАНИЕ" или "ОГЛАВЛЕНИЕ" по центру

3. ВВЕДЕНИЕ должно содержать:
   - Актуальность темы
   - Цель работы
   - Задачи работы
   - Объект и предмет исследования
   - Методы исследования
   - Структура работы

4.  ОСНОВНАЯ ЧАСТЬ:
   - Разделы и подразделы с нумерацией
   - Теоретическая часть
   - Практическая часть (при наличии)

5. ЗАКЛЮЧЕНИЕ:
   - Выводы по проделанной работе
   - Результаты достижения цели и задач

6.  СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ (ЛИТЕРАТУРЫ):
   - Пронумерованный список
   - Оформление по ГОСТ Р 7.0.5-2008

7. ПРИЛОЖЕНИЯ (при наличии):
   - Обозначаются заглавными буквами (Приложение А, Б, В...)

8. ОБЩИЕ ТРЕБОВАНИЯ К ОФОРМЛЕНИЮ:
   - Шрифт Times New Roman, размер 14 пт (12 пт допускается для таблиц)
   - Межстрочный интервал 1,5
   - Поля: левое 30 мм, правое 15 мм, верхнее и нижнее 20 мм
   - Нумерация страниц арабскими цифрами, внизу по центру или справа
   - Титульный лист включается в общую нумерацию, но номер не ставится
   - Заголовки разделов — прописными буквами, по центру или с абзацного отступа
   - Каждый раздел начинается с новой страницы

---

Верни результат в формате JSON:

{{
    "success": true,
    "document_type": "реферат / курсовая работа / отчёт о НИР / дипломная работа / другое",
    
    "structure_analysis": {{
        "title_page": {{
            "present": true/false,
            "has_organization": true/false,
            "has_department": true/false,
            "has_document_type": true/false,
            "has_topic": true/false,
            "has_author": true/false,
            "has_supervisor": true/false,
            "has_city_year": true/false,
            "errors": ["список ошибок оформления титульного листа"],
            "recommendations": ["рекомендации по исправлению"]
        }},
        
        "table_of_contents": {{
            "present": true/false,
            "has_page_numbers": true/false,
            "has_all_sections": true/false,
            "errors": ["список ошибок"],
            "recommendations": ["рекомендации"]
        }},
        
        "introduction": {{
            "present": true/false,
            "has_relevance": true/false,
            "has_goal": true/false,
            "has_tasks": true/false,
            "has_object_subject": true/false,
            "has_methods": true/false,
            "has_structure_description": true/false,
            "errors": ["список ошибок"],
            "recommendations": ["рекомендации"]
        }},
        
        "main_body": {{
            "present": true/false,
            "has_sections": true/false,
            "sections_count": 0,
            "has_subsections": true/false,
            "has_theoretical_part": true/false,
            "has_practical_part": true/false,
            "errors": ["список ошибок"],
            "recommendations": ["рекомендации"]
        }},
        
        "conclusion": {{
            "present": true/false,
            "has_conclusions": true/false,
            "has_results": true/false,
            "errors": ["список ошибок"],
            "recommendations": ["рекомендации"]
        }},
        
        "references": {{
            "present": true/false,
            "count": 0,
            "is_numbered": true/false,
            "errors": ["список ошибок оформления"],
            "recommendations": ["рекомендации"]
        }},
        
        "appendices": {{
            "present": true/false,
            "count": 0,
            "properly_labeled": true/false,
            "errors": ["список ошибок"],
            "recommendations": ["рекомендации"]
        }}
    }},
    
    "formatting_analysis": {{
        "font_appears_correct": true/false,
        "has_page_numbers": true/false,
        "sections_start_new_page": true/false,
        "headings_formatted": true/false,
        "errors": ["список ошибок форматирования"],
        "recommendations": ["рекомендации по форматированию"]
    }},
    
    "overall_compliance": {{
        "score": 0-100,
        "level": "высокий / средний / низкий",
        "summary": "общее заключение о соответствии документа требованиям ГОСТ"
    }},
    
    "missing_elements": [
        "список отсутствующих обязательных элементов"
    ],
    
    "corrections": [
        {{
            "section": "название раздела/элемента",
            "issue": "описание проблемы",
            "recommendation": "как исправить"
        }}
    ],
    
    "general_recommendations": [
        "общие рекомендации по улучшению документа"
    ],
    
    "error": null
}}"""

    try:
        response_text = call_ollama_api(prompt, system_instruction, max_output_tokens=8000, temperature=0.1)
        cleaned_response = clean_json_response(response_text)
        
        try:
            result = json.loads(cleaned_response)
            
            if not isinstance(result, dict):
                raise ValueError("Ответ не является JSON объектом")
            
            # Нормализация структуры
            result.setdefault('success', True)
            result. setdefault('document_type', 'не определён')
            result. setdefault('structure_analysis', {})
            result.setdefault('formatting_analysis', {})
            result.setdefault('overall_compliance', {'score': 0, 'level': 'низкий', 'summary': ''})
            result. setdefault('missing_elements', [])
            result.setdefault('corrections', [])
            result.setdefault('general_recommendations', [])
            result. setdefault('error', None)
            
            # Для совместимости
            result['processed_count'] = len(result.get('corrections', []))
            
            # Подсчёт найденных элементов
            structure = result.get('structure_analysis', {})
            found_count = sum(1 for key in structure if structure. get(key, {}).get('present', False))
            result['total_found'] = found_count
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            return {
                "success": False,
                "document_type": "не определён",
                "structure_analysis": {},
                "formatting_analysis": {},
                "overall_compliance": {"score": 0, "level": "низкий", "summary": "Ошибка анализа"},
                "missing_elements": [],
                "corrections": [],
                "general_recommendations": [],
                "processed_count": 0,
                "total_found": 0,
                "error": f"Ошибка парсинга ответа ИИ: {str(e)}",
                "raw_response": cleaned_response[:2000]
            }
            
    except Exception as e:
        print(f"Ошибка при анализе документа: {e}")
        return {
            "success": False,
            "document_type": "не определён",
            "structure_analysis": {},
            "formatting_analysis": {},
            "overall_compliance": {"score": 0, "level": "низкий", "summary": "Ошибка анализа"},
            "missing_elements": [],
            "corrections": [],
            "general_recommendations": [],
            "processed_count": 0,
            "total_found": 0,
            "error": str(e)
        }


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_document(file_path: str, text_content: str, gost_id: int, db_session) -> dict:
    """
    Главная функция анализа документа. 
    Выбирает метод анализа в зависимости от типа файла и ГОСТа. 
    Сначала пробует анализ через изображения, затем текстовый анализ.
    """
    gost = db_session.query(GOST).filter_by(id=gost_id).one_or_none() if gost_id else None
    gost_name = gost.name if gost else "ГОСТ Р 7.0.5-2008"
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Для PDF и DOCX пробуем анализ через изображения
    if file_ext in ['.pdf', '. docx', '.doc'] and PYMUPDF_AVAILABLE:
        try:
            print(f"🖼️ Используем анализ через изображения для {file_ext}")
            result = analyze_document_with_images(file_path, gost_name)
            if result. get('success'):
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


# ============================================================================
# FILE PROCESSING FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла."""
    return '.' in filename and filename. rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def check_command_available(command: str) -> bool:
    """Проверяет, доступна ли команда в системе."""
    import subprocess
    try:
        subprocess.run(['which', command], capture_output=True, check=True, timeout=5)
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
    import platform
    import subprocess
    
    pdf_filename = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    system = platform.system().lower()
    
    print(f"🔄 Начинаем конвертацию DOCX в PDF (ОС: {system})...")
    
    # Метод 1: LibreOffice (работает в Linux, Windows, macOS)
    if check_command_available('libreoffice'):
        try:
            print("📄 Попытка конвертации через LibreOffice...")
            # Используем абсолютный путь для избежания проблем с путями
            abs_docx_path = os.path.abspath(docx_path)
            abs_output_dir = os.path.abspath(output_dir)
            
            result = subprocess.run([
                'libreoffice', '--headless', '--nodefault', '--nolockcheck',
                '--convert-to', 'pdf',
                '--outdir', abs_output_dir,
                abs_docx_path
            ], capture_output=True, timeout=120, check=False, text=True)
            
            # LibreOffice создаёт файл с тем же базовым именем
            base_name = os.path.splitext(os.path.basename(docx_path))[0]
            possible_pdf = os.path.join(abs_output_dir, base_name + ".pdf")
            
            if os.path.exists(possible_pdf):
                # Переименовываем в нужное имя, если отличается
                if possible_pdf != pdf_path:
                    os.rename(possible_pdf, pdf_path)
                print(f"✅ DOCX конвертирован в PDF через LibreOffice: {pdf_path}")
                if result.stdout:
                    print(f"   Вывод LibreOffice: {result.stdout[:200]}")
                return pdf_path
            else:
                print(f"⚠️ LibreOffice не создал файл. Код возврата: {result.returncode}")
                if result.stderr:
                    print(f"   Ошибка: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print("⚠️ LibreOffice превысил время ожидания")
        except Exception as e:
            print(f"⚠️ Ошибка LibreOffice: {e}")
    
    # Метод 2: unoconv (обёртка над LibreOffice, часто проще в использовании)
    if check_command_available('unoconv'):
        try:
            print("📄 Попытка конвертации через unoconv...")
            abs_docx_path = os.path.abspath(docx_path)
            abs_output_dir = os.path.abspath(output_dir)
            
            result = subprocess.run([
                'unoconv', '-f', 'pdf', '-o', pdf_path, abs_docx_path
            ], capture_output=True, timeout=120, check=False, text=True)
            
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
    
    # Метод 3: pandoc (универсальный конвертер документов)
    if check_command_available('pandoc'):
        try:
            print("📄 Попытка конвертации через pandoc...")
            abs_docx_path = os.path.abspath(docx_path)
            
            result = subprocess.run([
                'pandoc', abs_docx_path, '-o', pdf_path
            ], capture_output=True, timeout=120, check=False, text=True)
            
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
    
    # Метод 4: docx2pdf (работает только на Windows/Mac с установленным MS Word)
    if DOCX2PDF_AVAILABLE and system != 'linux':
        try:
            print("📄 Попытка конвертации через docx2pdf...")
            docx_to_pdf_convert(docx_path, pdf_path)
            if os.path.exists(pdf_path):
                print(f"✅ DOCX конвертирован в PDF через docx2pdf: {pdf_path}")
                return pdf_path
        except Exception as e:
            print(f"⚠️ Ошибка docx2pdf: {e}")
    
    # Если ничего не сработало, выдаём понятное сообщение об ошибке
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
        
        ext = os.path. splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            # Сначала пробуем PyMuPDF (лучше качество)
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(file_path)
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text())
                    doc.close()
                    text = '\n'.join(text_parts)
                    if text. strip():
                        print(f"✅ PDF прочитан через PyMuPDF: {len(text)} символов")
                        return text
                except Exception as e:
                    print(f"⚠️ Ошибка PyMuPDF: {e}")
            
            # Запасной вариант - PyPDF2
            if PYPDF2_AVAILABLE:
                try:
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2. PdfReader(f)
                        if len(reader.pages) == 0:
                            print("⚠️ PDF файл не содержит страниц")
                            return None
                        
                        text_parts = []
                        for page_num, page in enumerate(reader.pages, 1):
                            try:
                                page_text = page. extract_text()
                                if page_text:
                                    text_parts. append(page_text)
                            except Exception as e:
                                print(f"⚠️ Ошибка чтения страницы {page_num}: {e}")
                        
                        if not text_parts:
                            print("⚠️ Не удалось извлечь текст из PDF")
                            return None
                        
                        text = '\n'.join(text_parts)
                        print(f"✅ PDF прочитан через PyPDF2: {len(text)} символов, {len(reader.pages)} страниц")
                        return text
                        
                except Exception as pdf_err:
                    print(f"❌ Ошибка чтения PDF: {pdf_err}")
                    return None
        
        elif ext == '.docx' and DOCX_AVAILABLE:
            try:
                doc = docx.Document(file_path)
                paragraphs = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        paragraphs.append(para.text)
                
                if not paragraphs:
                    print("⚠️ DOCX файл не содержит текста")
                    return None
                
                text = '\n'.join(paragraphs)
                print(f"✅ DOCX прочитан: {len(text)} символов, {len(paragraphs)} параграфов")
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


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_current_user(db_session):
    """Получает текущего пользователя из сессии."""
    user_id = session.get('user_id')
    if user_id:
        return db_session.query(User). get(user_id)
    return None


# ============================================================================
# FLASK REQUEST HANDLERS
# ============================================================================

@app.before_request
def before_request():
    """Создаёт сессию БД для каждого запроса."""
    g.db_session = get_session()


@app.teardown_request
def teardown_request(exception):
    """Закрывает сессию БД после запроса."""
    db_session = g. pop('db_session', None)
    if db_session:
        db_session.close()


# ============================================================================
# ROUTES
# ============================================================================
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    db = g.db_session
    if request.method == 'POST':
        login_input = request.form.get('login')
        password = request.form.get('password')
        client_type = request.form.get('client_type')
        company_key = request.form.get('company_key')

        user = db.query(User).filter_by(login=login_input, client_type=client_type).one_or_none()
        
        if user and user.check_password(password):
            valid = True
            if client_type == 'company':
                key_obj = db.query(KeyCompany).filter_by(
                    key_value=company_key, 
                    company_id=user.company_id, 
                    is_active=True
                ).one_or_none()
                if not key_obj:
                    valid = False
            
            if valid:
                session['user_id'] = user.id
                session['client_type'] = user.client_type
                flash(f'Добро пожаловать, {user.login}!', 'success')
                return redirect(url_for('lk_company' if user.client_type == 'company' else 'lk_private'))
            else:
                flash('Неверный ключ компании.', 'error')
        else:
            flash('Неверный логин или пароль.', 'error')
            
    return render_template('login.html')


@app.route('/registration', methods=['GET', 'POST'])
def registration():
    db = g.db_session
    if request.method == 'POST':
        login_input = request.form.get('login')
        email = request.form.get('email')
        password = request.form.get('password')
        client_type = request.form.get('client_type')
        activity_type = request.form.get('activity_type')
        company_key = request.form.get('company_key')

        if db.query(User).filter_by(login=login_input).count() > 0:
            flash('Логин занят.', 'error')
            return redirect(url_for('registration'))
        if db.query(User).filter_by(email=email).count() > 0:
            flash('Email занят.', 'error')
            return redirect(url_for('registration'))
        
        company_id = None
        if client_type == 'company':
            key_obj = db.query(KeyCompany).filter_by(key_value=company_key, is_active=True).one_or_none()
            if not key_obj:
                flash('Неверный ключ компании.', 'error')
                return redirect(url_for('registration'))
            company_id = key_obj.company_id
        
        user = User(
            login=login_input, 
            email=email, 
            client_type=client_type, 
            activity_type=activity_type, 
            company_id=company_id
        )
        user.set_password(password)
        
        try:
            db.add(user)
            db.commit()
            flash('Аккаунт создан! Теперь войдите.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            flash(f'Ошибка: {e}', 'error')
            return redirect(url_for('registration'))
            
    return render_template('registration.html')


@app.route('/lk')
@app.route('/lk-private')
def lk_private():
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for('login'))
    if user.client_type != 'private':
        return redirect(url_for('lk_company'))
    
    uploads = db.query(UserUpload).filter_by(user_id=user.id).order_by(UserUpload.upload_date.desc()).all()
    return render_template('lk.html', user=user, uploads=uploads)


@app.route('/lk-company')
def lk_company():
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for('login'))
    if user.client_type != 'company':
        return redirect(url_for('lk_private'))
    
    uploads = db.query(UserUpload).join(User).filter(User.company_id == user.company_id).order_by(UserUpload.upload_date.desc()).all()
    return render_template('lk_company.html', user=user, uploads=uploads)


@app.route('/check-file', methods=['GET', 'POST'])
def check_file():
    """Страница загрузки и проверки файла."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_session()
    user = db.query(User).filter_by(id=session['user_id']).one_or_none()
    
    if not user:
        db.close()
        return redirect(url_for('login'))
    
    # Получаем доступные ГОСТы
    if user.client_type == 'company':
        gosts = db.query(GOST).all()
    else:
        gosts = db.query(GOST).filter_by(client_type_for='all').all()
    
    # Для API предупреждения
    api_warning = None
    if not IS_API_CONFIGURED:
        api_warning = "API ключ не настроен"
    
    if request.method == 'POST':
        print("📤 Получен POST запрос")
        print(f"📤 Form data keys: {list(request.form. keys())}")
        print(f"📤 Files keys: {list(request.files.keys())}")
        
        # ИСПРАВЛЕНО: ищем 'file_upload' вместо 'file'
        if 'file_upload' not in request.files:
            flash('Файл не найден в запросе', 'error')
            db.close()
            return redirect(request.url)
        
        file = request.files['file_upload']
        print(f"📁 Файл: {file.filename}")
        
        if file.filename == '' or file.filename is None:
            flash('Файл не выбран', 'error')
            db.close()
            return redirect(request. url)
        
        # Проверяем расширение файла
        if not allowed_file(file.filename):
            flash('Неподдерживаемый формат файла.  Разрешены: .pdf, . docx', 'error')
            db.close()
            return redirect(request.url)
        
        # ИСПРАВЛЕНО: получаем gost_id по правильному имени поля 'gost_select'
        gost_id = request.form.get('gost_select', type=int)
        print(f"📋 ГОСТ ID: {gost_id}")
        
        if not gost_id:
            flash('Выберите стандарт (ГОСТ)', 'error')
            db.close()
            return redirect(request.url)
        
        # Проверка API
        if not IS_API_CONFIGURED:
            flash('Ошибка: Ollama сервер недоступен. Проверьте подключение к серверу.', 'error')
            db.close()
            return redirect(request.url)
        
        # Сохраняем файл
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1]. lower()
        original_filename = filename
        original_unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Создаём папку uploads если не существует
        uploads_dir = os. path.join(app.root_path, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        original_file_path = os. path.join(uploads_dir, original_unique_filename)
        file.save(original_file_path)
        print(f"💾 Оригинальный файл сохранён: {original_file_path}")
        
        # Конвертируем DOCX в PDF перед анализом
        file_path = original_file_path
        unique_filename = original_unique_filename
        pdf_path = None
        
        if file_ext in ['.docx', '.doc']:
            try:
                print(f"🔄 Конвертируем {file_ext} в PDF...")
                pdf_path = convert_docx_to_pdf(original_file_path, uploads_dir)
                
                # Используем PDF для анализа
                file_path = pdf_path
                unique_filename = os.path.basename(pdf_path)
                file_ext = '.pdf'
                print(f"✅ Файл конвертирован в PDF: {pdf_path}")
            except Exception as e:
                print(f"❌ Ошибка конвертации DOCX в PDF: {e}")
                flash(f'Ошибка конвертации файла в PDF: {str(e)}', 'error')
                db.close()
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
            
            if file_ext == '.pdf' and PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(file_path)
                    text_content = '\n'.join([page.get_text() for page in doc])
                    doc.close()
                    print(f"✅ Текст извлечён из PDF: {len(text_content)} символов")
                except Exception as e:
                    print(f"⚠️ Ошибка чтения PDF: {e}")
            elif file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
            
            # Анализируем документ (используем PDF файл)
            print(f"🔍 Начинаем анализ файла: {original_filename} (конвертирован в PDF: {unique_filename}), ГОСТ ID: {gost_id}")
            analysis_result = analyze_document(file_path, text_content, gost_id, db)
            print(f"✅ Результат анализа: success={analysis_result. get('success')}")
            
            # Сохраняем результат в БД
            # Сохраняем оригинальное имя файла, но путь к PDF
            upload = UserUpload(
                filename=original_filename,  # Оригинальное имя
                file_path=unique_filename,   # Путь к PDF файлу
                user_id=user.id,
                gost_id=gost_id,
                status='Проверено' if analysis_result. get('success') else 'Ошибка',
                report_json=json.dumps({'gost_processing': analysis_result}, ensure_ascii=False),
                upload_date=datetime.now()
            )
            db.add(upload)
            db.commit()
            
            upload_id = upload. id
            print(f"✅ Сохранено в БД, ID: {upload_id}")
            
            # Удаляем оригинальный DOCX файл, если был создан PDF
            if pdf_path and os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                    print(f"🗑️ Оригинальный DOCX файл удалён: {original_file_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить оригинальный файл: {e}")
            
            if analysis_result.get('success'):
                flash('Файл успешно обработан!', 'success')
            else:
                flash(f'Ошибка обработки: {analysis_result.get("error", "Неизвестная ошибка")}', 'error')
            
            db.close()
            return redirect(url_for('process_file', upload_id=upload_id))
            
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
                file_path=unique_filename if 'unique_filename' in locals() else original_unique_filename,
                user_id=user.id,
                gost_id=gost_id,
                status='Ошибка',
                report_json=json.dumps({'gost_processing': {'success': False, 'error': str(e)}}, ensure_ascii=False),
                upload_date=datetime. now()
            )
            db.add(upload)
            db.commit()
            upload_id = upload. id
            
            flash(f'Ошибка обработки файла: {str(e)}', 'error')
            db.close()
            
            return redirect(url_for('process_file', upload_id=upload_id))
    
    # GET запрос - показываем форму
    return_route = url_for('lk_company') if user.client_type == 'company' else url_for('lk_private')
    
    db.close()
    return render_template('check.html', 
                          user=user, 
                          gosts=gosts, 
                          return_route=return_route,
                          api_warning=api_warning,
                          is_api_configured=IS_API_CONFIGURED)


@app.route('/process-file/<int:upload_id>')
def process_file(upload_id):
    """Отображение результатов обработки файла."""
    db = g.db_session
    user = get_current_user(db)
    if not user:
        return redirect(url_for('login'))
    
    upload = db.query(UserUpload).filter_by(id=upload_id).one_or_none()
    if not upload:
        return redirect(url_for('lk_private'))
    
    # Проверка прав доступа
    if upload.user_id != user.id and not (user.client_type == 'company' and upload.user.company_id == user.company_id):
        return redirect(url_for('lk_private'))

    gost_obj = db.query(GOST).filter_by(id=upload.gost_id).one_or_none()
    
    # Парсинг результата
    result = None
    if upload.report_json:
        try:
            data = json.loads(upload.report_json)
            result = data.get('gost_processing')
        except:
            pass

    return_route = url_for('lk_company') if user.client_type == 'company' else url_for('lk_private')
    return render_template('process-file.html', upload=upload, user=user, gost=gost_obj, 
                         result=result, return_route=return_route)


@app.route('/work-details/<int:upload_id>')
def work_details(upload_id):
    return redirect(url_for('process_file', upload_id=upload_id))


@app.route('/settings')
def settings():
    user = get_current_user(g.db_session)
    if not user:
        return redirect(url_for('login'))
    return_route = url_for('lk_company') if user.client_type == 'company' else url_for('lk_private')
    return render_template('settings.html', user=user, return_route=return_route)


@app.route('/password-recovery', methods=['GET', 'POST'])
def password_recovery():
    return render_template('password-recovery.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Запуск WorkWise Application")
    print("="*60)
    initialize_database()
    print("="*60 + "\n")
    app.run(debug=True, port=5001)
