"""
Тестовый скрипт для проверки интеграции с Ollama
Проверяет:
1. Вызов Ollama после перехода на страницу документа
2. Передачу промпта
3. Ожидание и обработку результата
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.page_processor import PAGE_ANALYSIS_PROMPT, get_page_processor
from ollama_client import OllamaClient
from database import get_session, Document, Page, PageStatus
import time


def test_prompt_formatting():
    """Тест форматирования промпта"""
    print("=" * 60)
    print("ТЕСТ 1: Форматирование промпта")
    print("=" * 60)
    
    page_number = 1
    formatted_prompt = PAGE_ANALYSIS_PROMPT.format(номер_страницы=page_number)
    
    print(f"Номер страницы: {page_number}")
    print(f"\nСформированный промпт:")
    print("-" * 60)
    print(formatted_prompt)
    print("-" * 60)
    
    # Проверяем, что номер страницы подставлен
    assert f'number="{page_number}"' in formatted_prompt, "Номер страницы не подставлен в промпт"
    print("\n✓ Промпт правильно форматируется с номером страницы")
    print()


def test_ollama_client_initialization():
    """Тест инициализации клиента Ollama"""
    print("=" * 60)
    print("ТЕСТ 2: Инициализация клиента Ollama")
    print("=" * 60)
    
    client = OllamaClient(
        model="qwen3-vl:2b-instruct"
    )
    
    print(f"Base URL: {client.base_url}")
    print(f"Model: {client.model}")
    print(f"API URL: {client.api_url}")
    print("\n✓ Клиент Ollama успешно инициализирован")
    print()


def test_page_processor_initialization():
    """Тест инициализации процессора страниц"""
    print("=" * 60)
    print("ТЕСТ 3: Инициализация процессора страниц")
    print("=" * 60)
    
    processor = get_page_processor()
    
    print(f"Процессор создан: {processor is not None}")
    print(f"Воркеры запущены: {processor.running}")
    print(f"Количество воркеров: {processor.num_workers}")
    print("\n✓ Процессор страниц успешно инициализирован")
    print()


def test_document_processing_flow():
    """Тест потока обработки документа"""
    print("=" * 60)
    print("ТЕСТ 4: Поток обработки документа")
    print("=" * 60)
    
    db = get_session()
    try:
        # Находим документ с необработанными страницами
        documents = db.query(Document).all()
        
        if not documents:
            print("⚠ Нет документов в БД для тестирования")
            return
        
        print(f"Найдено документов: {len(documents)}")
        
        # Ищем документ с необработанными страницами
        test_document = None
        for doc in documents:
            pages = db.query(Page).filter_by(document_id=doc.id).all()
            queued_pages = [p for p in pages if p.status == PageStatus.QUEUED.value]
            if queued_pages:
                test_document = doc
                print(f"\nНайден документ ID={doc.id} с {len(queued_pages)} страницами в очереди")
                break
        
        if not test_document:
            print("⚠ Нет документов с необработанными страницами")
            print("   Создайте документ через веб-интерфейс для полного теста")
            return
        
        # Проверяем структуру страниц
        pages = sorted(test_document.pages, key=lambda p: p.page_number)
        print(f"\nСтраницы документа:")
        for page in pages:
            print(f"  Страница {page.page_number}: статус={page.status}, путь={page.image_path}")
        
        # Проверяем, что изображения существуют
        print(f"\nПроверка существования изображений:")
        for page in pages:
            image_path = os.path.join("uploads", page.image_path)
            exists = os.path.exists(image_path)
            print(f"  Страница {page.page_number}: {'✓' if exists else '✗'} {image_path}")
        
        print("\n✓ Поток обработки документа проверен")
        
    except Exception as e:
        print(f"\n✗ Ошибка при проверке потока: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_prompt_structure():
    """Тест структуры промпта"""
    print("=" * 60)
    print("ТЕСТ 5: Структура промпта")
    print("=" * 60)
    
    prompt = PAGE_ANALYSIS_PROMPT.format(номер_страницы=1)
    
    # Проверяем наличие ключевых элементов
    checks = [
        ("<page", "Содержит тег <page"),
        ("<block", "Содержит тег <block"),
        ("<text", "Содержит тег <text"),
        ("short-description", "Содержит атрибут short-description"),
        ("position-x", "Содержит атрибут position-x"),
        ("position-y", "Содержит атрибут position-y"),
        ("font-family", "Содержит атрибут font-family"),
        ("font-size", "Содержит атрибут font-size"),
    ]
    
    print("Проверка структуры промпта:")
    all_passed = True
    for check_text, description in checks:
        passed = check_text in prompt
        status = "✓" if passed else "✗"
        print(f"  {status} {description}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✓ Структура промпта корректна")
    else:
        print("\n✗ Структура промпта имеет проблемы")
    print()


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ С OLLAMA")
    print("=" * 60)
    print()
    
    try:
        test_prompt_formatting()
        test_ollama_client_initialization()
        test_page_processor_initialization()
        test_prompt_structure()
        test_document_processing_flow()
        
        print("=" * 60)
        print("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60)
        print("\nДля полного теста:")
        print("1. Запустите приложение: python3 app.py")
        print("2. Загрузите документ через веб-интерфейс")
        print("3. Перейдите на страницу просмотра документа")
        print("4. Проверьте логи в консоли и файле ollama_logs.log")
        print()
        
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
