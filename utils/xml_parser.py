"""
Парсер и валидатор XML-ответов от Ollama
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime


class XMLParseError(Exception):
    """Ошибка парсинга XML"""
    pass


def extract_xml_from_text(text: str) -> str:
    """
    Извлекает XML из текста, удаляя лишние символы и комментарии вне XML
    
    Args:
        text: Текст ответа от модели
        
    Returns:
        Очищенный XML
    """
    # Ищем XML между тегами <page> и </page>
    xml_match = re.search(r'<page[^>]*>.*?</page>', text, re.DOTALL)
    if xml_match:
        return xml_match.group(0)
    
    # Если не нашли, пробуем найти любой XML
    xml_match = re.search(r'<[^>]+>.*?</[^>]+>', text, re.DOTALL)
    if xml_match:
        return xml_match.group(0)
    
    # Если ничего не найдено, возвращаем весь текст
    return text


def parse_page_xml(xml_string: str, page_number: int) -> List[Dict]:
    """
    Парсит XML ответ от Ollama и возвращает структурированные данные
    
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
                text_data = {
                    'text': (text_elem.text or '').strip(),
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
