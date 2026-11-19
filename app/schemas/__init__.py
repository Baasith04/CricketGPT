"""
CricketGPT — Pydantic Schemas

This package defines data validation, request parsing, and response serialization
models for the REST API and internal service boundaries.
"""

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.matches import (
    BatterScorecard,
    BowlerScorecard,
    ExtrasScorecard,
    InningsScorecard,
    InningsWickets,
    MatchDetailResponse,
    MatchResultInfo,
    MatchScorecardResponse,
    MatchTeamInfo,
    MatchTossInfo,
    MatchWicketsResponse,
    WicketDetail,
)
from app.schemas.players import (
    PlayerBattingStatsResponse,
    PlayerBowlingStatsResponse,
)
from app.schemas.rag import (
    RagDirectoryIngestRequest,
    RagIngestRequest,
    RagIngestResponse,
    RagMatchSummariesIngestRequest,
    RagSearchChunk,
    RagSearchResponse,
)
from app.schemas.teams import (
    SeasonChampionshipResponse,
    TeamDetailStatsResponse,
    TeamHeadToHeadResponse,
    TeamOverallStatsResponse,
)

__all__ = [
    "BatterScorecard",
    "BowlerScorecard",
    "ChatRequest",
    "ChatResponse",
    "ExtrasScorecard",
    "InningsScorecard",
    "InningsWickets",
    "MatchDetailResponse",
    "MatchResultInfo",
    "MatchScorecardResponse",
    "MatchTeamInfo",
    "MatchTossInfo",
    "MatchWicketsResponse",
    "PlayerBattingStatsResponse",
    "PlayerBowlingStatsResponse",
    "SeasonChampionshipResponse",
    "TeamDetailStatsResponse",
    "TeamHeadToHeadResponse",
    "TeamOverallStatsResponse",
    "WicketDetail",
]
