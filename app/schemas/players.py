from typing import Optional
from pydantic import BaseModel, Field


class PlayerBattingStatsResponse(BaseModel):
    """Pydantic model representing career batting statistics for an IPL player."""

    player_id: str = Field(..., description="Unique player identifier (Cricsheet registry ID)")
    player_name: str = Field(..., description="Canonical player name")
    innings: int = Field(..., description="Number of innings batted")
    matches: int = Field(..., description="Number of matches played")
    total_runs: int = Field(..., description="Total career runs scored")
    not_outs: int = Field(..., description="Number of times not out")
    batting_average: Optional[float] = Field(default=None, description="Batting average (runs per dismissal)")
    balls_faced: int = Field(..., description="Total legal balls faced (excludes wides)")
    strike_rate: Optional[float] = Field(default=None, description="Batting strike rate (runs per 100 balls)")
    fours: int = Field(..., description="Total boundaries (fours) hit")
    sixes: int = Field(..., description="Total sixes hit")
    fifties: int = Field(..., description="Number of half-centuries scored (50-99 runs)")
    hundreds: int = Field(..., description="Number of centuries scored (100+ runs)")
    highest_score: Optional[int] = Field(default=None, description="Highest score in an individual innings")

    model_config = {
        "json_schema_extra": {
            "example": {
                "player_id": "ba607b88",
                "player_name": "V Kohli",
                "innings": 275,
                "matches": 275,
                "total_runs": 9336,
                "not_outs": 46,
                "batting_average": 40.77,
                "balls_faced": 6926,
                "strike_rate": 134.80,
                "fours": 845,
                "sixes": 317,
                "fifties": 68,
                "hundreds": 9,
                "highest_score": 113,
            }
        }
    }


class PlayerBowlingStatsResponse(BaseModel):
    """Pydantic model representing career bowling statistics for an IPL player."""

    player_id: str = Field(..., description="Unique player identifier (Cricsheet registry ID)")
    player_name: str = Field(..., description="Canonical player name")
    innings: int = Field(..., description="Number of innings bowled")
    matches: int = Field(..., description="Number of matches played")
    legal_balls: int = Field(..., description="Total legal balls bowled")
    overs: float = Field(..., description="Total overs bowled (calculated as legal_balls / 6)")
    maidens: int = Field(..., description="Total complete maiden overs bowled")
    runs_conceded: int = Field(..., description="Total runs conceded off bowler (excludes byes/leg-byes/penalties)")
    wickets: int = Field(..., description="Total wickets credited to bowler")
    economy: Optional[float] = Field(default=None, description="Bowling economy rate (runs per over)")
    bowling_average: Optional[float] = Field(default=None, description="Bowling average (runs per wicket)")
    bowling_strike_rate: Optional[float] = Field(default=None, description="Bowling strike rate (balls per wicket)")
    best_bowling: Optional[str] = Field(default=None, description="Best bowling figures in an innings (W/R format)")
    best_bowling_figures: Optional[str] = Field(default=None, description="Alias for best bowling figures (W/R format)")
    best_innings_wickets: Optional[int] = Field(default=None, description="Most wickets taken in a single innings")

    model_config = {
        "json_schema_extra": {
            "example": {
                "player_id": "a12e1d51",
                "player_name": "SL Malinga",
                "innings": 122,
                "matches": 122,
                "legal_balls": 2827,
                "overs": 471.2,
                "maidens": 8,
                "runs_conceded": 3366,
                "wickets": 170,
                "economy": 7.14,
                "bowling_average": 19.80,
                "bowling_strike_rate": 16.63,
                "best_bowling": "5/13",
                "best_bowling_figures": "5/13",
                "best_innings_wickets": 5,
            }
        }
    }

