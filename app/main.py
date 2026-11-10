"""
CricketGPT — Main FastAPI Application

This is the entry point of the CricketGPT backend.
It creates the FastAPI application instance and registers all API routes.

Key concepts:
- FastAPI() creates the web application object.
- @app.get() is a decorator that registers a function to handle GET requests.
- Pydantic models define the shape of API responses (type-safe JSON).
- The function return value is automatically converted to a JSON response.
- Database health checks verify live connectivity without exposing credentials.
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.api.routes.chat import router as chat_router
from app.api.routes.leaderboards import router as leaderboard_router
from app.api.routes.matches import router as matches_router
from app.api.routes.players import router as players_router
from app.api.routes.rag import router as rag_router
from app.api.routes.teams import router as teams_router

from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    check_database_connection,
)


# ---------------------------------------------------------------------------
# Pydantic Response Models
# ---------------------------------------------------------------------------
# These classes define the exact structure of each JSON response.
# FastAPI uses them to:
#   1. Validate the data your code returns.
#   2. Generate the Swagger/OpenAPI documentation automatically.
#   3. Show example responses in the docs UI.
# ---------------------------------------------------------------------------

class WelcomeResponse(BaseModel):
    """Response model for the root welcome endpoint."""
    message: str
    project: str


class HealthResponse(BaseModel):
    """Response model for the service health check endpoint."""
    status: str
    service: str


class InfoResponse(BaseModel):
    """Response model for the application info endpoint."""
    app_name: str
    version: str
    environment: str
    description: str


class DatabaseHealthResponse(BaseModel):
    """Response model for a successful database health check."""
    status: str
    database: str


class DatabaseErrorResponse(BaseModel):
    """Response model for a failed database health check."""
    status: str
    message: str


def parse_cors_origins(raw_origins: Optional[str] = None) -> List[str]:
    """Parse comma-separated allowed origins from CORS_ALLOW_ORIGINS."""
    value = raw_origins if raw_origins is not None else os.getenv("CORS_ALLOW_ORIGINS", "")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def build_cors_config(raw_origins: Optional[str] = None) -> Dict[str, Any]:
    """
    Build CORSMiddleware configuration from CORS_ALLOW_ORIGINS.
    Never enables allow_credentials alongside a wildcard ('*') origin.
    """
    origins = parse_cors_origins(raw_origins)
    has_wildcard = "*" in origins
    return {
        "allow_origins": ["*"] if has_wildcard else origins,
        "allow_credentials": bool(origins) and not has_wildcard,
        "allow_methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type", "X-API-Key"],
    }


def create_app() -> FastAPI:
    """Create and configure the CricketGPT FastAPI application."""
    application = FastAPI(
        title="CricketGPT",
        description="AI-powered IPL cricket statistics and question-answering assistant.",
        version="0.1.0",
    )
    cors_cfg = build_cors_config()
    application.add_middleware(CORSMiddleware, **cors_cfg)
    application.include_router(chat_router)
    application.include_router(leaderboard_router)
    application.include_router(matches_router)
    application.include_router(players_router)
    application.include_router(rag_router)
    application.include_router(teams_router)

    @application.get(
        "/",
        response_model=WelcomeResponse,
        summary="Welcome",
        tags=["General"],
    )
    def root() -> WelcomeResponse:
        return WelcomeResponse(
            message="Welcome to CricketGPT! Your AI-powered IPL cricket assistant.",
            project="CricketGPT",
        )

    @application.get(
        "/health",
        response_model=HealthResponse,
        summary="Service health check",
        tags=["General"],
    )
    def health_check() -> HealthResponse:
        return HealthResponse(
            status="healthy",
            service="CricketGPT",
        )

    @application.get(
        "/api/info",
        response_model=InfoResponse,
        summary="Application info",
        tags=["General"],
    )
    def app_info() -> InfoResponse:
        return InfoResponse(
            app_name="CricketGPT",
            version="0.1.0",
            environment="development",
            description="AI-powered IPL cricket statistics and question-answering assistant.",
        )

    @application.get(
        "/health/database",
        response_model=DatabaseHealthResponse,
        responses={
            200: {"model": DatabaseHealthResponse, "description": "Database is reachable"},
            503: {"model": DatabaseErrorResponse, "description": "Database connection failed"},
        },
        summary="Database health check",
        tags=["Database"],
    )
    def database_health_check():
        try:
            result = check_database_connection()
            return DatabaseHealthResponse(**result)
        except (DatabaseConfigurationError, DatabaseConnectionError):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "message": "Database connection failed"},
            )
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "message": "Database connection failed"},
            )

    return application


# ---------------------------------------------------------------------------
# FastAPI Application Instance
# ---------------------------------------------------------------------------

app = create_app()
