"""
Модуль для работы с Ollama API
Поддерживает работу с vision-language моделями (qwen3-vl:2b-instruct)

Использование:
    from ollama_client import OllamaClient
    
    # Создание клиента
    client = OllamaClient(
        base_url="http://192.168.1.250:11434",
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Простой запрос
    response = client.generate_simple(
        prompt="Опиши изображение",
        image_paths=["path/to/image.jpg"],
        system_prompt="Ты помощник для анализа изображений."
    )
    
    # Полный запрос с метаданными
    result = client.generate(
        user_prompt="Вопрос",
        system_prompt="Системный промпт",
        image_paths=["image.jpg"],
        temperature=0.7
    )

Логирование:
    Все промпты и ответы автоматически логируются в файл (по умолчанию ollama_logs.log)
    и выводятся в консоль.
"""

import base64
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import requests
from datetime import datetime


class OllamaClient:
    """
    Клиент для работы с Ollama API.
    Поддерживает отправку изображений, системных промптов и пользовательских промптов.
    """
    
    def __init__(
        self,
        base_url: str = "http://192.168.1.250:11434",
        model: str = "qwen3-vl:2b-instruct",
        log_file: Optional[str] = "ollama_logs.log"
    ):
        """
        Инициализация клиента Ollama.
        
        Args:
            base_url: Базовый URL сервера Ollama
            model: Название модели для использования
            log_file: Путь к файлу для логирования (None для отключения логирования в файл)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_url = f"{self.base_url}/api/chat"
        
        # Настройка логирования
        self.logger = logging.getLogger('OllamaClient')
        self.logger.setLevel(logging.INFO)
        
        # Обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Обработчик для файла
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def _encode_image(self, image_path: str) -> str:
        """
        Кодирует изображение в base64.
        
        Args:
            image_path: Путь к файлу изображения
            
        Returns:
            Base64 строка изображения
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если файл не является изображением
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Изображение не найдено: {image_path}")
        
        # Проверка расширения файла
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Неподдерживаемый формат изображения: {path.suffix}")
        
        with open(path, 'rb') as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
        
        return base64_image
    
    def _prepare_images(self, image_paths: List[str]) -> List[str]:
        """
        Подготавливает список изображений в формате base64 для отправки в Ollama.
        
        Args:
            image_paths: Список путей к изображениям
            
        Returns:
            Список base64 строк изображений
        """
        images = []
        for img_path in image_paths:
            try:
                base64_image = self._encode_image(img_path)
                images.append(base64_image)
                self.logger.info(f"Изображение загружено: {img_path}")
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке изображения {img_path}: {e}")
                raise
        
        return images
    
    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерирует ответ от модели Ollama.
        
        Args:
            user_prompt: Промпт от пользователя
            system_prompt: Системный промпт (опционально)
            image_paths: Список путей к изображениям (опционально)
            stream: Использовать ли потоковый режим (по умолчанию False)
            **kwargs: Дополнительные параметры для API
            
        Returns:
            Словарь с ответом от модели
            
        Raises:
            requests.RequestException: При ошибке HTTP запроса
        """
        # Логирование входящих данных
        self.logger.info("=" * 80)
        self.logger.info(f"Запрос к модели: {self.model}")
        self.logger.info(f"Время запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if system_prompt:
            self.logger.info(f"Системный промпт: {system_prompt}")
        self.logger.info(f"Пользовательский промпт: {user_prompt}")
        
        if image_paths:
            self.logger.info(f"Количество изображений: {len(image_paths)}")
            for idx, img_path in enumerate(image_paths, 1):
                self.logger.info(f"  Изображение {idx}: {img_path}")
        
        # Подготовка сообщений для Ollama API
        messages = []
        
        # Системный промпт
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Подготовка изображений в формате base64
        images_base64 = []
        if image_paths:
            images_base64 = self._prepare_images(image_paths)
        
        # Пользовательское сообщение
        user_message = {
            "role": "user",
            "content": user_prompt
        }
        
        # Добавляем изображения, если они есть
        if images_base64:
            user_message["images"] = images_base64
        
        messages.append(user_message)
        
        # Подготовка данных запроса для Ollama API
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        try:
            # Отправка запроса
            self.logger.info(f"Отправка запроса на {self.api_url}")
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=300,  # 5 минут таймаут
                stream=stream
            )
            response.raise_for_status()
            
            if stream:
                # Обработка потокового ответа
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            content = chunk['message']['content']
                            full_response += content
                            if chunk.get('done', False):
                                break
                
                result = {
                    "model": self.model,
                    "response": full_response,
                    "done": True
                }
            else:
                # Обработка обычного ответа
                result = response.json()
            
            # Логирование ответа
            if 'message' in result and 'content' in result['message']:
                response_text = result['message']['content']
            elif 'response' in result:
                response_text = result['response']
            else:
                response_text = str(result)
            
            self.logger.info("=" * 80)
            self.logger.info("Ответ от модели:")
            self.logger.info(response_text)
            self.logger.info("=" * 80)
            
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при запросе к Ollama: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Статус код: {e.response.status_code}")
                self.logger.error(f"Ответ сервера: {e.response.text}")
            raise
    
    def generate_simple(
        self,
        prompt: str,
        image_paths: Optional[List[str]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Упрощенный метод для получения только текстового ответа.
        
        Args:
            prompt: Промпт от пользователя
            image_paths: Список путей к изображениям (опционально)
            system_prompt: Системный промпт (опционально)
            
        Returns:
            Текст ответа от модели
        """
        result = self.generate(
            user_prompt=prompt,
            system_prompt=system_prompt,
            image_paths=image_paths
        )
        
        # Извлечение текста ответа
        if 'message' in result:
            if isinstance(result['message'], dict) and 'content' in result['message']:
                return result['message']['content']
            elif isinstance(result['message'], str):
                return result['message']
        elif 'response' in result:
            return result['response']
        else:
            return str(result)


# Пример использования
if __name__ == "__main__":
    # Создание клиента
    client = OllamaClient(
        base_url="http://192.168.1.250:11434",
        model="qwen3-vl:2b-instruct",
        log_file="ollama_logs.log"
    )
    
    # Пример 1: Текстовый запрос без изображений
    print("\n=== Пример 1: Текстовый запрос ===")
    response = client.generate_simple(
        prompt="Привет! Как дела?",
        system_prompt="Ты полезный ассистент."
    )
    print(f"Ответ: {response}")
    
    # Пример 2: Запрос с изображением
    print("\n=== Пример 2: Запрос с изображением ===")
    # Раскомментируйте, если есть тестовое изображение
    # response = client.generate_simple(
    #     prompt="Опиши что изображено на этой картинке",
    #     image_paths=["path/to/image.jpg"],
    #     system_prompt="Ты помощник для анализа изображений."
    # )
    # print(f"Ответ: {response}")
