"""
Парсер и валидатор XML-ответов от Ollama
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime
import html


class XMLParseError(Exception):
    """Ошибка парсинга XML"""
    pass


def extract_xml_from_text(text: str) -> str:
    """
    Извлекает XML из текста, удаляя лишние символы и комментарии вне XML
    
    Поддерживает:
    - XML в markdown блоках кода (```xml ... ```)
    - XML с пояснениями до/после
    - CDATA секции для программного кода
    
    Args:
        text: Текст ответа от модели
        
    Returns:
        Очищенный XML
    """
    # Удаляем markdown разметку, если есть
    # Ищем XML в markdown блоках кода
    markdown_xml_match = re.search(r'```(?:xml)?\s*(<page[^>]*>.*?</page>)', text, re.DOTALL | re.IGNORECASE)
    if markdown_xml_match:
        return markdown_xml_match.group(1)
    
    # Ищем XML между тегами <page> и </page>
    xml_match = re.search(r'<page[^>]*>.*?</page>', text, re.DOTALL)
    if xml_match:
        return xml_match.group(0)
    
    # Если не нашли полный XML, пробуем найти начало и конец отдельно
    # (модель могла добавить пояснения внутри)
    page_start = re.search(r'<page[^>]*>', text, re.IGNORECASE)
    page_end = re.search(r'</page>', text, re.IGNORECASE)
    
    if page_start and page_end:
        # Берем текст от начала до конца, но ищем закрывающие теги правильно
        start_pos = page_start.start()
        # Ищем последний </page>
        end_pos = page_end.end()
        
        # Проверяем, что между ними есть правильная структура
        potential_xml = text[start_pos:end_pos]
        
        # Подсчитываем открывающие и закрывающие теги page
        open_count = potential_xml.count('<page')
        close_count = potential_xml.count('</page>')
        
        if open_count == close_count:
            return potential_xml
    
    # Если ничего не найдено, возвращаем весь текст
    return text


def _escape_code_in_xml(xml_string: str) -> str:
    """
    Экранирует специальные символы в тексте внутри тегов <text>,
    которые могут содержать программный код (Python, Java и т.д.)
    
    Обрабатывает:
    - Символы <, >, & в коде Python/Java
    - CDATA секции (оставляет как есть)
    - Вложенные теги в тексте
    
    Args:
        xml_string: XML строка
        
    Returns:
        XML с экранированным кодом
    """
    # Паттерн для поиска содержимого тегов <text>
    # Ищем <text ...>содержимое</text> с учетом возможных вложенных тегов
    pattern = r'(<text[^>]*>)(.*?)(</text>)'
    
    def replace_text(match):
        start_tag = match.group(1)
        content = match.group(2)
        end_tag = match.group(3)
        
        # Если уже есть CDATA, не трогаем
        if '<![CDATA[' in content and ']]>' in content:
            return match.group(0)
        
        # Проверяем, не содержит ли текст незакрытые теги (это может быть код)
        # Если есть символы < или >, но нет парных тегов, это скорее всего код
        open_brackets = content.count('<')
        close_brackets = content.count('>')
        
        # Если количество открывающих и закрывающих скобок не совпадает,
        # или есть < без соответствующего >, это может быть код
        if open_brackets != close_brackets or (open_brackets > 0 and not re.search(r'<[^>]+>', content)):
            # Экранируем все специальные XML символы
            escaped_content = html.escape(content)
            return start_tag + escaped_content + end_tag
        
        # Если есть валидные XML теги внутри, проверяем их структуру
        # Если структура валидна, оставляем как есть
        # Иначе экранируем
        try:
            # Пробуем распарсить содержимое как XML фрагмент
            test_xml = f"<root>{content}</root>"
            ET.fromstring(test_xml)
            # Если успешно, значит это валидный XML, не трогаем
            return match.group(0)
        except:
            # Если не валидный XML, экранируем
            escaped_content = html.escape(content)
            return start_tag + escaped_content + end_tag
    
    # Заменяем содержимое всех тегов <text>
    xml_string = re.sub(pattern, replace_text, xml_string, flags=re.DOTALL)
    
    return xml_string


def parse_page_xml(xml_string: str, page_number: int) -> List[Dict]:
    """
    Парсит XML ответ от Ollama и возвращает структурированные данные
    
    Поддерживает обработку программного кода внутри тегов <text>
    (Python, Java и другие языки с символами <, >, &)
    
    Args:
        xml_string: XML строка от модели
        page_number: Номер страницы
        
    Returns:
        Список словарей с данными блоков:
        [{
            'short_description': str,
            'position_x': float,
            'position_y': float,
            'width': float,
            'height': float,
            'text_elements': [{
                'text': str,
                'font_family': str,
                'font_size': float,
                'color': str,
                'position_x': float,
                'position_y': float,
                'width': float,
                'height': float
            }]
        }]
        
    Raises:
        XMLParseError: При ошибке парсинга
    """
    try:
        # Извлекаем XML из текста
        xml_string = extract_xml_from_text(xml_string)
        
        # Экранируем специальные символы в тексте (для программного кода)
        xml_string = _escape_code_in_xml(xml_string)
        
        # Парсим XML
        root = ET.fromstring(xml_string)
        
        # Проверяем, что корневой элемент - <page>
        if root.tag != 'page':
            raise XMLParseError(f"Ожидался тег <page>, получен <{root.tag}>")
        
        # Проверяем номер страницы
        page_num_attr = root.get('number')
        if page_num_attr and int(page_num_attr) != page_number:
            raise XMLParseError(f"Несоответствие номера страницы: ожидался {page_number}, получен {page_num_attr}")
        
        blocks = []
        
        # Обрабатываем все блоки
        for block_elem in root.findall('block'):
            block_data = {
                'short_description': block_elem.get('short-description', ''),
                'position_x': float(block_elem.get('position-x', 0)),
                'position_y': float(block_elem.get('position-y', 0)),
                'width': float(block_elem.get('width', 0)),
                'height': float(block_elem.get('height', 0)),
                'text_elements': []
            }
            
            # Обрабатываем текстовые элементы
            for text_elem in block_elem.findall('text'):
                # Получаем весь текст элемента, включая дочерние узлы
                # ElementTree автоматически обрабатывает экранированные символы
                text_parts = []
                
                # Добавляем основной текст
                if text_elem.text:
                    text_parts.append(text_elem.text)
                
                # Добавляем текст из дочерних элементов (если есть)
                for child in text_elem:
                    if child.text:
                        text_parts.append(child.text)
                    # Добавляем tail (текст после дочернего элемента)
                    if child.tail:
                        text_parts.append(child.tail)
                
                # Объединяем все части
                text_content = ''.join(text_parts)
                
                # Декодируем HTML entities обратно в обычный текст
                # Это вернет исходные символы <, >, & из программного кода
                text_content = html.unescape(text_content).strip()
                
                text_data = {
                    'text': text_content,
                    'font_family': text_elem.get('font-family', ''),
                    'font_size': _parse_float(text_elem.get('font-size')),
                    'color': text_elem.get('color', ''),
                    'position_x': float(text_elem.get('position-x', 0)),
                    'position_y': float(text_elem.get('position-y', 0)),
                    'width': float(text_elem.get('width', 0)),
                    'height': float(text_elem.get('height', 0))
                }
                block_data['text_elements'].append(text_data)
            
            blocks.append(block_data)
        
        return blocks
    
    except ET.ParseError as e:
        raise XMLParseError(f"Ошибка парсинга XML: {str(e)}")
    except ValueError as e:
        raise XMLParseError(f"Ошибка преобразования значений: {str(e)}")
    except Exception as e:
        raise XMLParseError(f"Неожиданная ошибка при парсинге XML: {str(e)}")


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Безопасное преобразование строки в float"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except ValueError:
        return None


def validate_xml_structure(xml_string: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует структуру XML
    
    Args:
        xml_string: XML строка для валидации
        
    Returns:
        (is_valid, error_message)
    """
    try:
        xml_string = extract_xml_from_text(xml_string)
        root = ET.fromstring(xml_string)
        
        # Проверяем обязательные элементы
        if root.tag != 'page':
            return False, f"Корневой элемент должен быть <page>, получен <{root.tag}>"
        
        # Проверяем наличие блоков
        blocks = root.findall('block')
        if not blocks:
            return False, "Не найдено ни одного блока <block>"
        
        # Проверяем структуру блоков
        for block in blocks:
            required_attrs = ['short-description', 'position-x', 'position-y', 'width', 'height']
            for attr in required_attrs:
                if attr not in block.attrib:
                    return False, f"Блок не содержит обязательный атрибут: {attr}"
            
            # Проверяем наличие текстовых элементов
            texts = block.findall('text')
            if not texts:
                return False, "Блок должен содержать хотя бы один элемент <text>"
        
        return True, None
    
    except ET.ParseError as e:
        return False, f"Ошибка парсинга XML: {str(e)}"
    except Exception as e:
        return False, f"Ошибка валидации: {str(e)}"


def aggregate_pages_xml(pages_data: List[Dict]) -> str:
    """
    Агрегирует данные всех страниц в единый XML для проверки ГОСТ
    
    Args:
        pages_data: Список данных страниц (результаты parse_page_xml)
        
    Returns:
        XML строка со всеми страницами
    """
    root = ET.Element('document')
    
    for page_num, blocks in enumerate(pages_data, start=1):
        page_elem = ET.SubElement(root, 'page', number=str(page_num))
        
        for block_data in blocks:
            block_elem = ET.SubElement(
                page_elem,
                'block',
                short_description=block_data['short_description'],
                position_x=str(block_data['position_x']),
                position_y=str(block_data['position_y']),
                width=str(block_data['width']),
                height=str(block_data['height'])
            )
            
            for text_data in block_data['text_elements']:
                text_elem = ET.SubElement(
                    block_elem,
                    'text',
                    font_family=text_data.get('font_family', ''),
                    font_size=str(text_data.get('font_size', '')),
                    color=text_data.get('color', ''),
                    position_x=str(text_data['position_x']),
                    position_y=str(text_data['position_y']),
                    width=str(text_data['width']),
                    height=str(text_data['height'])
                )
                text_elem.text = text_data['text']
    
    return ET.tostring(root, encoding='unicode')
