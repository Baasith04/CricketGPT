
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
)


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
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve batting leaderboard.",
        )


@router.get("/bowling")
def bowling_leaderboard(
    category: Literal[
        "wickets",
        "economy",
        "average",
        "strike_rate",
        "five_wickets",
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
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve bowling leaderboard.",
        )


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
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve best bowling figures.",
        )
