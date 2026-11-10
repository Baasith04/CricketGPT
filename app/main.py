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

from fastapi import FastAPI, status
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


# ---------------------------------------------------------------------------
# FastAPI Application Instance
# ---------------------------------------------------------------------------
# title, description, version appear in the Swagger UI header.
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CricketGPT",
    description="AI-powered IPL cricket statistics and question-answering assistant.",
    version="0.1.0",
)
app.include_router(chat_router)
app.include_router(leaderboard_router)
app.include_router(matches_router)
app.include_router(players_router)
app.include_router(rag_router)
app.include_router(teams_router)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/",
    response_model=WelcomeResponse,
    summary="Welcome",
    tags=["General"],
)
def root() -> WelcomeResponse:
    """
    Root endpoint — returns a CricketGPT welcome message.

    This is the simplest possible endpoint:
    - No input parameters.
    - Returns a fixed JSON object.
    - Useful to verify the server is running.
    """
    return WelcomeResponse(
        message="Welcome to CricketGPT! Your AI-powered IPL cricket assistant.",
        project="CricketGPT",
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["General"],
)
def health_check() -> HealthResponse:
    """
    Service health check endpoint — confirms the web server is alive.

    Used by:
    - Developers during local testing.
    - Deployment platforms (like Render) to verify process liveness.
    - Does NOT depend on database availability (intentional design).
    """
    return HealthResponse(
        status="healthy",
        service="CricketGPT",
    )


@app.get(
    "/api/info",
    response_model=InfoResponse,
    summary="Application info",
    tags=["General"],
)
def app_info() -> InfoResponse:
    """
    Application info endpoint — returns name, version and environment.
    """
    return InfoResponse(
        app_name="CricketGPT",
        version="0.1.0",
        environment="development",
        description="AI-powered IPL cricket statistics and question-answering assistant.",
    )


@app.get(
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
    """
    Database health check endpoint — tests connectivity to Supabase PostgreSQL.

    Executes a lightweight query (SELECT 1) and inspects PostgreSQL metadata.
    - Returns 200 OK when the database is reachable.
    - Returns 503 Service Unavailable when the database cannot be reached.
    - Never leaks connection strings, passwords, or internal stack traces.
    """
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
