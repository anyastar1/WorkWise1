"""
Обработчик страниц документов через Ollama
"""

import threading
import queue
import json
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from ollama_client import OllamaClient
from utils.xml_parser import parse_page_xml, validate_xml_structure, XMLParseError
from database import Page, Block, TextElement, PageStatus, Document, GOSTReport, get_session

# Настройка логирования
logger = logging.getLogger(__name__)


# Промпт для анализа страницы (строго формализованный)
# Используем двойные фигурные скобки {{ }} для экранирования в .format()
PAGE_ANALYSIS_PROMPT = """Ты - система обработки документов. Проанализируй предоставленное изображение страницы документа и выдели все текстовые блоки и их метаданные.

ВЕРНИ ответ **строго** в следующем формате XML. Не добавляй пояснений, комментариев и лишнего текста.

<page number="{номер_страницы}">
  <block short-description="{{краткое_описание_блока}}" position-x="{{X_левого_верхнего_угла}}" position-y="{{Y_левого_верхнего_угла}}" width="{{ширина_блока}}" height="{{высота_блока}}">
    <text font-family="{{название_шрифта}}" font-size="{{размер_шрифта}}" color="{{цвет_в_HEX}}" position-x="{{X_текста}}" position-y="{{Y_текста}}" width="{{ширина_текстовой_области}}" height="{{высота_текстовой_области}}">
      {{извлеченный_текст}}
    </text>
    <!-- Может быть несколько тегов <text> внутри одного блока, если шрифты различаются -->
  </block>
  <!-- Может быть несколько тегов <block> на странице -->
</page>"""

# Промпт для проверки ГОСТ
# Используем двойные фигурные скобки {{ }} для экранирования в .format()
GOST_CHECK_PROMPT = """Ты - эксперт по проверке документов на соответствие ГОСТ. Тебе будет предоставлен текст документа, извлеченный из PDF. Текст разметлен по блокам и страницам.

ПРОАНАЛИЗИРУЙ предоставленный текст и ВЕРНИ ответ **СТРОГО** в формате JSON.

ДАННЫЕ ДЛЯ АНАЛИЗА (в формате XML):
{сюда_подставляется_весь_извлеченный_XML_со_всех_страниц}

ТРЕБОВАНИЯ К ОТВЕТУ:
1. Верни ответ ТОЛЬКО в формате JSON, без дополнительных пояснений, комментариев или текста до/после JSON.
2. Формат JSON должен быть следующим:
{{
  "score": <целое число от 0 до 100, где 0 - полное несоответствие, 100 - полное соответствие>,
  "verdict": <строка с общей оценкой соответствия, например: "Документ полностью соответствует требованиям ГОСТ" или "Документ частично соответствует требованиям ГОСТ" или "Документ не соответствует требованиям ГОСТ">,
  "pages": [
    {{
      "page": <номер страницы (целое число)>,
      "gosterror": <описание нарушения ГОСТ (строка), если нарушений нет на странице - пустая строка "">,
      "howtofix": <рекомендация по исправлению (строка), если нарушений нет - пустая строка "">,
      "positionX": <координата X левого верхнего угла области ошибки (число с плавающей точкой), если ошибки нет - 0>,
      "positionY": <координата Y левого верхнего угла области ошибки (число с плавающей точкой), если ошибки нет - 0>,
      "width": <ширина области ошибки (число с плавающей точкой), если ошибки нет - 0>,
      "height": <высота области ошибки (число с плавающей точкой), если ошибки нет - 0>
    }}
  ]
}}

ВАЖНО:
- Если на странице нет нарушений, массив "pages" все равно должен содержать запись для этой страницы с пустыми строками в "gosterror" и "howtofix", и нулевыми координатами.
- Координаты (positionX, positionY, width, height) должны соответствовать координатам блоков из предоставленного XML.
- Если нарушение затрагивает несколько страниц, создай отдельную запись для каждой страницы.
- Поле "score" должно отражать общую оценку соответствия всего документа (0-100).
- Поле "verdict" должно содержать понятное текстовое описание общего вердикта.

Верни ТОЛЬКО валидный JSON, без markdown разметки, без комментариев, без дополнительного текста."""


def extract_json_from_text(text: str) -> Optional[str]:
    """Извлекает JSON из текста ответа Ollama"""
    if not text:
        return None
    
    # Пытаемся найти JSON в markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # Пытаемся найти JSON объект напрямую
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json_match.group(0)
    
    return None


def validate_gost_json(data: Dict) -> tuple[bool, Optional[str]]:
    """Валидирует структуру JSON отчета ГОСТ"""
    try:
        # Проверяем наличие обязательных полей верхнего уровня
        if 'score' not in data:
            return False, "Отсутствует поле 'score'"
        if 'verdict' not in data:
            return False, "Отсутствует поле 'verdict'"
        if 'pages' not in data:
            return False, "Отсутствует поле 'pages'"
        
        # Проверяем тип и диапазон score
        if not isinstance(data['score'], int):
            return False, "Поле 'score' должно быть целым числом"
        if data['score'] < 0 or data['score'] > 100:
            return False, "Поле 'score' должно быть в диапазоне 0-100"
        
        # Проверяем тип verdict
        if not isinstance(data['verdict'], str):
            return False, "Поле 'verdict' должно быть строкой"
        
        # Проверяем тип pages
        if not isinstance(data['pages'], list):
            return False, "Поле 'pages' должно быть массивом"
        
        # Проверяем структуру каждой страницы
        for i, page in enumerate(data['pages']):
            if not isinstance(page, dict):
                return False, f"Элемент {i} в массиве 'pages' должен быть объектом"
            
            required_fields = ['page', 'gosterror', 'howtofix', 'positionX', 'positionY', 'width', 'height']
            for field in required_fields:
                if field not in page:
                    return False, f"Отсутствует поле '{field}' в элементе {i} массива 'pages'"
            
            # Проверяем типы полей
            if not isinstance(page['page'], int):
                return False, f"Поле 'page' в элементе {i} должно быть целым числом"
            if not isinstance(page['gosterror'], str):
                return False, f"Поле 'gosterror' в элементе {i} должно быть строкой"
            if not isinstance(page['howtofix'], str):
                return False, f"Поле 'howtofix' в элементе {i} должно быть строкой"
            
            # Проверяем координаты (должны быть числами)
            coord_fields = ['positionX', 'positionY', 'width', 'height']
            for field in coord_fields:
                if not isinstance(page[field], (int, float)):
                    return False, f"Поле '{field}' в элементе {i} должно быть числом"
        
        return True, None
    
    except Exception as e:
        return False, f"Ошибка валидации: {str(e)}"


class PageProcessor:
    """Обработчик страниц документов"""
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama_client = ollama_client
        self.task_queue = queue.Queue()
        self.workers = []
        self.running = False
        self.num_workers = 2  # Количество параллельных обработчиков
    
    def start_workers(self):
        """Запускает воркеры для обработки задач"""
        if self.running:
            return
        
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def stop_workers(self):
        """Останавливает воркеры"""
        self.running = False
        # Добавляем стоп-сигналы в очередь
        for _ in range(self.num_workers):
            self.task_queue.put(None)
    
    def add_page_task(self, page_id: int, image_path: str, page_number: int):
        """Добавляет задачу на обработку страницы в очередь"""
        self.task_queue.put({
            'type': 'page',
            'page_id': page_id,
            'image_path': image_path,
            'page_number': page_number
        })
    
    def _worker(self):
        """Воркер для обработки задач из очереди"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:  # Стоп-сигнал
                    break
                
                if task['type'] == 'page':
                    self._process_page(task['page_id'], task['image_path'], task['page_number'])
                
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Ошибка в воркере: {e}")
    
    def _process_page(self, page_id: int, image_path: str, page_number: int):
        """Обрабатывает одну страницу"""
        db = get_session()
        try:
            page = db.get(Page, page_id)
            if not page:
                print(f"[ERROR] Страница {page_id} не найдена в БД")
                return
            
            # Обновляем статус на "обрабатывается"
            page.status = PageStatus.PROCESSING.value
            db.commit()
            print(f"[INFO] Начало обработки страницы {page_number} (ID: {page_id})")
            
            # Формируем промпт с номером страницы
            user_prompt = PAGE_ANALYSIS_PROMPT.format(номер_страницы=page_number)
            print(f"[DEBUG] Промпт для страницы {page_number}:")
            print(f"[DEBUG] {user_prompt[:200]}...")
            print(f"[DEBUG] Путь к изображению: {image_path}")
            
            # Отправляем запрос к Ollama
            print(f"[INFO] Отправка запроса к Ollama для страницы {page_number}...")
            response = self.ollama_client.generate(
                user_prompt=user_prompt,
                system_prompt="Ты - система обработки документов. Твоя задача - точно извлечь структурированные данные из изображения.",
                image_paths=[image_path],
                model="qwen3-vl:2b-instruct",
                timeout=300,
                max_retries=3
            )
            
            print(f"[INFO] Получен ответ от Ollama для страницы {page_number}")
            
            # Извлекаем текст ответа
            # Ollama API возвращает ответ в формате: {"message": {"content": "...", "role": "assistant"}, ...}
            response_text = ""
            if 'message' in response and isinstance(response['message'], dict):
                response_text = response['message'].get('content', '')
            elif 'response' in response:
                response_text = response['response']
            elif isinstance(response, str):
                response_text = response
            
            if not response_text:
                print(f"[WARNING] Пустой ответ от Ollama для страницы {page_number}")
                print(f"[DEBUG] Полный ответ (тип: {type(response)}): {response}")
                print(f"[DEBUG] Ключи в ответе: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
                raise ValueError("Пустой ответ от Ollama")
            
            print(f"[DEBUG] Длина ответа: {len(response_text)} символов")
            print(f"[DEBUG] Первые 500 символов ответа: {response_text[:500]}")
            
            # Пытаемся распарсить XML с повторными попытками
            max_parse_attempts = 3
            blocks_data = None
            last_error = None
            
            for parse_attempt in range(1, max_parse_attempts + 1):
                try:
                    print(f"[INFO] Попытка парсинга XML {parse_attempt}/{max_parse_attempts} для страницы {page_number}...")
                    
                    # Валидируем XML
                    is_valid, error_msg = validate_xml_structure(response_text)
                    if not is_valid:
                        print(f"[WARNING] Невалидный XML (попытка {parse_attempt}): {error_msg}")
                        if parse_attempt < max_parse_attempts:
                            # Пробуем улучшить XML перед следующей попыткой
                            print(f"[INFO] Попытка улучшить XML...")
                            # Можем попробовать запросить у модели исправление
                            continue
                        else:
                            raise XMLParseError(f"Невалидный XML после {max_parse_attempts} попыток: {error_msg}")
                    
                    print(f"[INFO] XML валиден, начинаем парсинг...")
                    # Парсим XML
                    blocks_data = parse_page_xml(response_text, page_number)
                    print(f"[INFO] Распарсено блоков: {len(blocks_data)}")
                    break  # Успешно распарсили
                    
                except XMLParseError as e:
                    last_error = e
                    print(f"[WARNING] Ошибка парсинга XML (попытка {parse_attempt}/{max_parse_attempts}): {str(e)}")
                    
                    if parse_attempt < max_parse_attempts:
                        # Пробуем запросить у модели исправленный ответ
                        print(f"[INFO] Запрашиваем исправленный ответ от модели...")
                        try:
                            # Формируем промпт с просьбой исправить XML
                            correction_prompt = f"""Предыдущий ответ содержал ошибки в XML формате. Исправь XML и верни только валидный XML без пояснений.

Ошибка: {str(e)}

Исправленный XML:"""
                            
                            correction_response = self.ollama_client.generate(
                                user_prompt=correction_prompt + "\n\n" + response_text[:2000],  # Первые 2000 символов для контекста
                                system_prompt="Ты - система обработки XML. Исправь ошибки в XML и верни только валидный XML.",
                                image_paths=[image_path],
                                model="qwen3-vl:2b-instruct",
                                timeout=300,
                                max_retries=2
                            )
                            
                            # Извлекаем исправленный ответ
                            correction_text = ""
                            if 'message' in correction_response and isinstance(correction_response['message'], dict):
                                correction_text = correction_response['message'].get('content', '')
                            elif 'response' in correction_response:
                                correction_text = correction_response['response']
                            
                            if correction_text:
                                print(f"[INFO] Получен исправленный ответ, длина: {len(correction_text)}")
                                response_text = correction_text
                                continue  # Пробуем снова с исправленным ответом
                            else:
                                print(f"[WARNING] Не удалось получить исправленный ответ")
                                
                        except Exception as correction_error:
                            print(f"[WARNING] Ошибка при запросе исправления: {correction_error}")
                    
                    # Если это последняя попытка, выбрасываем ошибку
                    if parse_attempt == max_parse_attempts:
                        raise
            
            if blocks_data is None:
                raise XMLParseError(f"Не удалось распарсить XML после {max_parse_attempts} попыток: {last_error}")
            
            # Сохраняем данные в БД
            for block_data in blocks_data:
                block = Block(
                    page_id=page_id,
                    short_description=block_data['short_description'],
                    position_x=block_data['position_x'],
                    position_y=block_data['position_y'],
                    width=block_data['width'],
                    height=block_data['height']
                )
                db.add(block)
                db.flush()
                
                # Сохраняем текстовые элементы
                for text_data in block_data['text_elements']:
                    text_elem = TextElement(
                        block_id=block.id,
                        text=text_data['text'],
                        font_family=text_data.get('font_family'),
                        font_size=text_data.get('font_size'),
                        color=text_data.get('color'),
                        position_x=text_data['position_x'],
                        position_y=text_data['position_y'],
                        width=text_data['width'],
                        height=text_data['height']
                    )
                    db.add(text_elem)
            
            # Обновляем статус страницы
            page.status = PageStatus.COMPLETED.value
            page.processed_at = datetime.utcnow()
            db.commit()
            print(f"[SUCCESS] Страница {page_number} успешно обработана")
            
            # Проверяем, все ли страницы обработаны
            self._check_all_pages_processed(page.document_id, db)
            
        except Exception as e:
            # Обновляем статус на "ошибка"
            error_msg = str(e)
            print(f"[ERROR] Ошибка обработки страницы {page_id} (страница {page_number}): {error_msg}")
            import traceback
            print(f"[ERROR] Трассировка: {traceback.format_exc()}")
            try:
                page = db.get(Page, page_id)
                if page:
                    page.status = PageStatus.ERROR.value
                    page.processing_error = error_msg
                    db.commit()
            except Exception as db_error:
                print(f"[ERROR] Ошибка при сохранении статуса ошибки: {db_error}")
        finally:
            db.close()
    
    def _check_all_pages_processed(self, document_id: int, db):
        """Проверяет, все ли страницы обработаны, и запускает проверку ГОСТ"""
        document = db.get(Document, document_id)
        if not document:
            return
        
        # Проверяем статусы всех страниц
        pages = db.query(Page).filter_by(document_id=document_id).all()
        all_completed = all(p.status == PageStatus.COMPLETED.value for p in pages)
        has_errors = any(p.status == PageStatus.ERROR.value for p in pages)
        
        if all_completed and not document.all_pages_processed:
            document.all_pages_processed = True
            db.commit()
            
            # Запускаем проверку ГОСТ в фоне
            threading.Thread(
                target=self._check_gost_compliance,
                args=(document_id,),
                daemon=True
            ).start()
    
    def _check_gost_compliance(self, document_id: int):
        """Проверяет документ на соответствие ГОСТ"""
        db = get_session()
        try:
            logger.info(f"[GOST] Начало проверки ГОСТ для документа {document_id}")
            
            document = db.get(Document, document_id)
            if not document or document.gost_check_completed:
                logger.warning(f"[GOST] Документ {document_id} не найден или проверка уже завершена")
                return
            
            # Собираем данные всех страниц
            logger.info(f"[GOST] Сбор данных страниц для документа {document_id}")
            pages = sorted(document.pages, key=lambda p: p.page_number)
            pages_data = []
            
            for page in pages:
                blocks_data = []
                for block in page.blocks:
                    text_elements_data = []
                    for text_elem in block.text_elements:
                        text_elements_data.append({
                            'text': text_elem.text,
                            'font_family': text_elem.font_family,
                            'font_size': text_elem.font_size,
                            'color': text_elem.color,
                            'position_x': text_elem.position_x,
                            'position_y': text_elem.position_y,
                            'width': text_elem.width,
                            'height': text_elem.height
                        })
                    
                    blocks_data.append({
                        'short_description': block.short_description,
                        'position_x': block.position_x,
                        'position_y': block.position_y,
                        'width': block.width,
                        'height': block.height,
                        'text_elements': text_elements_data
                    })
                
                pages_data.append(blocks_data)
            
            logger.info(f"[GOST] Собрано данных для {len(pages_data)} страниц")
            
            # Агрегируем в XML
            from utils.xml_parser import aggregate_pages_xml
            aggregated_xml = aggregate_pages_xml(pages_data)
            logger.info(f"[GOST] XML агрегирован, длина: {len(aggregated_xml)} символов")
            
            # Формируем промпт
            user_prompt = GOST_CHECK_PROMPT.format(
                сюда_подставляется_весь_извлеченный_XML_со_всех_страниц=aggregated_xml
            )
            
            # Попытки получения валидного JSON (до 3 попыток)
            max_attempts = 3
            gost_data = None
            report_text = None
            
            for attempt in range(1, max_attempts + 1):
                logger.info(f"[GOST] Попытка {attempt}/{max_attempts} получения ответа от Ollama")
                
                # Отправляем запрос к модели для проверки ГОСТ
                response = self.ollama_client.generate(
                    user_prompt=user_prompt,
                    system_prompt="Ты - эксперт по проверке документов на соответствие ГОСТ. ВАЖНО: Верни ответ ТОЛЬКО в формате JSON, без дополнительного текста.",
                    model="qwen2.5-coder:7b",  # Используем другую модель для проверки ГОСТ
                    timeout=600,
                    max_retries=3
                )
                
                # Извлекаем ответ
                raw_response = response.get('message', {}).get('content', '') if 'message' in response else response.get('response', '')
                logger.info(f"[GOST] Получен ответ от Ollama, длина: {len(raw_response)} символов")
                
                # Извлекаем JSON из ответа
                json_str = extract_json_from_text(raw_response)
                
                if not json_str:
                    logger.warning(f"[GOST] Попытка {attempt}: JSON не найден в ответе")
                    if attempt < max_attempts:
                        logger.info(f"[GOST] Повторная попытка...")
                        continue
                    else:
                        logger.error(f"[GOST] Не удалось извлечь JSON после {max_attempts} попыток")
                        # Сохраняем исходный ответ как текст для отладки
                        report_text = raw_response
                        break
                
                # Парсим JSON
                try:
                    gost_data = json.loads(json_str)
                    logger.info(f"[GOST] JSON успешно распарсен")
                except json.JSONDecodeError as e:
                    logger.warning(f"[GOST] Попытка {attempt}: Ошибка парсинга JSON: {e}")
                    if attempt < max_attempts:
                        logger.info(f"[GOST] Повторная попытка...")
                        continue
                    else:
                        logger.error(f"[GOST] Не удалось распарсить JSON после {max_attempts} попыток")
                        report_text = raw_response
                        break
                
                # Валидируем структуру JSON
                is_valid, error_msg = validate_gost_json(gost_data)
                if not is_valid:
                    logger.warning(f"[GOST] Попытка {attempt}: JSON не прошел валидацию: {error_msg}")
                    if attempt < max_attempts:
                        logger.info(f"[GOST] Повторная попытка...")
                        continue
                    else:
                        logger.error(f"[GOST] JSON не прошел валидацию после {max_attempts} попыток: {error_msg}")
                        # Сохраняем JSON как есть, но с предупреждением
                        report_text = json.dumps(gost_data, ensure_ascii=False, indent=2)
                        break
                
                # JSON валиден
                logger.info(f"[GOST] JSON успешно валидирован на попытке {attempt}")
                break
            
            # Определяем вердикт и score
            if gost_data:
                score = gost_data.get('score', 50)
                verdict_text = gost_data.get('verdict', '')
                
                # Определяем вердикт на основе score
                if score >= 80:
                    verdict = "да"
                elif score >= 40:
                    verdict = "частично"
                else:
                    verdict = "нет"
                
                # Сохраняем JSON в report_text
                report_text = json.dumps(gost_data, ensure_ascii=False, indent=2)
                logger.info(f"[GOST] Вердикт: {verdict}, Score: {score}")
            else:
                # Если не удалось получить валидный JSON, используем старую логику
                verdict = "частично"
                if report_text:
                    if "соответствует" in report_text.lower() and "не" not in report_text.lower()[:50]:
                        verdict = "да"
                    elif "не соответствует" in report_text.lower() or "наруш" in report_text.lower()[:100]:
                        verdict = "нет"
                logger.warning(f"[GOST] Использован fallback вердикт: {verdict}")
            
            # Сохраняем отчет
            gost_report = GOSTReport(
                document_id=document_id,
                verdict=verdict,
                report_text=report_text or "{}"
            )
            db.add(gost_report)
            
            document.gost_check_completed = True
            db.commit()
            
            logger.info(f"[GOST] Отчет сохранен для документа {document_id}")
            
        except Exception as e:
            logger.error(f"[GOST] Ошибка проверки ГОСТ для документа {document_id}: {e}")
            import traceback
            logger.error(f"[GOST] Трассировка: {traceback.format_exc()}")
            print(f"Ошибка проверки ГОСТ для документа {document_id}: {e}")
        finally:
            db.close()


# Глобальный экземпляр процессора
_processor_instance = None


def get_page_processor() -> PageProcessor:
    """Получает глобальный экземпляр процессора страниц"""
    global _processor_instance
    if _processor_instance is None:
        ollama_client = OllamaClient(
            base_url="http://192.168.1.250:11434",
            model="qwen3-vl:2b-instruct"
        )
        _processor_instance = PageProcessor(ollama_client)
        _processor_instance.start_workers()
    return _processor_instance
