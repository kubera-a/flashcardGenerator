"""
Configuration Module
------------------
Configuration settings for the Anki Flashcard Generator.

Note: Prompt templates are defined in config/prompts.py
"""

import os
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, using os.environ directly

# Base directories - can be overridden via environment variables
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("FLASHCARD_DATA_DIR", ROOT_DIR / "data"))

# User-facing directories (intuitive names)
# - INPUT_DIR: Place documents here (PDFs, markdown ZIPs)
# - EXPORTS_DIR: Exported Anki files appear here
INPUT_DIR = Path(os.getenv("FLASHCARD_INPUT_DIR", DATA_DIR / "input"))
EXPORTS_DIR = Path(os.getenv("FLASHCARD_EXPORTS_DIR", DATA_DIR / "exports"))

# Internal processing directories (hidden from user)
PROCESSING_DIR = DATA_DIR / ".processing"
UPLOADS_DIR = PROCESSING_DIR / "uploads"  # Temp storage for uploaded files
EXTRACTIONS_DIR = PROCESSING_DIR / "extractions"  # Extracted markdown/PDF content
CARD_IMAGES_DIR = PROCESSING_DIR / "images"  # Stored card images

# Legacy alias for backwards compatibility
OUTPUT_DIR = EXPORTS_DIR

# Create directories if they don't exist
for directory in [
    DATA_DIR,
    INPUT_DIR,
    EXPORTS_DIR,
    PROCESSING_DIR,
    UPLOADS_DIR,
    EXTRACTIONS_DIR,
    CARD_IMAGES_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

# LLM parameters
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4",
        "temperature": 0,
        "max_tokens": 1000,
    },
    "anthropic": {
        "model": "claude-sonnet-4-5",
        "temperature": 0,
        "max_tokens": 32768,
    },
}

# Anki configuration
ANKI_CONFIG = {
    "default_deck": "Generated::Software_Engineering",
    "default_tags": ["auto_generated", "software_engineering"],
    "card_format": "basic",  # basic, cloze, etc.
}

# AnkiConnect configuration
# In Docker, use host.docker.internal to reach the host machine where Anki runs
ANKI_CONNECT_URL = os.getenv(
    "ANKI_CONNECT_URL", "http://host.docker.internal:8765"
)

# Processing options (for text extraction fallback)
CHUNK_SIZE = 12000  # characters (~12,000 tokens)

# Logging configuration


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames and Anki media references."""
    import re
    return re.sub(r'[^\w\-.]', '_', name.replace(" ", "_").lower())


LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": str(ROOT_DIR / "logs" / "app.log"),
            "mode": "a",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        }
    },
}
