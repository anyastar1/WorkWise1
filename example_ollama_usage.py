"""
Пример использования модуля ollama_client.py
"""

import os
from dotenv import load_dotenv
from ollama_client import OllamaClient

# Загружаем переменные окружения из .env файла
load_dotenv()


def example_basic_text():
    """Пример 1: Простой текстовый запрос без изображений"""
    print("\n" + "=" * 80)
    print("Пример 1: Текстовый запрос")
    print("=" * 80)
    
    # Создание клиента (base_url будет взят из переменной окружения OLLAMA_BASE_URL)
    client = OllamaClient(
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Простой запрос
    response = client.generate_simple(
        prompt="Привет! Расскажи о себе.",
        system_prompt="Ты полезный ассистент, который отвечает на русском языке."
    )
    
    print(f"\nОтвет модели:\n{response}\n")


def example_with_image():
    """Пример 2: Запрос с изображением"""
    print("\n" + "=" * 80)
    print("Пример 2: Запрос с изображением")
    print("=" * 80)
    
    client = OllamaClient(
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Запрос с изображением
    # Замените путь на реальный путь к изображению
    image_path = "templates/image.png"  # Пример пути
    
    try:
        response = client.generate_simple(
            prompt="Опиши что изображено на этой картинке. Будь подробным.",
            image_paths=[image_path],
            system_prompt="Ты помощник для анализа изображений. Описывай изображения подробно на русском языке."
        )
        
        print(f"\nОтвет модели:\n{response}\n")
    except FileNotFoundError:
        print(f"Изображение не найдено: {image_path}")
        print("Укажите правильный путь к изображению")


def example_multiple_images():
    """Пример 3: Запрос с несколькими изображениями"""
    print("\n" + "=" * 80)
    print("Пример 3: Запрос с несколькими изображениями")
    print("=" * 80)
    
    client = OllamaClient(
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Запрос с несколькими изображениями
    image_paths = [
        "templates/image.png",  # Замените на реальные пути
        # "path/to/image2.jpg",
    ]
    
    try:
        response = client.generate_simple(
            prompt="Сравни эти изображения и найди различия.",
            image_paths=image_paths,
            system_prompt="Ты помощник для сравнения изображений."
        )
        
        print(f"\nОтвет модели:\n{response}\n")
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        print("Укажите правильные пути к изображениям")


def example_full_response():
    """Пример 4: Получение полного ответа с метаданными"""
    print("\n" + "=" * 80)
    print("Пример 4: Полный ответ с метаданными")
    print("=" * 80)
    
    client = OllamaClient(
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Полный запрос с дополнительными параметрами
    result = client.generate(
        user_prompt="Что такое искусственный интеллект?",
        system_prompt="Ты эксперт по искусственному интеллекту.",
        temperature=0.7,  # Дополнительный параметр
        top_p=0.9  # Дополнительный параметр
    )
    
    print(f"\nПолный ответ:\n{result}\n")
    print(f"Текст ответа: {client.generate_simple('Что такое искусственный интеллект?')}")


if __name__ == "__main__":
    print("Примеры использования OllamaClient")
    print("=" * 80)
    
    # Запуск примеров
    example_basic_text()
    
    # Раскомментируйте для тестирования с изображениями
    # example_with_image()
    # example_multiple_images()
    # example_full_response()
    
    print("\nВсе примеры завершены. Проверьте файл ollama_logs.log для просмотра логов.")
