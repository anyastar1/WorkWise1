"""
Обработчик страниц документов через Ollama
"""

import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional
from ollama_client import OllamaClient
from utils.xml_parser import parse_page_xml, validate_xml_structure, XMLParseError
from database import Page, Block, TextElement, PageStatus, Document, GOSTReport, get_session


# Промпт для анализа страницы (строго формализованный)
PAGE_ANALYSIS_PROMPT = """Ты - система обработки документов. Проанализируй предоставленное изображение страницы документа и выдели все текстовые блоки и их метаданные.

ВЕРНИ ответ **строго** в следующем формате XML. Не добавляй пояснений, комментариев и лишнего текста.

<page number="{номер_страницы}">
  <block short-description="{краткое_описание_блока}" position-x="{X_левого_верхнего_угла}" position-y="{Y_левого_верхнего_угла}" width="{ширина_блока}" height="{высота_блока}">
    <text font-family="{название_шрифта}" font-size="{размер_шрифта}" color="{цвет_в_HEX}" position-x="{X_текста}" position-y="{Y_текста}" width="{ширина_текстовой_области}" height="{высота_текстовой_области}">
      {извлеченный_текст}
    </text>
    <!-- Может быть несколько тегов <text> внутри одного блока, если шрифты различаются -->
  </block>
  <!-- Может быть несколько тегов <block> на странице -->
</page>"""

# Промпт для проверки ГОСТ
GOST_CHECK_PROMPT = """Ты - эксперт по проверке документов на соответствие ГОСТ. Тебе будет предоставлен текст документа, извлеченный из PDF. Текст разметлен по блокам и страницам.

ПРОАНАЛИЗИРУЙ предоставленный текст и ВЕРНИ ответ в виде структурированного отчета.

ДАННЫЕ ДЛЯ АНАЛИЗА (в формате XML):
{сюда_подставляется_весь_извлеченный_XML_со_всех_страниц}

СФОРМУЛИРУЙ ответ, который включает:
1.  **Общий вердикт:** Соответствует ли документ основным требованиям ГОСТ (да/нет/частично).
2.  **Список найденных нарушений:**
    *   Для каждого нарушения укажи: **Описание**, **Ссылку на пункт ГОСТ**, **Страницу и блок**, где оно было найдено.
3.  **Рекомендации:** Конкретные предложения по исправлению каждого нарушения.

Ответ представь в читаемом формате, используя заголовки, списки и жирный шрифт для акцентирования. Не используй XML-разметку для отчета."""


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
                return
            
            # Обновляем статус на "обрабатывается"
            page.status = PageStatus.PROCESSING.value
            db.commit()
            
            # Формируем промпт с номером страницы
            user_prompt = PAGE_ANALYSIS_PROMPT.format(номер_страницы=page_number)
            
            # Отправляем запрос к Ollama
            response = self.ollama_client.generate(
                user_prompt=user_prompt,
                system_prompt="Ты - система обработки документов. Твоя задача - точно извлечь структурированные данные из изображения.",
                image_paths=[image_path],
                model="qwen3-vl:2b-instruct",
                timeout=300,
                max_retries=3
            )
            
            # Извлекаем текст ответа
            response_text = response.get('message', {}).get('content', '') if 'message' in response else response.get('response', '')
            
            # Валидируем XML
            is_valid, error_msg = validate_xml_structure(response_text)
            if not is_valid:
                raise XMLParseError(f"Невалидный XML: {error_msg}")
            
            # Парсим XML
            blocks_data = parse_page_xml(response_text, page_number)
            
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
            
            # Проверяем, все ли страницы обработаны
            self._check_all_pages_processed(page.document_id, db)
            
        except Exception as e:
            # Обновляем статус на "ошибка"
            try:
                page = db.get(Page, page_id)
                if page:
                    page.status = PageStatus.ERROR.value
                    page.processing_error = str(e)
                    db.commit()
            except:
                pass
            print(f"Ошибка обработки страницы {page_id}: {e}")
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
            document = db.get(Document, document_id)
            if not document or document.gost_check_completed:
                return
            
            # Собираем данные всех страниц
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
            
            # Агрегируем в XML
            from utils.xml_parser import aggregate_pages_xml
            aggregated_xml = aggregate_pages_xml(pages_data)
            
            # Формируем промпт
            user_prompt = GOST_CHECK_PROMPT.format(
                сюда_подставляется_весь_извлеченный_XML_со_всех_страниц=aggregated_xml
            )
            
            # Отправляем запрос к модели для проверки ГОСТ
            response = self.ollama_client.generate(
                user_prompt=user_prompt,
                system_prompt="Ты - эксперт по проверке документов на соответствие ГОСТ.",
                model="qwen2.5-coder:7b",  # Используем другую модель для проверки ГОСТ
                timeout=600,
                max_retries=3
            )
            
            # Извлекаем ответ
            report_text = response.get('message', {}).get('content', '') if 'message' in response else response.get('response', '')
            
            # Определяем вердикт из текста отчета
            verdict = "частично"
            if "соответствует" in report_text.lower() and "не" not in report_text.lower()[:50]:
                verdict = "да"
            elif "не соответствует" in report_text.lower() or "наруш" in report_text.lower()[:100]:
                verdict = "нет"
            
            # Сохраняем отчет
            gost_report = GOSTReport(
                document_id=document_id,
                verdict=verdict,
                report_text=report_text
            )
            db.add(gost_report)
            
            document.gost_check_completed = True
            db.commit()
            
        except Exception as e:
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
