from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
)
from app.schemas.teams import (
    SeasonChampionshipResponse,
    TeamDetailStatsResponse,
    TeamHeadToHeadResponse,
    TeamOverallStatsResponse,
)
from app.services.teams.team_statistics_service import (
    get_individual_team_statistics,
    get_team_championships,
    get_team_head_to_head,
    get_teams_overall_statistics,
)

router = APIRouter(
    prefix="/api/teams",
    tags=["Teams"],
)


# ---------------------------------------------------------------------------
# 1. Overall Team Statistics
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[TeamOverallStatsResponse],
    summary="Get overall IPL team statistics",
    description="Returns matches played, wins, losses, ties, no-results, win percentage, and championships for all franchises.",
)
def teams_overall_statistics(
    active_only: bool = Query(
        default=False,
        description="Filter to active franchises only (exclude defunct teams)",
    ),
) -> List[TeamOverallStatsResponse]:
    """Retrieve all-time match statistics for all IPL teams."""
    try:
        return get_teams_overall_statistics(active_only=active_only)
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve team statistics.",
        )


# ---------------------------------------------------------------------------
# 2. Championship Titles by Season
# ---------------------------------------------------------------------------

@router.get(
    "/championships",
    response_model=List[SeasonChampionshipResponse],
    summary="Get IPL championship titles by season",
    description="Returns the tournament champion and final match details for each IPL season.",
)
def team_championships() -> List[SeasonChampionshipResponse]:
    """Retrieve all IPL championship titles by season."""
    try:
        return get_team_championships()
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve championship titles.",
        )


# ---------------------------------------------------------------------------
# 3. Head-to-Head Statistics
# ---------------------------------------------------------------------------

@router.get(
    "/head-to-head",
    response_model=TeamHeadToHeadResponse,
    summary="Get team head-to-head statistics",
    description="Returns all-time head-to-head match records between two IPL teams.",
    responses={
        200: {"model": TeamHeadToHeadResponse, "description": "Head-to-head record retrieved"},
        400: {"description": "Missing, identical, or ambiguous team parameters"},
        404: {"description": "One or both teams not found"},
        500: {"description": "Database or server error"},
    },
)
def team_head_to_head(
    team_one: str = Query(..., description="First team name, short code, or ID"),
    team_two: str = Query(..., description="Second team name, short code, or ID"),
) -> TeamHeadToHeadResponse:
    """Retrieve head-to-head match record between two teams."""
    t1 = team_one.strip() if team_one else ""
    t2 = team_two.strip() if team_two else ""

    if not t1 or not t2:
        raise HTTPException(
            status_code=400,
            detail="Both team_one and team_two parameters are required.",
        )

    try:
        return get_team_head_to_head(t1, t2)
    except ValueError as exc:
        err_msg = str(exc)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(
            status_code=500,
            detail="Database service unavailable.",
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve head-to-head statistics.",
        )


# ---------------------------------------------------------------------------
# 4. Individual Team Statistics
# ---------------------------------------------------------------------------

@router.get(
    "/{team_identifier}",
    response_model=TeamDetailStatsResponse,
    summary="Get individual team statistics",
    description="Returns detailed career match, batting, bowling, and championship statistics for a franchise by ID, name, short code, or alias.",
    responses={
        200: {"model": TeamDetailStatsResponse, "description": "Team statistics retrieved"},
        404: {"description": "Team not found"},
        400: {"description": "Ambiguous team name or invalid identifier"},
        500: {"description": "Database or server error"},
    },
)
@router.get(
    "/{team_identifier}/statistics",
    response_model=TeamDetailStatsResponse,
    include_in_schema=False,
)
def individual_team_statistics(
    team_identifier: str = Path(..., description="Franchise ID, canonical name, short code, or alias"),
) -> TeamDetailStatsResponse:
    """Retrieve comprehensive career statistics for one IPL team."""
    ident = team_identifier.strip() if team_identifier else ""
    if not ident:
        raise HTTPException(status_code=400, detail="Team identifier cannot be empty.")

    try:
        stats = get_individual_team_statistics(ident)
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"Team '{team_identifier}' was not found.",
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
            detail="Unable to retrieve individual team statistics.",
        )

