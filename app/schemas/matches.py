from datetime import date
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class MatchTeamInfo(BaseModel):
    """Pydantic model representing a team's participation in a match."""

    team_id: int = Field(..., description="Unique team identifier")
    team_name: str = Field(..., description="Canonical franchise name")
    short_code: str = Field(..., description="Standard abbreviation (e.g. RCB, KKR)")
    team_number: int = Field(..., description="Designated team 1 or team 2")
    original_team_name: str = Field(..., description="Original team name on match day")


class MatchTossInfo(BaseModel):
    """Pydantic model representing toss details."""

    toss_winner_id: Optional[int] = Field(default=None, description="Toss winning team ID")
    toss_winner_name: Optional[str] = Field(default=None, description="Toss winning team name")
    toss_decision: Optional[str] = Field(default=None, description="Elected to bat or field")


class MatchResultInfo(BaseModel):
    """Pydantic model representing the outcome of a match."""

    result_type: str = Field(..., description="Result type (runs, wickets, tie, no result, eliminator)")
    result_method: Optional[str] = Field(default=None, description="Result method (e.g. D/L)")
    winner_id: Optional[int] = Field(default=None, description="Match winning team ID")
    winner_name: Optional[str] = Field(default=None, description="Match winning team name")
    win_by_runs: Optional[int] = Field(default=None, description="Margin of victory in runs")
    win_by_wickets: Optional[int] = Field(default=None, description="Margin of victory in wickets")
    is_super_over: bool = Field(default=False, description="Whether match was decided by Super Over")
    summary: str = Field(..., description="Human-readable result summary")


class MatchDetailResponse(BaseModel):
    """Pydantic model representing complete match metadata and outcome."""

    match_id: int = Field(..., description="Cricsheet match identifier")
    season: str = Field(..., description="IPL season string (e.g. 2007/08, 2024)")
    match_date: Union[date, str] = Field(..., description="Match start date")
    venue: str = Field(..., description="Stadium / ground name")
    city: Optional[str] = Field(default=None, description="Host city")
    stage: Optional[str] = Field(default=None, description="Tournament stage (e.g. Final, League)")
    teams: List[MatchTeamInfo] = Field(default_factory=list, description="Participating teams")
    toss: MatchTossInfo = Field(..., description="Toss outcome")
    result: MatchResultInfo = Field(..., description="Match result")


class BatterScorecard(BaseModel):
    """Pydantic model representing a batter's individual performance in an innings."""

    player_id: str = Field(..., description="Cricsheet player identifier")
    player_name: str = Field(..., description="Batter canonical or match name")
    runs: int = Field(..., description="Runs scored by the batter")
    balls: int = Field(..., description="Balls faced (excluding wides)")
    fours: int = Field(..., description="Boundary fours hit")
    sixes: int = Field(..., description="Sixes hit")
    strike_rate: float = Field(..., description="Batting strike rate (runs * 100 / balls)")
    is_out: bool = Field(..., description="Whether the batter was dismissed")
    dismissal: Optional[str] = Field(default=None, description="Dismissal description (e.g. 'c Fielder b Bowler' or 'not out')")


class BowlerScorecard(BaseModel):
    """Pydantic model representing a bowler's individual figures in an innings."""

    player_id: str = Field(..., description="Cricsheet player identifier")
    player_name: str = Field(..., description="Bowler canonical or match name")
    overs: str = Field(..., description="Overs bowled (e.g. '4.0', '3.2')")
    legal_balls: int = Field(..., description="Total legal deliveries bowled")
    maidens: int = Field(..., description="Complete maiden overs bowled")
    runs_conceded: int = Field(..., description="Runs conceded off the bowler")
    wickets: int = Field(..., description="Wickets credited to the bowler")
    economy: float = Field(..., description="Bowling economy rate (runs per over)")
    wides: int = Field(default=0, description="Wide balls bowled")
    no_balls: int = Field(default=0, description="No-balls bowled")


class ExtrasScorecard(BaseModel):
    """Pydantic model representing extras conceded in an innings."""

    wides: int = Field(..., description="Wide runs")
    no_balls: int = Field(..., description="No-ball runs")
    byes: int = Field(..., description="Bye runs")
    leg_byes: int = Field(..., description="Leg-bye runs")
    penalty: int = Field(..., description="Penalty runs")
    total_extras: int = Field(..., description="Total extra runs")


class InningsScorecard(BaseModel):
    """Pydantic model representing a complete innings scorecard."""

    innings_id: int = Field(..., description="Unique innings identifier")
    innings_number: int = Field(..., description="Innings sequence number in the match")
    batting_team_id: int = Field(..., description="Batting team identifier")
    batting_team: str = Field(..., description="Batting team canonical name")
    bowling_team_id: int = Field(..., description="Bowling team identifier")
    bowling_team: str = Field(..., description="Bowling team canonical name")
    total_runs: int = Field(..., description="Total runs scored in the innings")
    total_wickets: int = Field(..., description="Total wickets lost in the innings")
    legal_balls_bowled: int = Field(..., description="Total legal balls bowled in the innings")
    overs: str = Field(..., description="Formatted overs bowled (e.g. '20.0', '15.1')")
    run_rate: float = Field(..., description="Run rate (runs * 6 / legal balls)")
    is_super_over: bool = Field(default=False, description="Whether this was a Super Over innings")
    target_runs: Optional[int] = Field(default=None, description="Target score if second innings")
    batting: List[BatterScorecard] = Field(default_factory=list, description="Batting scorecard")
    bowling: List[BowlerScorecard] = Field(default_factory=list, description="Bowling figures")
    extras: ExtrasScorecard = Field(..., description="Extras breakdown")


class MatchScorecardResponse(BaseModel):
    """Pydantic model representing the full match scorecard."""

    match: MatchDetailResponse = Field(..., description="Match metadata and outcome")
    has_super_over: bool = Field(default=False, description="Whether the match had Super Overs")
    innings: List[InningsScorecard] = Field(default_factory=list, description="Regular match innings")
    super_overs: List[InningsScorecard] = Field(default_factory=list, description="Super Over innings (if any)")


class WicketDetail(BaseModel):
    """Pydantic model representing an individual fall of wicket."""

    wicket_number: int = Field(..., description="Wicket sequence number in the innings (1st, 2nd...)")
    player_id: str = Field(..., description="Dismissed batter ID")
    player_name: str = Field(..., description="Dismissed batter name")
    dismissal_kind: str = Field(..., description="Dismissal kind (caught, bowled, lbw, run out...)")
    bowler_id: Optional[str] = Field(default=None, description="Bowler ID")
    bowler_name: Optional[str] = Field(default=None, description="Bowler name")
    fielders: List[str] = Field(default_factory=list, description="Fielder names involved")
    score: int = Field(..., description="Team cumulative runs at the fall of wicket")
    overs: str = Field(..., description="Formatted overs at fall of wicket (e.g. '5.2')")
    over_number: int = Field(..., description="Zero-indexed over number")
    delivery_sequence: int = Field(..., description="Delivery sequence within the over")


class InningsWickets(BaseModel):
    """Pydantic model representing fall of wickets for an innings."""

    innings_id: int = Field(..., description="Innings identifier")
    innings_number: int = Field(..., description="Innings number in match")
    batting_team_id: int = Field(..., description="Batting team identifier")
    batting_team: str = Field(..., description="Batting team canonical name")
    is_super_over: bool = Field(default=False, description="Whether this was a Super Over")
    total_runs: int = Field(..., description="Total runs in innings")
    total_wickets: int = Field(..., description="Total wickets lost in innings")
    fall_of_wickets: List[WicketDetail] = Field(default_factory=list, description="Chronological fall of wickets")


class MatchWicketsResponse(BaseModel):
    """Pydantic model representing all fall-of-wickets for a match."""

    match_id: int = Field(..., description="Match identifier")
    has_super_over: bool = Field(default=False, description="Whether match had a Super Over")
    innings: List[InningsWickets] = Field(default_factory=list, description="Regular innings wickets breakdown")
    super_overs: List[InningsWickets] = Field(default_factory=list, description="Super Over wickets breakdown (if any)")

