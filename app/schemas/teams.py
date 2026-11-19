from datetime import date
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class TeamOverallStatsResponse(BaseModel):
    """Pydantic model representing overall statistics for an IPL franchise."""

    team_id: int = Field(..., description="Unique team identifier")
    team_name: str = Field(..., description="Canonical franchise name")
    short_code: str = Field(..., description="Standard abbreviation (e.g. MI, CSK, RCB)")
    is_active: bool = Field(..., description="Whether the franchise is active or defunct")
    matches_played: int = Field(..., description="Total matches played in IPL history")
    wins: int = Field(..., description="Total matches won")
    losses: int = Field(..., description="Total matches lost")
    ties: int = Field(..., description="Total matches tied (including matches decided by Super Over)")
    no_results: int = Field(..., description="Total abandoned or rain-affected no-result matches")
    win_percentage: float = Field(..., description="Win percentage (wins / matches_played * 100)")
    championship_titles: int = Field(..., description="Total IPL championship titles won")

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": 10,
                "team_name": "Mumbai Indians",
                "short_code": "MI",
                "is_active": True,
                "matches_played": 291,
                "wins": 155,
                "losses": 132,
                "ties": 4,
                "no_results": 0,
                "win_percentage": 53.26,
                "championship_titles": 5,
            }
        }
    }


class TeamDetailStatsResponse(BaseModel):
    """Pydantic model representing detailed batting, bowling, and match statistics for a franchise."""

    team_id: int = Field(..., description="Unique team identifier")
    team_name: str = Field(..., description="Canonical franchise name")
    short_code: str = Field(..., description="Standard abbreviation")
    is_active: bool = Field(..., description="Whether the franchise is active or defunct")
    matches_played: int = Field(..., description="Total matches played")
    wins: int = Field(..., description="Total matches won")
    losses: int = Field(..., description="Total matches lost")
    ties: int = Field(..., description="Total matches tied")
    no_results: int = Field(..., description="Total no-result matches")
    win_percentage: float = Field(..., description="Win percentage")
    innings_batted: int = Field(..., description="Total innings batted (excludes Super Overs)")
    runs_scored: int = Field(..., description="Total runs scored (excludes Super Overs)")
    wickets_lost: int = Field(..., description="Total wickets lost (excludes Super Overs)")
    legal_balls_faced: int = Field(..., description="Total legal balls faced (excludes Super Overs)")
    batting_run_rate: float = Field(..., description="Batting run rate (runs * 6 / legal balls faced)")
    innings_bowled: int = Field(..., description="Total innings bowled (excludes Super Overs)")
    runs_conceded: int = Field(..., description="Total runs conceded (excludes Super Overs)")
    wickets_taken: int = Field(..., description="Total wickets taken (excludes Super Overs)")
    legal_balls_bowled: int = Field(..., description="Total legal balls bowled (excludes Super Overs)")
    bowling_economy: float = Field(..., description="Bowling economy rate (runs conceded * 6 / legal balls bowled)")
    championship_titles: int = Field(..., description="Total IPL titles won")
    championship_seasons: List[str] = Field(default_factory=list, description="Seasons in which titles were won")

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": 1,
                "team_name": "Chennai Super Kings",
                "short_code": "CSK",
                "is_active": True,
                "matches_played": 266,
                "wins": 148,
                "losses": 116,
                "ties": 1,
                "no_results": 1,
                "win_percentage": 55.64,
                "innings_batted": 265,
                "runs_scored": 43591,
                "wickets_lost": 1421,
                "legal_balls_faced": 30893,
                "batting_run_rate": 8.47,
                "innings_bowled": 266,
                "runs_conceded": 42170,
                "wickets_taken": 1644,
                "legal_balls_bowled": 30659,
                "bowling_economy": 8.25,
                "championship_titles": 5,
                "championship_seasons": ["2009/10", "2011", "2018", "2021", "2023"],
            }
        }
    }


class TeamHeadToHeadResponse(BaseModel):
    """Pydantic model representing head-to-head match statistics between two franchises."""

    team_one: str = Field(..., description="Canonical name of first team")
    team_two: str = Field(..., description="Canonical name of second team")
    matches_played: int = Field(..., description="Total matches played between the two teams")
    team_one_wins: int = Field(..., description="Matches won by team one")
    team_two_wins: int = Field(..., description="Matches won by team two")
    ties: int = Field(..., description="Matches tied between the two teams")
    no_results: int = Field(..., description="Matches abandoned or no result")

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_one": "Mumbai Indians",
                "team_two": "Chennai Super Kings",
                "matches_played": 41,
                "team_one_wins": 21,
                "team_two_wins": 20,
                "ties": 0,
                "no_results": 0,
            }
        }
    }


class SeasonChampionshipResponse(BaseModel):
    """Pydantic model representing an IPL season championship winner."""

    season: str = Field(..., description="IPL season string (e.g. '2024', '2007/08')")
    match_id: int = Field(..., description="Match ID of the final match")
    match_date: Union[date, str] = Field(..., description="Date the final was played")
    team_id: Optional[int] = Field(default=None, description="Winner franchise ID")
    winner: str = Field(..., description="Canonical franchise name of the champion")

    model_config = {
        "json_schema_extra": {
            "example": {
                "season": "2024",
                "match_id": 1426312,
                "match_date": "2024-05-26",
                "team_id": 8,
                "winner": "Kolkata Knight Riders",
            }
        }
    }

