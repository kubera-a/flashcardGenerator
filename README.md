# Anki Flashcard Generator

An automated system for generating high-quality Anki flashcards from PDF documents using Large Language Models.

## Features

- **PDF Processing**: Extract and clean text from PDF documents
- **Intelligent Card Generation**: Use LLMs to create effective question-answer pairs
- **Quality Assurance**: Validate and improve generated cards for better learning outcomes
- **Anki Integration**: Export cards in a format ready for Anki import
- **Flexible API Support**: Works with OpenAI (GPT-4) or Anthropic (Claude) models

## Architecture

The system consists of several modules working together:

1. **Input Processing Module**: Handles PDF extraction and preprocessing
2. **LLM Interface**: Communicates with LLM providers (OpenAI or Anthropic)
3. **Card Generation Module**: Creates flashcards from extracted content
4. **Quality Assurance Module**: Validates and improves generated cards
5. **Anki Integration Module**: Formats and exports cards for Anki
6. **Orchestration & Control**: Coordinates the end-to-end process

## Installation

### Prerequisites

- Python 3.12+
- UV (for package and environment management)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/flashcardgenerator.git
cd flashcardgenerator

# Create and activate a virtual environment with UV
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies using UV and pyproject.toml
uv pip install .

# Create .env file with your API keys
cp .env.template .env
# Edit .env with your API keys
```

## Development Setup

For developers who want to contribute to the project:

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

## Usage

### Command Line Interface

Generate flashcards from a PDF document:

```bash
python -m cli generate path/to/document.pdf --llm openai --max-cards 50
```

Check if your API keys are configured correctly:

```bash
python -m cli check-api --llm openai
```

### Options

- `--output`, `-o`: Specify the output file path
- `--llm`: Choose the LLM provider ('openai' or 'anthropic')
- `--max-cards`: Set the maximum number of cards to generate
- `--verbose`, `-v`: Enable verbose output

## Importing Cards into Anki

1. Open Anki on your computer
2. Click "Import File" from the main screen
3. Select the generated CSV file
4. Configure the import settings as described in the generated instructions file
5. Click "Import"

## Configuration

The project uses a modular configuration system:

- LLM parameters (models, temperature, tokens) are configured in `config/settings.py`
- Anki export settings (default deck, tags) can be customized
- Processing options like chunk size and cards per chunk can be adjusted

## Project Structure

```
flashcardgenerator/
├── config/                # Configuration settings
├── modules/               # Core modules
│   ├── pdf_processor.py   # PDF text extraction
│   ├── llm_interface.py   # LLM API integration
│   ├── card_generation.py # Flashcard creation
│   └── anki_exporter.py   # Anki export formatting
├── utils/                 # Utility functions
│   └── pipeline.py        # Processing pipeline
├── cli.py                 # Command-line interface
├── main.py                # Application entry point
├── pyproject.toml         # Project configuration and dependencies
└── .env                   # Environment variables (API keys)
```

## License

To be filled

## Acknowledgements

This project uses the following technologies:

- [OpenAI API](https://openai.com/api/) and [Anthropic API](https://anthropic.com/) for LLM capabilities
- [PyPDF2](https://pypi.org/project/PyPDF2/) and [pdfminer.six](https://pypi.org/project/pdfminer.six/) for PDF processing
- [Click](https://click.palletsprojects.com/) for the command-line interface
- [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- [UV](https://github.com/astral-sh/uv) for Python environment management
- [Ruff](https://github.com/astral-sh/ruff) for code linting and formatting