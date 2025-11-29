#!/usr/bin/env python3
"""
Простой тест подключения к Ollama без зависимостей
"""

import sys
import os

# Проверяем наличие requests
try:
    import requests
    print("✅ requests установлен")
except ImportError:
    print("❌ requests не установлен. Установите: pip install requests")
    sys.exit(1)

# Проверяем конфигурацию
try:
    from config import OLLAMA_BASE_URL, OLLAMA_MODEL
    print(f"✅ Конфигурация загружена")
    print(f"   URL: {OLLAMA_BASE_URL}")
    print(f"   Model: {OLLAMA_MODEL}")
except Exception as e:
    print(f"❌ Ошибка загрузки конфигурации: {e}")
    sys.exit(1)

# Тест подключения
print("\n" + "=" * 60)
print("Тест подключения к Ollama")
print("=" * 60)

try:
    test_url = f"{OLLAMA_BASE_URL}/api/tags"
    print(f"Проверяю {test_url}...")
    response = requests.get(test_url, timeout=5)
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        model_names = [m.get('name', '') for m in models]
        
        print(f"✅ Подключение успешно!")
        print(f"   Найдено моделей: {len(models)}")
        
        if OLLAMA_MODEL in model_names:
            print(f"✅ Модель {OLLAMA_MODEL} найдена!")
        else:
            print(f"⚠️  Модель {OLLAMA_MODEL} не найдена")
            print(f"   Доступные модели (первые 5):")
            for name in model_names[:5]:
                print(f"     - {name}")
    else:
        print(f"❌ HTTP {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print(f"❌ Не удалось подключиться к {OLLAMA_BASE_URL}")
    print("   Убедитесь, что Ollama сервер запущен")
except Exception as e:
    print(f"❌ Ошибка: {e}")
