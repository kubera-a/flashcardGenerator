"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.v1.router import api_router
from backend.db.database import SessionLocal, init_db
from backend.db.models import Session as DBSession
from backend.db.models import SessionStatus
from backend.services.prompt_service import seed_initial_prompts
from config.settings import EXPORTS_DIR


def recover_stuck_sessions():
    """Reset any sessions stuck in 'processing' state from a previous crash/restart."""
    db = SessionLocal()
    try:
        stuck = db.query(DBSession).filter(
            DBSession.status == SessionStatus.PROCESSING.value
        ).all()
        for session in stuck:
            session.status = SessionStatus.FAILED.value
        if stuck:
            db.commit()
            print(f"Recovered {len(stuck)} stuck session(s) from 'processing' to 'failed'")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    seed_initial_prompts()
    recover_stuck_sessions()
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
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
