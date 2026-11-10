
import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.error_logging import log_sanitized_exception
from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/leaderboards",
    tags=["Leaderboards"],
)


@router.get("/batting")
def batting_leaderboard(
    category: Literal[
        "runs",
        "highest_score",
        "sixes",
        "fours",
        "average",
        "strike_rate",
        "centuries",
        "fifties",
    ] = "runs",
    season: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
    min_balls: int = Query(default=0, ge=0),
):
    """Get an IPL batting leaderboard."""

    try:
        return get_batting_leaderboard(
            category=category,
            season=season,
            limit=limit,
            min_balls=min_balls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_sanitized_exception(logger, "Error in GET /api/leaderboards/batting", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve batting leaderboard.",
        ) from exc


@router.get("/bowling")
def bowling_leaderboard(
    category: Literal[
        "wickets",
        "economy",
        "average",
        "strike_rate",
        "five_wickets",
        "dot_balls",
    ] = "wickets",
    season: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
    min_balls: int = Query(default=0, ge=0),
):
    """Get an IPL bowling leaderboard."""

    try:
        return get_bowling_leaderboard(
            category=category,
            season=season,
            limit=limit,
            min_balls=min_balls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_sanitized_exception(logger, "Error in GET /api/leaderboards/bowling", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve bowling leaderboard.",
        ) from exc


@router.get("/best-bowling")
def best_bowling_figures(
    season: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
):
    """Get the best individual bowling figures in IPL history."""

    try:
        return get_best_bowling_figures(
            season=season,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_sanitized_exception(logger, "Error in GET /api/leaderboards/best-bowling", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve best bowling figures.",
        ) from exc
