"""Unit tests for the independent Phase 4 offline evaluation framework."""

from pathlib import Path

from app.evaluation.dataset import BenchmarkCase, filter_benchmark_cases, load_benchmark_dataset
from app.evaluation.scorer import (
    evaluate_case,
    evaluate_dataset,
    render_markdown_report,
    save_evaluation_reports,
    summarize_evaluations,
)
from app.evaluation.tracer import (
    ChatExecutionTrace,
    MockFixtureExecutor,
    RagChunkTrace,
    SqlEvidenceTrace,
    build_default_offline_fixtures,
)


def _sample_case(**overrides) -> BenchmarkCase:
    defaults = {
        "id": "case_1",
        "category": "statistics",
        "question": "How many runs did Virat Kohli score in 2024?",
        "expected_route": "sql_player_stats",
        "expected_cutoff_scope": "post_cutoff",
        "requires_sql": True,
        "requires_rag": False,
        "must_refuse_or_clarify": False,
        "expected_citations": ["Source: CricketGPT"],
        "required_facts": ["V Kohli"],
        "required_numbers": ["741", "15"],
        "forbidden_patterns": [],
        "ground_truth_status": "verified",
    }
    defaults.update(overrides)
    return BenchmarkCase(**defaults)


def test_benchmark_dataset_loads_all_categories_cleanly():
    cases = load_benchmark_dataset()
    assert len(cases) >= 26
    categories = {c.category for c in cases}
    assert categories == {"historical", "recent", "statistics", "narrative", "edge_case"}
    assert any(c.ground_truth_status == "pending_verification" for c in cases)
    assert any(c.ground_truth_status == "verified" for c in cases)

    hist_only = filter_benchmark_cases(cases, categories=["historical"])
    assert all(c.category == "historical" for c in hist_only)
    verified_only = filter_benchmark_cases(cases, verified_only=True)
    assert all(c.ground_truth_status == "verified" for c in verified_only)


def test_evaluate_case_correct_outcome():
    case = _sample_case()
    trace = ChatExecutionTrace(
        case_id="case_1",
        question=case.question,
        selected_route="sql_player_stats",
        cutoff_scope="post_cutoff",
        sql_evidence=[SqlEvidenceTrace(service_name="get_player_batting_stats", row_count=1)],
        answer="V Kohli scored 741 runs in 15 matches.\nSource: CricketGPT historical database.",
    )
    res = evaluate_case(case, trace)
    assert res.verdict == "correct"
    assert res.route_ok is True
    assert res.facts_ok is True
    assert res.citation_ok is True
    assert res.failure_reasons == []


def test_evaluate_case_partial_outcome_on_missing_citation_or_phantom_chunk():
    case = _sample_case(
        id="rag_partial",
        category="recent",
        expected_route="rag_narrative",
        requires_rag=True,
        expected_rag_season="2026",
        expected_citations=["[SQL]", "[S1]"],
        required_facts=["Royal Challengers Bengaluru"],
        required_numbers=["161"],
    )
    trace = ChatExecutionTrace(
        case_id="rag_partial",
        question=case.question,
        selected_route="rag_narrative",
        cutoff_scope="post_cutoff",
        rag_chunks=[RagChunkTrace(doc_id=19, season="2026", match_id=1535465)],
        answer="Royal Challengers Bengaluru scored 161/5 [SQL] and [S3].",
    )
    res = evaluate_case(case, trace)
    assert res.verdict == "partial"
    assert res.facts_ok is True
    assert res.citation_ok is False
    assert 3 in res.citations.phantom_rag_indices


def test_evaluate_case_incorrect_outcome_on_wrong_facts_or_hallucination():
    case = _sample_case(forbidden_patterns=["Punjab Kings"])
    trace = ChatExecutionTrace(
        case_id="case_1",
        question=case.question,
        selected_route="sql_player_stats",
        cutoff_scope="post_cutoff",
        answer="Punjab Kings player V Kohli scored 500 runs.\nSource: CricketGPT",
    )
    res = evaluate_case(case, trace)
    assert res.verdict == "incorrect"
    assert res.facts_ok is False
    assert res.forbidden_ok is False
    assert "741" in res.missing_numbers


def test_evaluate_case_appropriate_refusal_and_missed_refusal():
    refusal_case = _sample_case(
        id="edge_refuse",
        category="edge_case",
        question="Explain fictional super-mega-over rule XYZ999 in IPL",
        expected_route="rag_narrative",
        expected_cutoff_scope="ambiguous",
        requires_sql=False,
        requires_rag=True,
        must_refuse_or_clarify=True,
        expected_citations=[],
        required_facts=[],
        required_numbers=[],
        forbidden_patterns=["10 runs"],
    )
    good_trace = ChatExecutionTrace(
        case_id="edge_refuse",
        question=refusal_case.question,
        selected_route="rag_narrative",
        cutoff_scope="ambiguous",
        rag_chunks=[],
        answer="I could not find relevant documents in the CricketGPT knowledge base.",
    )
    res_good = evaluate_case(refusal_case, good_trace)
    assert res_good.verdict == "appropriate_refusal"
    assert res_good.refusal_ok is True

    hallucinated_trace = ChatExecutionTrace(
        case_id="edge_refuse",
        question=refusal_case.question,
        selected_route="rag_narrative",
        cutoff_scope="ambiguous",
        rag_chunks=[],
        answer="This rule grants 10 runs automatically.",
    )
    res_bad = evaluate_case(refusal_case, hallucinated_trace)
    assert res_bad.verdict == "incorrect"
    assert res_bad.refusal_ok is False


def test_evaluate_case_pending_verification_never_marked_correct():
    pending_case = _sample_case(
        id="pending_1",
        ground_truth_status="pending_verification",
        required_facts=[],
        required_numbers=[],
    )
    trace = ChatExecutionTrace(
        case_id="pending_1",
        question=pending_case.question,
        selected_route="sql_player_stats",
        cutoff_scope="post_cutoff",
        answer="Some unverified response",
    )
    res = evaluate_case(pending_case, trace)
    assert res.verdict == "pending_verification"

    err_trace = ChatExecutionTrace(
        case_id="pending_1",
        question=pending_case.question,
        selected_route="sql_player_stats",
        http_status=500,
        error="Internal error",
    )
    res_err = evaluate_case(pending_case, err_trace)
    assert res_err.verdict == "incorrect"


def test_full_offline_mock_dataset_evaluation_and_report_generation(tmp_path: Path):
    cases = load_benchmark_dataset()
    executor = MockFixtureExecutor(build_default_offline_fixtures())
    output = evaluate_dataset(cases, executor)
    summary = output["summary"]
    results = output["results"]

    assert summary.total_cases == len(cases)
    assert summary.incorrect == 0
    assert summary.correct > 0
    assert summary.appropriate_refusals >= 5
    assert summary.pending_verification >= 1
    assert summary.routing_accuracy == 1.0
    assert summary.sql_fact_accuracy == 1.0

    written = save_evaluation_reports(summary, results, tmp_path, mode_label="offline_mock")
    assert written["json"].is_file()
    assert written["markdown"].is_file()
    md_text = written["markdown"].read_text(encoding="utf-8")
    assert "CricketGPT Evaluation Report (offline_mock)" in md_text
    assert "Pending ground-truth verification" in md_text

