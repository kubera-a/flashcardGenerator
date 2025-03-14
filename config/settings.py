"""
Configuration Module
------------------
Configuration settings and prompts for the Anki Flashcard Generator.
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

# Prompt templates for card generation
CARD_GENERATION_PROMPTS = {
    "system_prompt": """
    You are an expert in creating educational flashcards for software engineering topics.
    Your task is to generate high-quality Anki flashcards that follow best practices 
    for effective learning and retention.
    
    Always return your response in valid JSON format with no additional text or explanation.
    """,

    "user_prompt_template": """
    I need you to create effective Anki flashcards based on the following content from a technical document about software engineering.
    
    Document Information:
    Title: {title}
    Author: {author}
    
    Content:
    ```
    {content}
    ```
    
    Create up to {max_cards} high-quality flashcards with the following characteristics:
    1. Each card should focus on a single, clear concept
    2. The question (front) should be specific and unambiguous
    3. The answer (back) should be concise but complete
    4. Prioritize important concepts over trivial details
    5. Avoid overly complex or compound questions
    6. Formulate questions that test understanding, not just recall
    7. Use clear, straightforward language
    
    For technical content, create cards that:
    - Focus on core principles and concepts
    - Include key definitions of important terms
    - Cover relationships between concepts
    - Address common misconceptions
    - Include practical applications where relevant
    
    Return the cards as JSON only.
    """
}

# Prompt templates for card validation
CARD_VALIDATION_PROMPTS = {
    "system_prompt": """
    You are an expert in educational psychology and spaced repetition learning.
    Your task is to review and improve flashcards for effectiveness.
    
    Return only valid JSON with the improved cards. Do not include any explanations or additional text.
    """,

    "user_prompt_template": """
    Review the following flashcards for quality and effectiveness:
    
    {cards_str}
    
    For each card, evaluate:
    1. Is the question clear and specific?
    2. Is the answer concise but complete?
    3. Does the card focus on an important concept?
    4. Is the card formatted properly?
    
    Improve any cards that don't meet these criteria.
    Return only the improved cards in JSON format.
    """
}

# Output formats for LLM responses
OUTPUT_FORMATS = {
    "card_generation": {
        "cards": [
            {
                "front": "Question text goes here",
                "back": "Answer text goes here",
                "tags": ["tag1", "tag2"]
            }
        ]
    },

    "card_validation": {
        "improved_cards": [
            {
                "front": "Improved question text",
                "back": "Improved answer text",
                "tags": ["tag1", "tag2"]
            }
        ]
    }
}

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
