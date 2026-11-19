"""
CricketGPT — API Route Controllers

This package holds modular APIRouters for matches, players, teams,
statistics, ingestion synchronization, and the conversational chat interface.
"""

from app.api.routes.chat import router as chat_router
from app.api.routes.leaderboards import router as leaderboard_router
from app.api.routes.matches import router as matches_router
from app.api.routes.players import router as players_router
from app.api.routes.rag import router as rag_router
from app.api.routes.teams import router as teams_router

__all__ = [
    "chat_router",
    "leaderboard_router",
    "matches_router",
    "players_router",
    "rag_router",
    "teams_router",
]
