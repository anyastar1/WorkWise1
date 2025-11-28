"""
Конфигурация приложения WorkWise
"""

import os

# ============================================================================
# API CONFIGURATION
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.250:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-vl:4b-instruct")

# ============================================================================
# FILE UPLOAD CONFIGURATION
# ============================================================================

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"docx", "pdf"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB max file size

# ============================================================================
# FLASK CONFIGURATION
# ============================================================================

SECRET_KEY = os.urandom(24)

# ============================================================================
# DOCUMENT PROCESSOR CONFIGURATION
# ============================================================================

DOCUMENT_PROCESSOR_DPI = 150
DOCUMENT_PROCESSOR_MAX_PAGES = 30
