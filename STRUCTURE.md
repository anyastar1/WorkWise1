# Структура проекта WorkWise

Проект разбит на модули для лучшей организации кода.

## Структура директорий

```
WorkWise/
├── app.py                 # Главный файл приложения (использует импорты из модулей)
├── config.py             # Конфигурация приложения
├── database.py           # Модели базы данных
├── document_processor.py # Обработка документов
│
├── api/                  # API клиенты
│   ├── __init__.py
│   └── ollama_client.py  # Клиент для работы с Ollama API
│
├── services/             # Бизнес-логика
│   ├── __init__.py
│   └── document_analyzer.py  # Анализ документов
│
├── utils/                # Вспомогательные функции
│   ├── __init__.py
│   └── helpers.py        # Утилиты (конвертация файлов, чтение и т.д.)
│
└── routes/               # Маршруты Flask (можно разбить дальше)
    └── __init__.py
```

## Модули

### config.py
Содержит все конфигурационные константы:
- `OLLAMA_BASE_URL` - адрес Ollama сервера
- `OLLAMA_MODEL` - модель для использования
- `UPLOAD_FOLDER` - папка для загрузок
- `ALLOWED_EXTENSIONS` - разрешённые расширения файлов
- `MAX_CONTENT_LENGTH` - максимальный размер файла

### api/ollama_client.py
Функции для работы с Ollama API:
- `check_ollama_available()` - проверка доступности сервера
- `is_api_configured()` - статус настройки API
- `call_ollama_api()` - запрос к API без изображений
- `call_ollama_api_with_images()` - запрос к API с изображениями

### services/document_analyzer.py
Функции анализа документов:
- `analyze_document()` - главная функция анализа
- `analyze_document_with_images()` - анализ через изображения
- `analyze_structure_from_images()` - анализ структуры по ГОСТ 7.32-2001
- `analyze_bibliography_from_images()` - анализ библиографии по ГОСТ Р 7.0.5-2008
- `analyze_document_with_gost()` - текстовый анализ библиографии
- `analyze_document_structure_gost_732()` - текстовый анализ структуры

### utils/helpers.py
Вспомогательные функции:
- `clean_json_response()` - очистка JSON ответов
- `allowed_file()` - проверка расширения файла
- `check_command_available()` - проверка доступности команды в системе
- `convert_docx_to_pdf()` - конвертация DOCX в PDF
- `read_file_content()` - чтение содержимого файлов

## Использование

Все функции импортируются в `app.py`:

```python
from config import UPLOAD_FOLDER, OLLAMA_BASE_URL
from api.ollama_client import call_ollama_api
from services.document_analyzer import analyze_document
from utils.helpers import convert_docx_to_pdf
```

## Дальнейшее развитие

Можно дополнительно разбить:
- `routes/` на `auth.py`, `main.py`, `upload.py` для маршрутов
- Вынести промпты в отдельный файл `prompts.py`
- Создать `models/` для бизнес-моделей
