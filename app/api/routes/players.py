from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
)
from app.schemas.players import (
    PlayerBattingStatsResponse,
    PlayerBowlingStatsResponse,
)
from app.services.statistics.batting_service import (
    get_batting_leaderboard,
    get_player_batting_stats,
)
from app.services.statistics.bowling_service import (
    get_bowling_leaderboard,
    get_player_bowling_stats,
)

router = APIRouter(
    prefix="/api/players",
    tags=["Players"],
)


# ---------------------------------------------------------------------------
# Leaderboard Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/leaderboard/batting",
    response_model=List[PlayerBattingStatsResponse],
    summary="Get IPL batting leaderboard",
    description="Returns top IPL run-scorers ranked by total runs descending.",
)
def batting_leaderboard(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of players to return (1-100)",
    ),
) -> List[PlayerBattingStatsResponse]:
    """Retrieve the top IPL run-scorers."""
    try:
        return get_batting_leaderboard(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve batting leaderboard.",
        )


@router.get(
    "/leaderboard/bowling",
    response_model=List[PlayerBowlingStatsResponse],
    summary="Get IPL bowling leaderboard",
    description="Returns top IPL wicket-takers ranked by wickets descending and economy ascending.",
)
def bowling_leaderboard(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of players to return (1-100)",
    ),
) -> List[PlayerBowlingStatsResponse]:
    """Retrieve the top IPL wicket-takers."""
    try:
        return get_bowling_leaderboard(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve bowling leaderboard.",
        )


# ---------------------------------------------------------------------------
# Individual Player Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{player_id}/batting",
    response_model=PlayerBattingStatsResponse,
    summary="Get player career batting statistics",
    description="Returns career IPL batting statistics for a specific player by Cricsheet ID.",
    responses={
        200: {"model": PlayerBattingStatsResponse, "description": "Batting statistics retrieved"},
        404: {"description": "Player has no batting statistics or not found"},
        400: {"description": "Invalid player ID"},
        500: {"description": "Database or server error"},
    },
)
def player_batting_stats(
    player_id: str = Path(..., description="Cricsheet player identifier"),
) -> PlayerBattingStatsResponse:
    """Retrieve career IPL batting statistics for one player."""
    normalized_id = player_id.strip() if player_id else ""
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Player ID cannot be empty.")

    try:
        stats = get_player_batting_stats(normalized_id)
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"Player '{player_id}' has no batting statistics.",
            )
        return stats
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve player batting statistics.",
        )


@router.get(
    "/{player_id}/bowling",
    response_model=PlayerBowlingStatsResponse,
    summary="Get player career bowling statistics",
    description="Returns career IPL bowling statistics for a specific player by Cricsheet ID.",
    responses={
        200: {"model": PlayerBowlingStatsResponse, "description": "Bowling statistics retrieved"},
        404: {"description": "Player has no bowling statistics or not found"},
        400: {"description": "Invalid player ID"},
        500: {"description": "Database or server error"},
    },
)
def player_bowling_stats(
    player_id: str = Path(..., description="Cricsheet player identifier"),
) -> PlayerBowlingStatsResponse:
    """Retrieve career IPL bowling statistics for one player."""
    normalized_id = player_id.strip() if player_id else ""
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Player ID cannot be empty.")

    try:
        stats = get_player_bowling_stats(normalized_id)
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"Player '{player_id}' has no bowling statistics.",
            )
        return stats
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve player bowling statistics.",
        )

