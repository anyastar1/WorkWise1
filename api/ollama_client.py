"""
Клиент для работы с Ollama API
"""

import json
import time
import requests
from typing import List
from datetime import datetime
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

# Глобальная переменная для проверки доступности API
_is_api_configured = None


def check_ollama_available() -> bool:
    """Проверяет доступность Ollama сервера."""
    global _is_api_configured
    if _is_api_configured is not None:
        return _is_api_configured

    try:
        test_url = f"{OLLAMA_BASE_URL}/api/tags"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            _is_api_configured = True
            return True
        else:
            print(f"⚠️  Ollama сервер вернул код {response.status_code}")
            _is_api_configured = False
            return False
    except requests.exceptions.ConnectionError:
        print(
            f"⚠️  Не удалось подключиться к Ollama серверу по адресу {OLLAMA_BASE_URL}"
        )
        _is_api_configured = False
        return False
    except Exception as e:
        print(f"⚠️  Ошибка при проверке Ollama: {e}")
        _is_api_configured = False
        return False


def is_api_configured() -> bool:
    """Возвращает статус настройки API."""
    if _is_api_configured is None:
        check_ollama_available()
    return _is_api_configured or False


def call_ollama_api(
    prompt, system_instruction=None, max_output_tokens=4000, temperature=0.3
):
    """
    Вызывает Ollama API с заданным промптом.

    Args:
        prompt: Текст запроса пользователя
        system_instruction: Системная инструкция (опционально)
        max_output_tokens: Максимальное количество токенов в ответе
        temperature: Температура генерации (0.0-1.0)

    Returns:
        str: Ответ от API
    """
    if not is_api_configured():
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
            "num_predict": max_output_tokens if max_output_tokens else 4000,
        },
    }

    headers = {"Content-Type": "application/json"}

    api_url = f"{OLLAMA_BASE_URL}/api/generate"

    # Подробное логирование запроса
    print("\n" + "=" * 80)
    print("📤 ЗАПРОС К OLLAMA API")
    print("=" * 80)
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
    print("-" * 80)

    start_time = time.time()

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=300,  # Увеличенный таймаут для больших запросов
        )

        elapsed_time = time.time() - start_time

        # Подробное логирование ответа
        print("\n" + "=" * 80)
        print("📥 ОТВЕТ ОТ OLLAMA API")
        print("=" * 80)
        print(f"📊 HTTP статус: {response.status_code}")
        print(
            f"⏱️  Время выполнения: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)"
        )
        print(f"📏 Размер ответа: {len(response.content)} байт")

        if response.status_code != 200:
            error_msg = f"Ошибка Ollama API (код {response.status_code})"
            try:
                error_data = response.json()
                print(
                    f"❌ Ошибка в JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}"
                )
                if "error" in error_data:
                    error_msg = f"Ошибка Ollama: {error_data['error']}"
            except:
                error_text = response.text[:500]
                print(f"❌ Текст ошибки: {error_text}")
                error_msg = f"Ошибка Ollama API: {error_text}"
            print("=" * 80 + "\n")
            raise ValueError(error_msg)

        data = response.json()

        # Логируем метаданные из ответа
        print(f"📦 Ключи в ответе: {list(data.keys())}")

        if "model" in data:
            print(f"🤖 Модель в ответе: {data['model']}")
        if "created_at" in data:
            print(f"🕐 Создано: {data['created_at']}")
        if "done" in data:
            print(f"✅ Завершено: {data['done']}")
        if "total_duration" in data:
            print(
                f"⏱️  Общее время (от Ollama): {data['total_duration']/1e9:.2f} секунд"
            )
        if "load_duration" in data:
            print(f"⏳ Время загрузки модели: {data['load_duration']/1e9:.2f} секунд")
        if "prompt_eval_count" in data:
            print(f"📝 Токенов в промпте: {data['prompt_eval_count']}")
        if "eval_count" in data:
            print(f"📤 Токенов в ответе: {data['eval_count']}")
        if "eval_duration" in data:
            print(f"⏱️  Время генерации: {data['eval_duration']/1e9:.2f} секунд")

        if "response" in data:
            content = data["response"]
            if content:
                print(f"✅ Длина ответа: {len(content)} символов")
                print(f"📄 Первые 300 символов ответа:")
                print("-" * 80)
                print(content[:300] + ("..." if len(content) > 300 else ""))
                print("-" * 80)
                if len(content) > 300:
                    print(f"📄 Последние 200 символов ответа:")
                    print("-" * 80)
                    print("..." + content[-200:])
                    print("-" * 80)
                print("=" * 80 + "\n")
                return content
            else:
                print("❌ Пустой ответ от API")
                print("=" * 80 + "\n")
                raise ValueError("Пустой ответ от API")
        else:
            print(f"❌ Неожиданный формат ответа. Полный ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            print("=" * 80 + "\n")
            raise ValueError(f"Неожиданный формат ответа: {data}")

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ Превышено время ожидания ({elapsed_time:.2f} секунд)")
        print("=" * 80 + "\n")
        raise ValueError("Превышено время ожидания ответа от Ollama API.")
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка подключения: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка подключения к Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка парсинга JSON: {str(e)}")
        print(f"📄 Первые 500 символов ответа: {response.text[:500]}")
        print("=" * 80 + "\n")
        raise ValueError("Некорректный JSON ответ от Ollama API")
    except ValueError as e:
        raise
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Неожиданная ошибка: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка при вызове Ollama API: {str(e)}")


def call_ollama_api_with_pdf(
    prompt: str,
    system_instruction: str,
    pdf_file_path: str,
    max_output_tokens: int = 8000,
    temperature: float = 0.1,
) -> str:
    """
    Вызывает Ollama API с PDF файлом напрямую (без преобразования в изображения).
    
    Args:
        prompt: Текстовый промпт
        system_instruction: Системная инструкция
        pdf_file_path: Путь к PDF файлу
        max_output_tokens: Максимальное количество токенов в ответе
        temperature: Температура генерации
        
    Returns:
        Ответ от API
    """
    if not is_api_configured():
        raise ValueError("Ollama сервер недоступен. Проверьте подключение к серверу.")
    
    import base64
    import os
    
    # Проверяем существование файла
    if not os.path.exists(pdf_file_path):
        raise ValueError(f"PDF файл не найден: {pdf_file_path}")
    
    # Читаем PDF файл и конвертируем в base64
    print(f"📄 Читаю PDF файл: {pdf_file_path}")
    with open(pdf_file_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    
    file_size_mb = len(pdf_bytes) / 1024 / 1024
    base64_size_mb = len(pdf_base64) / 1024 / 1024
    
    print(f"✅ PDF прочитан: {file_size_mb:.2f} MB (base64: {base64_size_mb:.2f} MB)")
    
    # Проверяем размер (максимум 50MB для base64)
    max_total_size = 50 * 1024 * 1024  # 50MB
    if len(pdf_base64) > max_total_size:
        raise ValueError(
            f"PDF файл слишком большой: {base64_size_mb:.2f} MB "
            f"(максимум {max_total_size/1024/1024:.2f} MB)"
        )
    
    # Формируем промпт с системной инструкцией
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n{prompt}"
    
    # Для vision моделей Ollama можно отправить PDF как base64 в массиве images
    # Некоторые модели могут обрабатывать PDF напрямую
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "images": [pdf_base64],  # PDF как base64 в массиве images
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens if max_output_tokens else 8000,
        },
    }
    
    headers = {"Content-Type": "application/json"}
    api_url = f"{OLLAMA_BASE_URL}/api/generate"
    
    # Подробное логирование запроса
    print("\n" + "=" * 80)
    print("📤 ЗАПРОС К OLLAMA API (С PDF ФАЙЛОМ)")
    print("=" * 80)
    print(f"🔗 URL: {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📄 PDF файл: {pdf_file_path}")
    print(f"📊 Размер файла: {file_size_mb:.2f} MB")
    print(f"📦 Размер base64: {base64_size_mb:.2f} MB")
    print(f"📝 Длина промпта: {len(prompt)} символов")
    if system_instruction:
        print(f"⚙️  Длина системной инструкции: {len(system_instruction)} символов")
    print(f"📊 Длина полного промпта: {len(full_prompt)} символов")
    print(f"🌡️  Temperature: {temperature}")
    print(f"🔢 Max tokens: {max_output_tokens}")
    print(f"⏰ Время начала запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    preview = full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
    print(f"📄 Превью промпта: {preview}")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        print(f"📤 Отправка PDF файла в Ollama...")
        response = requests.post(
            api_url, headers=headers, json=payload, timeout=600
        )  # Увеличенный таймаут для PDF
        
        elapsed_time = time.time() - start_time
        
        # Подробное логирование ответа
        print("\n" + "=" * 80)
        print("📥 ОТВЕТ ОТ OLLAMA API (С PDF ФАЙЛОМ)")
        print("=" * 80)
        print(f"📊 HTTP статус: {response.status_code}")
        print(
            f"⏱️  Время выполнения: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)"
        )
        print(f"📏 Размер ответа: {len(response.content)} байт")
        
        if response.status_code != 200:
            error_msg = f"Ошибка Ollama API (код {response.status_code})"
            try:
                error_data = response.json()
                print(
                    f"❌ Ошибка в JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}"
                )
                if "error" in error_data:
                    error_msg = f"Ошибка Ollama: {error_data['error']}"
            except:
                error_text = response.text[:500]
                print(f"❌ Текст ошибки: {error_text}")
                error_msg = f"Ошибка Ollama API: {error_text}"
            print("=" * 80 + "\n")
            raise ValueError(error_msg)
        
        data = response.json()
        
        # Логируем метаданные из ответа
        print(f"📦 Ключи в ответе: {list(data.keys())}")
        
        if "model" in data:
            print(f"🤖 Модель в ответе: {data['model']}")
        if "created_at" in data:
            print(f"🕐 Создано: {data['created_at']}")
        if "done" in data:
            print(f"✅ Завершено: {data['done']}")
        if "total_duration" in data:
            print(
                f"⏱️  Общее время (от Ollama): {data['total_duration']/1e9:.2f} секунд"
            )
        if "load_duration" in data:
            print(f"⏳ Время загрузки модели: {data['load_duration']/1e9:.2f} секунд")
        if "prompt_eval_count" in data:
            print(f"📝 Токенов в промпте: {data['prompt_eval_count']}")
        if "eval_count" in data:
            print(f"📤 Токенов в ответе: {data['eval_count']}")
        if "eval_duration" in data:
            print(f"⏱️  Время генерации: {data['eval_duration']/1e9:.2f} секунд")
        
        if "response" in data:
            content = data["response"]
            print(f"✅ Длина ответа: {len(content)} символов")
            print(f"📄 Первые 300 символов ответа:")
            print("-" * 80)
            print(content[:300] + ("..." if len(content) > 300 else ""))
            print("-" * 80)
            if len(content) > 300:
                print(f"📄 Последние 200 символов ответа:")
                print("-" * 80)
                print("..." + content[-200:])
                print("-" * 80)
            print("=" * 80 + "\n")
            return content
        else:
            print(f"❌ Неожиданный формат ответа. Полный ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            print("=" * 80 + "\n")
            raise ValueError(f"Неожиданный формат ответа: {data}")
    
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ Превышено время ожидания ({elapsed_time:.2f} секунд)")
        print("=" * 80 + "\n")
        raise ValueError("Превышено время ожидания ответа от Ollama API.")
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка подключения: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка подключения к Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка парсинга JSON: {str(e)}")
        print(f"📄 Первые 500 символов ответа: {response.text[:500]}")
        print("=" * 80 + "\n")
        raise ValueError("Некорректный JSON ответ от Ollama API")
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Неожиданная ошибка: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка обработки ответа: {e}")


def call_ollama_api_with_images(
    prompt: str,
    system_instruction: str,
    images_base64: List[str],
    max_output_tokens: int = 8000,
    temperature: float = 0.1,
) -> str:
    """
    Вызывает Ollama API с изображениями.

    Args:
        prompt: Текстовый промпт
        system_instruction: Системная инструкция
        images_base64: Список base64 закодированных изображений
        max_output_tokens: Максимальное количество токенов в ответе
        temperature: Температура генерации

    Returns:
        Ответ от API
    """
    if not is_api_configured():
        raise ValueError("Ollama сервер недоступен. Проверьте подключение к серверу.")

    # Формируем промпт с системной инструкцией
    # Для vision моделей Ollama системная инструкция добавляется в промпт
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n{prompt}"

    # Очищаем base64 строки от префикса если есть
    cleaned_images = []
    for img_base64 in images_base64:
        if not img_base64:
            continue
        # Убираем префикс data:image/png;base64, если есть
        if "," in img_base64:
            img_base64 = img_base64.split(",", 1)[1]
        # Проверяем, что это валидный base64 (не пустая строка)
        if img_base64.strip():
            cleaned_images.append(img_base64)

    if not cleaned_images:
        raise ValueError("Нет валидных изображений для обработки")

    # Ограничиваем количество изображений (максимум 10 для стабильности)
    max_images = min(len(cleaned_images), 10)
    images_to_send = cleaned_images[:max_images]

    # Вычисляем размер изображений
    total_image_size = sum(len(img) for img in images_to_send)
    
    # Проверяем общий размер (примерно 50MB максимум для base64)
    max_total_size = 50 * 1024 * 1024  # 50MB
    if total_image_size > max_total_size:
        raise ValueError(
            f"Общий размер изображений слишком большой: {total_image_size/1024/1024:.2f} MB "
            f"(максимум {max_total_size/1024/1024:.2f} MB)"
        )

    # Формируем payload для vision модели
    # Для qwen3-vl используется формат с полем "images" как массив base64 строк
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "images": images_to_send,  # Массив base64 строк БЕЗ префикса data:image/...
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens if max_output_tokens else 8000,
        },
    }

    headers = {"Content-Type": "application/json"}
    api_url = f"{OLLAMA_BASE_URL}/api/generate"

    # Подробное логирование запроса
    print("\n" + "=" * 80)
    print("📤 ЗАПРОС К OLLAMA API (С ИЗОБРАЖЕНИЯМИ)")
    print("=" * 80)
    print(f"🔗 URL: {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📝 Длина промпта: {len(prompt)} символов")
    if system_instruction:
        print(f"⚙️  Длина системной инструкции: {len(system_instruction)} символов")
    print(f"📊 Длина полного промпта: {len(full_prompt)} символов")
    print(
        f"🖼️  Количество изображений: {max_images} (из {len(images_base64)} переданных)"
    )
    print(
        f"📦 Общий размер изображений (base64): {total_image_size:,} символов ({total_image_size/1024/1024:.2f} MB)"
    )
    for i, img in enumerate(
        images_to_send[:3], 1
    ):  # Показываем размер первых 3 изображений
        print(f"   Изображение {i}: {len(img):,} символов ({len(img)/1024:.2f} KB)")
    if len(images_to_send) > 3:
        print(f"   ... и ещё {len(images_to_send) - 3} изображений")
    print(f"🌡️  Temperature: {temperature}")
    print(f"🔢 Max tokens: {max_output_tokens}")
    print(f"⏰ Время начала запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Показываем первые 200 символов промпта для отладки
    preview = full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
    print(f"📄 Превью промпта: {preview}")
    print("-" * 80)

    start_time = time.time()

    try:
        print(f"📤 Отправка запроса с изображениями в Ollama...")
        response = requests.post(
            api_url, headers=headers, json=payload, timeout=600
        )  # Увеличенный таймаут для изображений

        elapsed_time = time.time() - start_time

        # Подробное логирование ответа
        print("\n" + "=" * 80)
        print("📥 ОТВЕТ ОТ OLLAMA API (С ИЗОБРАЖЕНИЯМИ)")
        print("=" * 80)
        print(f"📊 HTTP статус: {response.status_code}")
        print(
            f"⏱️  Время выполнения: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)"
        )
        print(f"📏 Размер ответа: {len(response.content)} байт")

        if response.status_code != 200:
            error_msg = f"Ошибка Ollama API (код {response.status_code})"
            try:
                error_data = response.json()
                print(
                    f"❌ Ошибка в JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}"
                )
                if "error" in error_data:
                    error_msg = f"Ошибка Ollama: {error_data['error']}"
            except:
                error_text = response.text[:500]
                print(f"❌ Текст ошибки: {error_text}")
                error_msg = f"Ошибка Ollama API: {error_text}"
            print("=" * 80 + "\n")
            raise ValueError(error_msg)

        data = response.json()

        # Логируем метаданные из ответа
        print(f"📦 Ключи в ответе: {list(data.keys())}")

        if "model" in data:
            print(f"🤖 Модель в ответе: {data['model']}")
        if "created_at" in data:
            print(f"🕐 Создано: {data['created_at']}")
        if "done" in data:
            print(f"✅ Завершено: {data['done']}")
        if "total_duration" in data:
            print(
                f"⏱️  Общее время (от Ollama): {data['total_duration']/1e9:.2f} секунд"
            )
        if "load_duration" in data:
            print(f"⏳ Время загрузки модели: {data['load_duration']/1e9:.2f} секунд")
        if "prompt_eval_count" in data:
            print(f"📝 Токенов в промпте: {data['prompt_eval_count']}")
        if "eval_count" in data:
            print(f"📤 Токенов в ответе: {data['eval_count']}")
        if "eval_duration" in data:
            print(f"⏱️  Время генерации: {data['eval_duration']/1e9:.2f} секунд")

        if "response" in data:
            content = data["response"]
            print(f"✅ Длина ответа: {len(content)} символов")
            print(f"📄 Первые 300 символов ответа:")
            print("-" * 80)
            print(content[:300] + ("..." if len(content) > 300 else ""))
            print("-" * 80)
            if len(content) > 300:
                print(f"📄 Последние 200 символов ответа:")
                print("-" * 80)
                print("..." + content[-200:])
                print("-" * 80)
            print("=" * 80 + "\n")
            return content
        else:
            print(f"❌ Неожиданный формат ответа. Полный ответ:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            print("=" * 80 + "\n")
            raise ValueError(f"Неожиданный формат ответа: {data}")

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ Превышено время ожидания ({elapsed_time:.2f} секунд)")
        print("=" * 80 + "\n")
        raise ValueError("Превышено время ожидания ответа от Ollama API.")
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка подключения: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка подключения к Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Ошибка парсинга JSON: {str(e)}")
        print(f"📄 Первые 500 символов ответа: {response.text[:500]}")
        print("=" * 80 + "\n")
        raise ValueError("Некорректный JSON ответ от Ollama API")
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Неожиданная ошибка: {str(e)}")
        print(f"⏱️  Время до ошибки: {elapsed_time:.2f} секунд")
        print("=" * 80 + "\n")
        raise ValueError(f"Ошибка обработки ответа: {e}")
