"""
Execution tracing contracts for CricketGPT offline/mock evaluation.

NOTE ON PHASE 4 SCOPE:
Only `MockFixtureExecutor` is active in this offline phase so production router,
SQL, RAG, Gemini, and active backfill modules remain untouched.
`AbstractChatExecutor` defines the exact interface a future live executor will
implement after historical backfill completes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.evaluation.dataset import BenchmarkCase


class RagChunkTrace(BaseModel):
    """Metadata captured for one retrieved pgvector chunk."""

    doc_id: Optional[int] = None
    source_key: Optional[str] = None
    title: str = ""
    doc_type: Optional[str] = None
    season: Optional[str] = None
    match_id: Optional[int] = None
    hybrid_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    keyword_score: Optional[float] = None


class SqlEvidenceTrace(BaseModel):
    """Structured record of one SQL service query executed during a chat turn."""

    service_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0
    summary_facts: Dict[str, Any] = Field(default_factory=dict)


class ChatExecutionTrace(BaseModel):
    """Complete captured trace for one evaluated question."""

    case_id: str
    question: str
    mode: str = "mock"
    selected_route: Optional[str] = None
    cutoff_scope: Optional[str] = None
    seasons_extracted: List[str] = Field(default_factory=list)
    sql_evidence: List[SqlEvidenceTrace] = Field(default_factory=list)
    rag_chunks: List[RagChunkTrace] = Field(default_factory=list)
    llm_provider: Optional[str] = None
    answer: str = ""
    http_status: int = 200
    latency_ms: float = 0.0
    error: Optional[str] = None


class AbstractChatExecutor(ABC):
    """Base executor interface decoupled from production live modules."""

    @abstractmethod
    def execute(self, case: BenchmarkCase) -> ChatExecutionTrace:
        """Execute or replay one benchmark case and return its structured trace."""


class MockFixtureExecutor(AbstractChatExecutor):
    """
    Offline executor that replays pre-recorded or unit-test mock traces cleanly
    without touching Supabase, Gemini, or production router code.
    """

    def __init__(
        self,
        fixtures: Optional[Dict[str, ChatExecutionTrace]] = None,
    ) -> None:
        self._fixtures: Dict[str, ChatExecutionTrace] = dict(fixtures or {})

    def execute(self, case: BenchmarkCase) -> ChatExecutionTrace:
        if case.id in self._fixtures:
            return self._fixtures[case.id]

        # Deterministic offline placeholder trace preserving explicit pending state.
        return ChatExecutionTrace(
            case_id=case.id,
            question=case.question,
            mode="mock_unpopulated",
            selected_route=case.expected_route,
            cutoff_scope=case.expected_cutoff_scope,
            answer="",
            http_status=200,
            error="No mock fixture registered for this case.",
        )


def build_default_offline_fixtures() -> Dict[str, ChatExecutionTrace]:
    """
    Build representative offline/mock fixtures for local framework smoke checks.
    Unverified cases remain intentionally unpopulated so they stay `pending_verification`.
    """
    return {
        "hist_2008_rr_campaign": ChatExecutionTrace(
            case_id="hist_2008_rr_campaign",
            question="Explain Rajasthan Royals' 2008 campaign.",
            mode="mock",
            selected_route="gemini_historical",
            cutoff_scope="within_cutoff",
            seasons_extracted=["2007/08"],
            llm_provider="gemini",
            answer=(
                "Rajasthan Royals won the inaugural IPL 2008 trophy under captain-coach "
                "Shane Warne despite entering as heavy underdogs.\n\n"
                "### Sources\n"
                "- **[Gemini Historical Knowledge]** Answered directly within configured boundary."
            ),
        ),
        "hist_2009_champion": ChatExecutionTrace(
            case_id="hist_2009_champion",
            question="Who won IPL 2009?",
            mode="mock",
            selected_route="sql_season_winner",
            cutoff_scope="within_cutoff",
            seasons_extracted=["2009"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_season_winner",
                    parameters={"season": "2009"},
                    row_count=1,
                    summary_facts={"winner": "Deccan Chargers", "match_id": 392239},
                )
            ],
            answer=(
                "The IPL 2009 champion was **Deccan Chargers**.\n\n"
                "Final Match ID: 392239\n"
                "Final Date: 2009-05-24\n"
                "Source: CricketGPT historical IPL database (Supabase)."
            ),
        ),
        "hist_2016_champion": ChatExecutionTrace(
            case_id="hist_2016_champion",
            question="Who won IPL 2016?",
            mode="mock",
            selected_route="sql_season_winner",
            cutoff_scope="within_cutoff",
            seasons_extracted=["2016"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_season_winner",
                    parameters={"season": "2016"},
                    row_count=1,
                    summary_facts={"winner": "Sunrisers Hyderabad", "match_id": 981019},
                )
            ],
            answer=(
                "The IPL 2016 champion was **Sunrisers Hyderabad**.\n\n"
                "Final Match ID: 981019\n"
                "Final Date: 2016-05-29\n"
                "Source: CricketGPT historical IPL database (Supabase)."
            ),
        ),
        "recent_2024_champion": ChatExecutionTrace(
            case_id="recent_2024_champion",
            question="Who won IPL 2024?",
            mode="mock",
            selected_route="sql_season_winner",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2024"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_season_winner",
                    parameters={"season": "2024"},
                    row_count=1,
                    summary_facts={"winner": "Kolkata Knight Riders", "match_id": 1426312},
                )
            ],
            answer=(
                "The IPL 2024 champion was **Kolkata Knight Riders**.\n\n"
                "Final Match ID: 1426312\n"
                "Final Date: 2024-05-26\n"
                "Source: CricketGPT historical IPL database (Supabase)."
            ),
        ),
        "recent_2024_final_narrative": ChatExecutionTrace(
            case_id="recent_2024_final_narrative",
            question="Explain IPL 2024 final",
            mode="mock",
            selected_route="rag_narrative",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2024"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_season_winner",
                    parameters={"season": "2024"},
                    row_count=1,
                    summary_facts={"winner": "Kolkata Knight Riders"},
                )
            ],
            rag_chunks=[
                RagChunkTrace(
                    doc_id=3,
                    source_key="db:match:1426312",
                    title="IPL 2024 Final Match Report: Sunrisers Hyderabad vs Kolkata Knight Riders",
                    doc_type="match_report",
                    season="2024",
                    match_id=1426312,
                    hybrid_score=0.61,
                )
            ],
            llm_provider="gemini",
            answer=(
                "Kolkata Knight Riders defeated Sunrisers Hyderabad by 8 wickets in the "
                "IPL 2024 Final on 2024-05-26 [S1].\n\n"
                "### Sources\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[S1] IPL 2024 Final Match Report**"
            ),
        ),
        "recent_2026_final": ChatExecutionTrace(
            case_id="recent_2026_final",
            question="Explain the IPL 2026 final.",
            mode="mock",
            selected_route="rag_narrative",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2026"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_match_scorecard",
                    parameters={"match_id": 1535465},
                    row_count=2,
                    summary_facts={"winner": "Royal Challengers Bengaluru", "win_by_wickets": 5},
                )
            ],
            rag_chunks=[
                RagChunkTrace(
                    doc_id=19,
                    source_key="db:match:1535465",
                    title="IPL 2026 Final Match Report: Gujarat Titans vs Royal Challengers Bengaluru",
                    doc_type="match_report",
                    season="2026",
                    match_id=1535465,
                    hybrid_score=0.84,
                )
            ],
            llm_provider="gemini",
            answer=(
                "In the IPL 2026 Final [SQL][S1], Gujarat Titans posted 155/8 before "
                "Royal Challengers Bengaluru chased 161/5 to win by 5 wickets, with "
                "V Kohli named Player of the Match.\n\n"
                "### Sources\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[S1] IPL 2026 Final Match Report: Gujarat Titans vs Royal Challengers Bengaluru**"
            ),
        ),
        "recent_latest_season_overview": ChatExecutionTrace(
            case_id="recent_latest_season_overview",
            question="What happened in the latest IPL season?",
            mode="mock",
            selected_route="post_cutoff_overview",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2026"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_batting_leaderboard",
                    parameters={"season": "2026"},
                    row_count=5,
                )
            ],
            rag_chunks=[
                RagChunkTrace(
                    doc_id=19,
                    source_key="db:match:1535465",
                    title="IPL 2026 Final Match Report: Gujarat Titans vs Royal Challengers Bengaluru",
                    doc_type="match_report",
                    season="2026",
                    match_id=1535465,
                    hybrid_score=0.72,
                )
            ],
            llm_provider="gemini",
            answer=(
                "Royal Challengers Bengaluru won the 2026 IPL season [SQL], while "
                "V Suryavanshi topped the run charts with 776 runs [SQL][S1].\n\n"
                "### Sources\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[S1] IPL 2026 Final Match Report**"
            ),
        ),
        "stat_kohli_2024_runs": ChatExecutionTrace(
            case_id="stat_kohli_2024_runs",
            question="How many runs did Virat Kohli score in 2024?",
            mode="mock",
            selected_route="sql_player_stats",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2024"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_player_batting_stats",
                    parameters={"player": "Virat Kohli", "season": "2024"},
                    row_count=1,
                    summary_facts={"total_runs": 741, "matches_played": 15},
                )
            ],
            answer=(
                "## IPL 2024 Statistics — V Kohli\n"
                "| Matches | 15 |\n| Runs | 741 |\n"
                "Source: CricketGPT historical IPL statistics database (Supabase)."
            ),
        ),
        "stat_2026_most_runs": ChatExecutionTrace(
            case_id="stat_2026_most_runs",
            question="Who scored the most runs in IPL 2026?",
            mode="mock",
            selected_route="sql_batting_leaderboard",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2026"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_batting_leaderboard",
                    parameters={"season": "2026", "category": "runs"},
                    row_count=10,
                )
            ],
            answer=(
                "**IPL Batting Leaderboard - IPL 2026**\n"
                "1 | V Suryavanshi | 776 | 16\n"
                "2 | Shubman Gill | 732 | 16\n"
                "Source: CricketGPT historical IPL statistics database (Supabase)."
            ),
        ),
        "stat_kohli_2023_vs_2026": ChatExecutionTrace(
            case_id="stat_kohli_2023_vs_2026",
            question="Compare Kohli's performance in 2023 and 2026.",
            mode="mock",
            selected_route="hybrid_player_multi_season",
            cutoff_scope="cross_cutoff",
            seasons_extracted=["2023", "2026"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_player_batting_stats",
                    parameters={"player": "Kohli", "seasons": ["2023", "2026"]},
                    row_count=2,
                )
            ],
            llm_provider="gemini",
            answer=(
                "V Kohli scored 639 runs in IPL 2023 [SQL] and 675 runs in IPL 2026 [SQL].\n\n"
                "### Sources\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[Gemini Historical Knowledge]** Pre-boundary context"
            ),
        ),
        "narr_csk_2024_hybrid": ChatExecutionTrace(
            case_id="narr_csk_2024_hybrid",
            question="Explain CSK's 2024 performance using match statistics",
            mode="mock",
            selected_route="hybrid_team",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2024"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_individual_team_statistics",
                    parameters={"team": "csk", "season": "2024"},
                    row_count=1,
                )
            ],
            rag_chunks=[
                RagChunkTrace(
                    doc_id=2,
                    source_key="file:summaries/ipl_2024_narrative.md",
                    title="IPL 2024 Tournament Narrative",
                    doc_type="season_summary",
                    season="2024",
                    hybrid_score=0.58,
                )
            ],
            llm_provider="gemini",
            answer=(
                "Chennai Super Kings transitioned leadership to Ruturaj Gaikwad in IPL 2024 [SQL][S1].\n\n"
                "### Sources\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[S1] IPL 2024 Tournament Narrative**"
            ),
        ),
        "narr_compare_2016_vs_2026": ChatExecutionTrace(
            case_id="narr_compare_2016_vs_2026",
            question="Compare IPL 2016 and IPL 2026.",
            mode="mock",
            selected_route="hybrid_cross_boundary",
            cutoff_scope="cross_cutoff",
            seasons_extracted=["2016", "2026"],
            sql_evidence=[
                SqlEvidenceTrace(
                    service_name="get_season_winner",
                    parameters={"seasons": ["2016", "2026"]},
                    row_count=2,
                )
            ],
            rag_chunks=[
                RagChunkTrace(
                    doc_id=19,
                    source_key="db:match:1535465",
                    title="IPL 2026 Final Match Report",
                    doc_type="match_report",
                    season="2026",
                    match_id=1535465,
                    hybrid_score=0.71,
                )
            ],
            llm_provider="gemini",
            answer=(
                "Sunrisers Hyderabad won IPL 2016 [Gemini Historical Knowledge][SQL], "
                "whereas Royal Challengers Bengaluru won IPL 2026 [SQL][S1].\n\n"
                "### Sources\n"
                "- **[Gemini Historical Knowledge]** Historical context\n"
                "- **[SQL]** CricketGPT PostgreSQL / Supabase\n"
                "- **[S1] IPL 2026 Final Match Report**"
            ),
        ),
        "narr_dls_rules": ChatExecutionTrace(
            case_id="narr_dls_rules",
            question="Explain DLS rules",
            mode="mock",
            selected_route="rag_narrative",
            cutoff_scope="ambiguous",
            rag_chunks=[
                RagChunkTrace(
                    doc_id=1,
                    source_key="file:rules/dls_and_ipl_playing_conditions.md",
                    title="Duckworth-Lewis-Stern (DLS) Method and IPL Playing Conditions",
                    doc_type="cricket_rule",
                    hybrid_score=0.82,
                )
            ],
            llm_provider="gemini",
            answer=(
                "The Duckworth-Lewis-Stern (DLS) method calculates revised target scores in rain-shortened matches [S1].\n\n"
                "### Sources\n"
                "- **[S1] Duckworth-Lewis-Stern (DLS) Method and IPL Playing Conditions**"
            ),
        ),
        "edge_missing_season_2099": ChatExecutionTrace(
            case_id="edge_missing_season_2099",
            question="Who won IPL 2099?",
            mode="mock",
            selected_route="sql_season_winner",
            cutoff_scope="post_cutoff",
            seasons_extracted=["2099"],
            sql_evidence=[
                SqlEvidenceTrace(service_name="get_season_winner", parameters={"season": "2099"}, row_count=0)
            ],
            answer="No IPL final match record was found for season 2099.",
        ),
        "edge_unknown_player": ChatExecutionTrace(
            case_id="edge_unknown_player",
            question="How many runs did Unknown Player XYZ score in IPL?",
            mode="mock",
            selected_route="sql_player_stats",
            cutoff_scope="ambiguous",
            sql_evidence=[
                SqlEvidenceTrace(service_name="get_player_batting_stats", parameters={"player": "Unknown Player XYZ"}, row_count=0)
            ],
            answer="No IPL statistics found for player matching 'Unknown Player XYZ'.",
        ),
        "edge_unsupported_non_ipl": ChatExecutionTrace(
            case_id="edge_unsupported_non_ipl",
            question="Who won the 2022 FIFA World Cup?",
            mode="mock",
            selected_route="rag_narrative",
            cutoff_scope="within_cutoff",
            rag_chunks=[],
            answer=(
                "I could not find relevant documents in the CricketGPT knowledge base "
                "to answer this question accurately."
            ),
        ),
        "edge_no_matching_rag_doc": ChatExecutionTrace(
            case_id="edge_no_matching_rag_doc",
            question="Explain fictional super-mega-over rule XYZ999 in IPL",
            mode="mock",
            selected_route="rag_narrative",
            cutoff_scope="ambiguous",
            rag_chunks=[],
            answer=(
                "I could not find relevant documents in the CricketGPT knowledge base "
                "to answer this question accurately."
            ),
        ),
        "edge_ambiguous_scorecard": ChatExecutionTrace(
            case_id="edge_ambiguous_scorecard",
            question="Show the scorecard.",
            mode="mock",
            selected_route="clarification",
            cutoff_scope="ambiguous",
            answer="Please specify a match ID or date and teams to retrieve match details.",
        ),
    }

