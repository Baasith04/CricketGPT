# CricketGPT Evaluation Report (offline_mock)

## Summary Metrics

| Metric | Value |
|---|---:|
| Total questions evaluated | 28 |
| Correct | 13 |
| Partially correct | 0 |
| Incorrect | 0 |
| Appropriate refusals / clarifications | 5 |
| Pending ground-truth verification | 10 |
| Routing accuracy | 100.0% |
| Fact / SQL accuracy (verified cases) | 100.0% |
| RAG retrieval quality | 100.0% |
| Citation quality | 100.0% |
| Refusal accuracy | 100.0% |

## Category Breakdown

| Category | Total | Correct | Partial | Incorrect | Appropriate Refusal | Pending Verification |
|---|---:|---:|---:|---:|---:|---:|
| edge_case | 6 | 0 | 0 | 0 | 5 | 1 |
| historical | 7 | 3 | 0 | 0 | 0 | 4 |
| narrative | 3 | 3 | 0 | 0 | 0 | 0 |
| recent | 5 | 4 | 0 | 0 | 0 | 1 |
| statistics | 7 | 3 | 0 | 0 | 0 | 4 |

## Per-Case Results

| ID | Category | Route (Expected -> Actual) | Verdict | Notes / Failures |
|---|---|---|---|---|
| `hist_2008_champion` | historical | `sql_season_winner` -> `sql_season_winner` | **pending_verification** | Ground truth pending live database verification. |
| `hist_2008_rr_campaign` | historical | `gemini_historical` -> `gemini_historical` | **correct** | OK |
| `hist_2009_champion` | historical | `sql_season_winner` -> `sql_season_winner` | **correct** | OK |
| `hist_2011_final` | historical | `gemini_historical` -> `gemini_historical` | **pending_verification** | Ground truth pending live database verification. |
| `hist_2016_champion` | historical | `sql_season_winner` -> `sql_season_winner` | **correct** | OK |
| `hist_2020_final` | historical | `gemini_historical` -> `gemini_historical` | **pending_verification** | Ground truth pending live database verification. |
| `hist_2023_final` | historical | `sql_season_winner` -> `sql_season_winner` | **pending_verification** | Ground truth pending live database verification. |
| `recent_2024_champion` | recent | `sql_season_winner` -> `sql_season_winner` | **correct** | OK |
| `recent_2024_final_narrative` | recent | `rag_narrative` -> `rag_narrative` | **correct** | OK |
| `recent_2025_final` | recent | `rag_narrative` -> `rag_narrative` | **pending_verification** | Ground truth pending live database verification. |
| `recent_2026_final` | recent | `rag_narrative` -> `rag_narrative` | **correct** | OK |
| `recent_latest_season_overview` | recent | `post_cutoff_overview` -> `post_cutoff_overview` | **correct** | OK |
| `stat_kohli_2024_runs` | statistics | `sql_player_stats` -> `sql_player_stats` | **correct** | OK |
| `stat_2026_most_runs` | statistics | `sql_batting_leaderboard` -> `sql_batting_leaderboard` | **correct** | OK |
| `stat_most_wickets_alltime` | statistics | `sql_bowling_leaderboard` -> `sql_bowling_leaderboard` | **pending_verification** | Ground truth pending live database verification. |
| `stat_csk_2024_wins` | statistics | `sql_team_stats` -> `sql_team_stats` | **pending_verification** | Ground truth pending live database verification. |
| `stat_csk_mi_h2h` | statistics | `sql_head_to_head` -> `sql_head_to_head` | **pending_verification** | Ground truth pending live database verification. |
| `stat_kohli_2023_vs_2026` | statistics | `hybrid_player_multi_season` -> `hybrid_player_multi_season` | **correct** | OK |
| `stat_kohli_rohit_2024_sql_only` | statistics | `sql_player_comparison` -> `sql_player_comparison` | **pending_verification** | Ground truth pending live database verification. |
| `narr_csk_2024_hybrid` | narrative | `hybrid_team` -> `hybrid_team` | **correct** | OK |
| `narr_compare_2016_vs_2026` | narrative | `hybrid_cross_boundary` -> `hybrid_cross_boundary` | **correct** | OK |
| `narr_dls_rules` | narrative | `rag_narrative` -> `rag_narrative` | **correct** | OK |
| `edge_missing_season_2099` | edge_case | `sql_season_winner` -> `sql_season_winner` | **appropriate_refusal** | OK |
| `edge_unknown_player` | edge_case | `sql_player_stats` -> `sql_player_stats` | **appropriate_refusal** | OK |
| `edge_unsupported_non_ipl` | edge_case | `rag_narrative` -> `rag_narrative` | **appropriate_refusal** | OK |
| `edge_no_matching_rag_doc` | edge_case | `rag_narrative` -> `rag_narrative` | **appropriate_refusal** | OK |
| `edge_ambiguous_scorecard` | edge_case | `clarification` -> `clarification` | **appropriate_refusal** | OK |
| `edge_current_season_winner` | edge_case | `sql_season_winner` -> `sql_season_winner` | **pending_verification** | Ground truth pending live database verification. |
