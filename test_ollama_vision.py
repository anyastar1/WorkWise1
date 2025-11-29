#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Ollama и работы с vision моделью qwen3-vl:4b-instruct
"""

import requests
import json
import base64
from PIL import Image
import io
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


def create_test_image_base64():
    """Создает простое тестовое изображение с текстом."""
    # Создаем простое изображение 200x100 с текстом
    img = Image.new('RGB', (200, 100), color='white')
    from PIL import ImageDraw, ImageFont
    
    draw = ImageDraw.Draw(img)
    # Пробуем использовать стандартный шрифт
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    draw.text((10, 40), "Test Image", fill='black', font=font)
    
    # Конвертируем в base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return img_base64


def test_ollama_connection():
    """Проверяет подключение к Ollama серверу."""
    print("=" * 80)
    print("🔍 ТЕСТ 1: Проверка подключения к Ollama")
    print("=" * 80)
    
    try:
        test_url = f"{OLLAMA_BASE_URL}/api/tags"
        print(f"📡 Проверяю подключение к {test_url}...")
        response = requests.get(test_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            print(f"✅ Подключение успешно!")
            print(f"📋 Доступные модели: {len(models)}")
            
            # Проверяем наличие нужной модели
            model_names = [m.get('name', '') for m in models]
            if OLLAMA_MODEL in model_names:
                print(f"✅ Модель {OLLAMA_MODEL} найдена!")
            else:
                print(f"⚠️  Модель {OLLAMA_MODEL} не найдена в списке")
                print(f"   Доступные модели: {', '.join(model_names[:5])}")
            
            return True
        else:
            print(f"❌ Ошибка: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться к {OLLAMA_BASE_URL}")
        print("   Проверьте, что Ollama сервер запущен и доступен")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_text_generation():
    """Тестирует генерацию текста без изображений."""
    print("\n" + "=" * 80)
    print("🔍 ТЕСТ 2: Генерация текста (без изображений)")
    print("=" * 80)
    
    api_url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Привет! Ответь коротко: что такое Python?",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 100,
        }
    }
    
    print(f"📤 Отправляю запрос к {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📝 Промпт: {payload['prompt']}")
    
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                answer = data["response"]
                print(f"✅ Успешно получен ответ:")
                print(f"📄 Ответ: {answer[:200]}...")
                return True
            else:
                print(f"❌ Неожиданный формат ответа: {list(data.keys())}")
                return False
        else:
            print(f"❌ Ошибка HTTP {response.status_code}")
            print(f"   Ответ: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_vision_api():
    """Тестирует API с изображениями."""
    print("\n" + "=" * 80)
    print("🔍 ТЕСТ 3: Vision API с изображениями")
    print("=" * 80)
    
    # Создаем тестовое изображение
    print("🖼️  Создаю тестовое изображение...")
    img_base64 = create_test_image_base64()
    print(f"✅ Изображение создано, размер base64: {len(img_base64)} символов")
    
    api_url = f"{OLLAMA_BASE_URL}/api/generate"
    
    # Формируем промпт для vision модели
    prompt = "Опиши что ты видишь на этом изображении. Ответь кратко на русском языке."
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [img_base64],  # Массив base64 изображений
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,
        }
    }
    
    print(f"📤 Отправляю запрос к {api_url}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"📝 Промпт: {prompt}")
    print(f"🖼️  Количество изображений: 1")
    print(f"📦 Размер изображения: {len(img_base64)} символов ({len(img_base64)/1024:.2f} KB)")
    
    try:
        print("⏳ Ожидаю ответ (это может занять время)...")
        response = requests.post(api_url, json=payload, timeout=120)
        
        print(f"📊 HTTP статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if "response" in data:
                answer = data["response"]
                print(f"✅ Успешно получен ответ от vision модели:")
                print(f"📄 Ответ: {answer}")
                
                # Дополнительная информация
                if "eval_count" in data:
                    print(f"📊 Токенов в ответе: {data['eval_count']}")
                if "total_duration" in data:
                    print(f"⏱️  Время выполнения: {data['total_duration']/1e9:.2f} секунд")
                
                return True
            else:
                print(f"❌ Неожиданный формат ответа")
                print(f"   Ключи в ответе: {list(data.keys())}")
                print(f"   Полный ответ: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                return False
        else:
            print(f"❌ Ошибка HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Ошибка: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"   Текст ответа: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Превышено время ожидания (120 секунд)")
        print("   Vision модели могут требовать больше времени для обработки")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ollama_client_functions():
    """Тестирует функции из ollama_client.py."""
    print("\n" + "=" * 80)
    print("🔍 ТЕСТ 4: Использование функций из ollama_client.py")
    print("=" * 80)
    
    try:
        from api.ollama_client import check_ollama_available, is_api_configured, call_ollama_api_with_images
        
        print("📡 Проверяю доступность через check_ollama_available()...")
        is_available = check_ollama_available()
        print(f"   Результат: {'✅ Доступен' if is_available else '❌ Недоступен'}")
        
        print("📡 Проверяю через is_api_configured()...")
        is_configured = is_api_configured()
        print(f"   Результат: {'✅ Настроен' if is_configured else '❌ Не настроен'}")
        
        if is_configured:
            print("🖼️  Тестирую call_ollama_api_with_images()...")
            img_base64 = create_test_image_base64()
            
            prompt = "Что ты видишь на изображении? Ответь кратко."
            system_instruction = "Ты помощник для анализа изображений."
            
            try:
                response = call_ollama_api_with_images(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    images_base64=[img_base64],
                    max_output_tokens=200,
                    temperature=0.1
                )
                print(f"✅ Функция call_ollama_api_with_images() работает!")
                print(f"📄 Ответ: {response[:200]}...")
                return True
            except Exception as e:
                print(f"❌ Ошибка при вызове функции: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("⚠️  API не настроен, пропускаю тест функции")
            return False
            
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Запускает все тесты."""
    print("\n" + "=" * 80)
    print("🚀 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К OLLAMA И VISION МОДЕЛИ")
    print("=" * 80)
    print(f"🔗 URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print("=" * 80)
    
    results = []
    
    # Тест 1: Подключение
    results.append(("Подключение к Ollama", test_ollama_connection()))
    
    # Тест 2: Текстовая генерация
    results.append(("Генерация текста", test_text_generation()))
    
    # Тест 3: Vision API
    results.append(("Vision API с изображениями", test_vision_api()))
    
    # Тест 4: Функции из ollama_client.py
    results.append(("Функции ollama_client.py", test_ollama_client_functions()))
    
    # Итоги
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n📈 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройки и подключение.")


if __name__ == "__main__":
    main()
