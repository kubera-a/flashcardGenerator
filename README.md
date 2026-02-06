# Anki Flashcard Generator

An automated system for generating high-quality Anki flashcards from PDF documents using Large Language Models.

## Features

- **PDF Processing**: Extract and clean text from PDF documents
- **Claude Native PDF Support**: Send PDFs directly to Claude for better understanding of visual elements, charts, and diagrams
- **Page Selection**: Preview PDF pages and select specific pages to generate flashcards from
- **Intelligent Card Generation**: Use LLMs to create effective question-answer pairs
- **Card Review Workflow**: Approve, reject, or edit generated cards with feedback (change your decision anytime)
- **Auto-Correction**: LLM-powered card improvement based on rejection feedback
- **Export Options**: Export to Anki or download CSV directly with save dialog
- **Prompt Evolution**: System learns from your feedback to improve future card generation
- **Anki Integration**: Export approved cards in a format ready for Anki import
- **Flexible API Support**: Works with OpenAI (GPT-4) or Anthropic (Claude) models

## Architecture

The system consists of several components:

### Backend (FastAPI)
- **Session Management**: Upload PDFs, track processing status
- **Card Management**: CRUD operations, approve/reject/edit cards
- **Prompt Evolution**: Analyze feedback and suggest prompt improvements
- **Export Service**: Generate Anki-compatible CSV files

### Frontend (React + TypeScript)
- **PDF Upload**: Drag-and-drop with page preview and selection
- **Card Review**: Interactive card review with approve/reject/edit actions
- **Prompt Management**: View and apply prompt improvement suggestions

### Core Modules
1. **PDF Processor**: Handles PDF extraction and preprocessing
2. **LLM Interface**: Communicates with LLM providers (OpenAI or Anthropic)
3. **Card Generation**: Creates flashcards from extracted content
4. **Anki Integration**: Formats and exports cards for Anki

## Installation

### Option 1: Docker (Recommended)

The easiest way to run the application is with Docker Compose, which handles all dependencies automatically.

**Prerequisites:**
- Docker and Docker Compose

**Setup:**

```bash
# Clone the repository
git clone https://github.com/yourusername/flashcardgenerator.git
cd flashcardgenerator

# Create .env file with your API keys
cp .env.template .env
# Edit .env with your API keys (OPENAI_API_KEY and/or ANTHROPIC_API_KEY)

# Build and start the containers
docker compose up --build
```

Open http://localhost:3000 in your browser.

To stop the application:
```bash
docker compose down
```

### Option 2: Local Development

For development or if you prefer not to use Docker.

**Prerequisites:**
- Python 3.12+
- Node.js 18+
- UV (for Python package management)
- Poppler (for PDF thumbnail generation):
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `apt-get install poppler-utils`
  - Windows: Download from [poppler releases](https://github.com/osber/poppler-windows/releases)

**Backend Setup:**

```bash
# Clone the repository
git clone https://github.com/yourusername/flashcardgenerator.git
cd flashcardgenerator

# Create and activate a virtual environment with UV
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv sync

# Create .env file with your API keys
cp .env.template .env
# Edit .env with your API keys (OPENAI_API_KEY and/or ANTHROPIC_API_KEY)
```

**Frontend Setup:**

```bash
cd frontend
npm install
```

## Usage

### Running with Docker

```bash
docker compose up
```

Open http://localhost:3000 in your browser.

### Running Locally (Development)

Start the backend server:

```bash
# From the project root
uv run uvicorn backend.main:app --reload
```

Start the frontend development server (in a separate terminal):

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

### Web Interface Workflow

1. **Upload PDF**: Drag and drop a PDF or click to select
2. **Select Pages**: Preview pages and select which ones to generate cards from
3. **Choose Provider**:
   - **Anthropic (Claude)**: Uses native PDF support for better visual understanding
   - **OpenAI (GPT-4)**: Uses text extraction
4. **Generate Cards**: Click to start generation
5. **Review Cards**: Approve, reject (with feedback), or edit each card
   - You can change your decision at any time (approve a rejected card, reject an approved card)
   - Finalized sessions can still be viewed and cards re-exported
6. **Finalize Session**: Triggers prompt evolution analysis
7. **Export**: Download approved cards as Anki-compatible CSV
   - "Export to Anki" opens the file in a new tab
   - "Download CSV" triggers a save dialog to choose the download location

### Command Line Interface

Generate flashcards from a PDF document:

```bash
uv run python -m cli generate path/to/document.pdf --llm anthropic --max-cards 50
```

Check if your API keys are configured correctly:

```bash
uv run python -m cli check-api --llm anthropic
```

### CLI Options

- `--output`, `-o`: Specify the output file path
- `--llm`: Choose the LLM provider ('openai' or 'anthropic')
- `--max-cards`: Set the maximum number of cards to generate
- `--verbose`, `-v`: Enable verbose output

## Configuration

The project uses a modular configuration system:

- LLM parameters (models, temperature, tokens) are configured in `config/settings.py`
- Anki export settings (default deck, tags) can be customized
- Processing options like chunk size and cards per chunk can be adjusted

## Project Structure

```
flashcardgenerator/
├── backend/               # FastAPI backend
│   ├── api/v1/            # API endpoints
│   ├── db/                # Database models and schemas
│   ├── services/          # Business logic
│   └── main.py            # FastAPI app
├── frontend/              # React frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── api/           # API client
│   │   └── types/         # TypeScript types
│   └── package.json
├── modules/               # Core modules
│   ├── pdf_processor.py   # PDF text extraction
│   ├── llm_interface.py   # LLM API integration
│   ├── card_generation.py # Flashcard creation
│   └── anki_integration.py # Anki export
├── config/                # Configuration settings
├── data/                  # SQLite database and uploads
├── cli.py                 # Command-line interface
├── pyproject.toml         # Python dependencies
└── .env                   # Environment variables
```

## Native PDF Support

When using Anthropic (Claude), the system can send PDFs directly to the API instead of extracting text. This provides:

- Better understanding of visual elements (charts, diagrams, tables)
- More accurate content extraction
- Support for complex layouts

The native PDF feature:
- Supports up to 100 pages per request
- Maximum file size of 32MB
- Can be toggled on/off in the upload UI

## Importing Cards into Anki

1. Open Anki on your computer
2. Click "Import File" from the main screen
3. Select the generated CSV file
4. Configure the import settings as described in the generated instructions file
5. Click "Import"

## License

To be filled

## Acknowledgements

This project uses the following technologies:

- [OpenAI API](https://openai.com/api/) and [Anthropic API](https://anthropic.com/) for LLM capabilities
- [FastAPI](https://fastapi.tiangolo.com/) for the backend API
- [React](https://react.dev/) for the frontend
- [PyPDF2](https://pypi.org/project/PyPDF2/) and [pdfminer.six](https://pypi.org/project/pdfminer.six/) for PDF processing
- [pdf2image](https://pypi.org/project/pdf2image/) for PDF thumbnail generation
- [SQLAlchemy](https://www.sqlalchemy.org/) for database ORM
- [Click](https://click.palletsprojects.com/) for the command-line interface
- [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- [UV](https://github.com/astral-sh/uv) for Python environment management
