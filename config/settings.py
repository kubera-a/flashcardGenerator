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

# Base directories
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

# LLM parameters
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4",
        "temperature": 0.3,
        "max_tokens": 1000,
    },
    "anthropic": {
        "model": "claude-sonnet-4-5",
        "temperature": 0.3,
        "max_tokens": 16384,
    }
}

# Anki configuration
ANKI_CONFIG = {
    "default_deck": "Generated::Software_Engineering",
    "default_tags": ["auto_generated", "software_engineering"],
    "card_format": "basic"  # basic, cloze, etc.
}

# Processing options (for text extraction fallback)
CHUNK_SIZE = 3000  # characters
MAX_CARDS_PER_CHUNK = 5

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": str(ROOT_DIR / "logs" / "app.log"),
            "mode": "a"
        }
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True
        }
    }
}
