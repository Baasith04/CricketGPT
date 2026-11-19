from fastapi import APIRouter, HTTPException, Path

from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
)
from app.schemas.matches import (
    MatchDetailResponse,
    MatchScorecardResponse,
    MatchWicketsResponse,
)
from app.services.matches.match_service import get_match_details
from app.services.matches.scorecard_service import (
    get_match_scorecard,
    get_match_wickets,
)

router = APIRouter(
    prefix="/api/matches",
    tags=["Matches"],
)


@router.get(
    "/{match_id}",
    response_model=MatchDetailResponse,
    summary="Get match information",
    description="Returns metadata, teams, venue, date, toss, and outcome for a specific IPL match.",
    responses={
        200: {"model": MatchDetailResponse, "description": "Match details retrieved"},
        404: {"description": "Match ID not found"},
        400: {"description": "Invalid match ID parameter"},
        500: {"description": "Database or server error"},
    },
)
def match_details(
    match_id: int = Path(..., description="Cricsheet match identifier", ge=1),
) -> MatchDetailResponse:
    """Retrieve match information, participating teams, toss outcome, and result."""
    try:
        match = get_match_details(match_id)
        if match is None:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {match_id} was not found.",
            )
        return match
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
            detail="Unable to retrieve match details.",
        )


@router.get(
    "/{match_id}/scorecard",
    response_model=MatchScorecardResponse,
    summary="Get match scorecard",
    description="Returns complete scorecard: innings totals, batter scorecards, bowler figures, and extras. Supports Super Overs explicitly.",
    responses={
        200: {"model": MatchScorecardResponse, "description": "Match scorecard retrieved"},
        404: {"description": "Match ID not found"},
        400: {"description": "Invalid match ID parameter"},
        500: {"description": "Database or server error"},
    },
)
def match_scorecard(
    match_id: int = Path(..., description="Cricsheet match identifier", ge=1),
) -> MatchScorecardResponse:
    """Retrieve full innings scorecards, batting figures, bowling figures, and extras breakdown."""
    try:
        scorecard = get_match_scorecard(match_id)
        if scorecard is None:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {match_id} was not found.",
            )
        return scorecard
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
            detail="Unable to retrieve match scorecard.",
        )


@router.get(
    "/{match_id}/wickets",
    response_model=MatchWicketsResponse,
    summary="Get match fall-of-wickets",
    description="Returns chronological fall-of-wickets details with team score and overs at each dismissal.",
    responses={
        200: {"model": MatchWicketsResponse, "description": "Fall-of-wickets details retrieved"},
        404: {"description": "Match ID not found"},
        400: {"description": "Invalid match ID parameter"},
        500: {"description": "Database or server error"},
    },
)
def match_wickets(
    match_id: int = Path(..., description="Cricsheet match identifier", ge=1),
) -> MatchWicketsResponse:
    """Retrieve fall of wickets per innings with cumulative score and overs."""
    try:
        wickets = get_match_wickets(match_id)
        if wickets is None:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {match_id} was not found.",
            )
        return wickets
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
            detail="Unable to retrieve match wickets.",
        )

