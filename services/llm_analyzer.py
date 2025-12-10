"""
Сервис анализа документов с помощью LLM (Ollama).

Проверяет текстовое содержание документа:
- Соответствие целям и теме
- Основные разделы
- Логичность и структуру
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


@dataclass
class LLMAnalysisResult:
    """Результат анализа документа LLM"""
    success: bool
    score: Optional[float] = None  # Оценка от 0 до 100
    summary: Optional[str] = None  # Краткое резюме
    strengths: Optional[list] = None  # Сильные стороны
    weaknesses: Optional[list] = None  # Слабые стороны
    recommendations: Optional[list] = None  # Рекомендации
    detailed_report: Optional[str] = None  # Подробный отчет
    error: Optional[str] = None  # Сообщение об ошибке


class LLMAnalyzer:
    """
    Анализатор документов на основе LLM (Ollama).
    """
    
    SYSTEM_PROMPT = """Ты — эксперт по анализу академических и технических документов. 
Твоя задача — проанализировать предоставленный текст документа и оценить его качество.

Проанализируй документ по следующим критериям:
1. Соответствие заявленной теме и целям
2. Наличие и качество основных разделов (введение, основная часть, заключение)
3. Логичность и последовательность изложения
4. Структурированность материала
5. Полнота раскрытия темы

Ответ предоставь СТРОГО в формате JSON:
{
    "score": <число от 0 до 100>,
    "summary": "<краткое резюме анализа в 2-3 предложениях>",
    "strengths": ["<сильная сторона 1>", "<сильная сторона 2>", ...],
    "weaknesses": ["<слабая сторона 1>", "<слабая сторона 2>", ...],
    "recommendations": ["<рекомендация 1>", "<рекомендация 2>", ...],
    "detailed_report": "<подробный анализ документа>"
}

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без дополнительного текста."""

    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    def analyze_document(self, document_text: str, document_title: str = "") -> LLMAnalysisResult:
        """
        Анализирует текст документа с помощью LLM.
        
        Args:
            document_text: Текст документа для анализа
            document_title: Название документа (опционально)
            
        Returns:
            LLMAnalysisResult с результатами анализа
        """
        if not document_text or len(document_text.strip()) < 100:
            return LLMAnalysisResult(
                success=False,
                error="Текст документа слишком короткий для анализа"
            )
        
        # Ограничиваем размер текста (LLM имеют лимит контекста)
        max_chars = 15000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "\n\n[... текст сокращён ...]"
        
        # Формируем запрос
        user_prompt = f"""Проанализируй следующий документ:

Название: {document_title or 'Без названия'}

Текст документа:
---
{document_text}
---

Предоставь анализ в формате JSON."""

        try:
            response = self._call_ollama(user_prompt)
            return self._parse_response(response)
        except requests.exceptions.ConnectionError:
            return LLMAnalysisResult(
                success=False,
                error=f"Не удалось подключиться к Ollama по адресу {self.host}"
            )
        except requests.exceptions.Timeout:
            return LLMAnalysisResult(
                success=False,
                error=f"Превышено время ожидания ответа от LLM ({self.timeout} сек)"
            )
        except Exception as e:
            return LLMAnalysisResult(
                success=False,
                error=f"Ошибка при анализе: {str(e)}"
            )
    
    def _call_ollama(self, prompt: str) -> str:
        """Вызов Ollama API"""
        url = f"{self.host}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": self.SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Низкая температура для более детерминированного ответа
                "num_predict": 2000
            }
        }
        
        response = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama вернул ошибку: {response.status_code} - {response.text}")
        
        result = response.json()
        return result.get("response", "")
    
    def _parse_response(self, response: str) -> LLMAnalysisResult:
        """Парсинг ответа LLM"""
        try:
            # Пытаемся найти JSON в ответе
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                # JSON не найден, пробуем использовать весь ответ как отчет
                return LLMAnalysisResult(
                    success=True,
                    score=50,
                    summary="Анализ выполнен, но результат в нестандартном формате",
                    detailed_report=response,
                    strengths=[],
                    weaknesses=[],
                    recommendations=[]
                )
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            return LLMAnalysisResult(
                success=True,
                score=float(data.get("score", 50)),
                summary=data.get("summary", ""),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                recommendations=data.get("recommendations", []),
                detailed_report=data.get("detailed_report", "")
            )
            
        except json.JSONDecodeError as e:
            # Если не удалось распарсить JSON, возвращаем сырой ответ
            return LLMAnalysisResult(
                success=True,
                score=50,
                summary="Анализ выполнен",
                detailed_report=response,
                strengths=[],
                weaknesses=[],
                recommendations=[],
                error=f"Не удалось распарсить JSON ответ: {str(e)}"
            )
    
    def check_connection(self) -> bool:
        """Проверка подключения к Ollama"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_available_models(self) -> list:
        """Получение списка доступных моделей"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []
