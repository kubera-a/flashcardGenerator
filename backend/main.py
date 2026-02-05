"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.v1.router import api_router
from backend.db.database import init_db
from backend.services.prompt_service import seed_initial_prompts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    seed_initial_prompts()
    yield
    # Shutdown (nothing to do)


app = FastAPI(
    title="Flashcard Generator API",
    description="API for generating and reviewing Anki flashcards from PDFs",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # Docker frontend
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Static files for exports
exports_dir = Path(__file__).parent.parent / "data" / "exports"
exports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(exports_dir)), name="exports")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
