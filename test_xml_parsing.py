"""
Тесты для проверки парсинга XML с программным кодом
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.xml_parser import parse_page_xml, extract_xml_from_text, _escape_code_in_xml
import html


def test_python_code_in_xml():
    """Тест обработки Python кода в XML"""
    print("=" * 60)
    print("ТЕСТ 1: Python код в XML")
    print("=" * 60)
    
    xml_with_code = '''<page number="1">
  <block short-description="код" position-x="10" position-y="20" width="100" height="50">
    <text font-family="monospace" font-size="12" color="#000000" position-x="10" position-y="20" width="100" height="50">
      def hello():
          if x < 5 and y > 10:
              return "test"
    </text>
  </block>
</page>'''
    
    try:
        blocks = parse_page_xml(xml_with_code, 1)
        assert len(blocks) == 1
        assert len(blocks[0]['text_elements']) == 1
        
        text = blocks[0]['text_elements'][0]['text']
        print(f"Извлеченный текст: {repr(text)}")
        
        # Проверяем, что символы < и > сохранены
        assert '<' in text
        assert '>' in text
        assert 'if x < 5' in text
        
        print("✓ Python код успешно обработан")
        return True
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_java_code_in_xml():
    """Тест обработки Java кода в XML"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Java код в XML")
    print("=" * 60)
    
    xml_with_code = '''<page number="1">
  <block short-description="код" position-x="10" position-y="20" width="100" height="50">
    <text font-family="monospace" font-size="12" color="#000000" position-x="10" position-y="20" width="100" height="50">
      if (x < 5 && y > 10) {
          return "test";
      }
    </text>
  </block>
</page>'''
    
    try:
        blocks = parse_page_xml(xml_with_code, 1)
        assert len(blocks) == 1
        
        text = blocks[0]['text_elements'][0]['text']
        print(f"Извлеченный текст: {repr(text)}")
        
        assert '<' in text
        assert '>' in text
        assert 'x < 5' in text
        assert 'y > 10' in text
        
        print("✓ Java код успешно обработан")
        return True
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_escape_function():
    """Тест функции экранирования"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Функция экранирования")
    print("=" * 60)
    
    xml_with_code = '''<page number="1">
  <block short-description="код" position-x="10" position-y="20" width="100" height="50">
    <text font-family="monospace" font-size="12" color="#000000" position-x="10" position-y="20" width="100" height="50">
      if x < 5 and y > 10:
          return "test & value"
    </text>
  </block>
</page>'''
    
    escaped = _escape_code_in_xml(xml_with_code)
    print(f"Экранированный XML содержит &lt;: {'&lt;' in escaped or '<' in escaped}")
    print(f"Экранированный XML содержит &gt;: {'&gt;' in escaped or '>' in escaped}")
    
    # Проверяем, что XML все еще валиден
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(escaped)
        print("✓ Экранированный XML валиден")
        return True
    except Exception as e:
        print(f"✗ Экранированный XML невалиден: {e}")
        return False


def test_markdown_extraction():
    """Тест извлечения XML из markdown"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Извлечение XML из markdown")
    print("=" * 60)
    
    markdown_text = '''Вот XML ответ:

```xml
<page number="1">
  <block short-description="текст" position-x="10" position-y="20" width="100" height="50">
    <text>Привет</text>
  </block>
</page>
```

Это конец.'''
    
    extracted = extract_xml_from_text(markdown_text)
    print(f"Извлеченный XML начинается с <page>: {extracted.startswith('<page')}")
    print(f"Извлеченный XML заканчивается на </page>: {extracted.endswith('</page>')}")
    
    if extracted.startswith('<page') and extracted.endswith('</page>'):
        print("✓ XML успешно извлечен из markdown")
        return True
    else:
        print(f"✗ Не удалось извлечь XML. Получено: {extracted[:100]}")
        return False


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ПАРСИНГА XML С ПРОГРАММНЫМ КОДОМ")
    print("=" * 60)
    
    results = []
    results.append(test_python_code_in_xml())
    results.append(test_java_code_in_xml())
    results.append(test_escape_function())
    results.append(test_markdown_extraction())
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"Пройдено: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✓ Все тесты пройдены успешно!")
        return 0
    else:
        print("\n✗ Некоторые тесты не пройдены")
        return 1


if __name__ == "__main__":
    sys.exit(main())
