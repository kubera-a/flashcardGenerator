"""Configuration settings for the Anki Flashcard Generator."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
ROOT_DIR = Path(__file__).parent.parent.parent
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
        "model": "claude-3-opus-20240229",
        "temperature": 0.3,
        "max_tokens": 1000,
    }
}

# Anki configuration
ANKI_CONFIG = {
    "default_deck": "Generated::Software_Engineering",
    "default_tags": ["auto_generated", "software_engineering"],
    "card_format": "basic"  # basic, cloze, etc.
}

# Processing options
CHUNK_SIZE = 3000  # characters
MAX_CARDS_PER_CHUNK = 5