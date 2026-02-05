"""Main API router that aggregates all v1 endpoints."""

from fastapi import APIRouter

from backend.api.v1 import cards, export, prompts, sessions

api_router = APIRouter()

api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
