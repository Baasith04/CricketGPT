"""
Deterministic offline/live answer evaluation scorer and report generator.

Evaluates:
- Route selection & cutoff classification accuracy
- Required SQL/factual & numeric exactness
- RAG chunk retrieval relevance
- Citation hygiene (presence of expected tags + zero phantom [S#] citations)
- Grounded refusal / clarification handling
- Explicit `pending_verification` separation (never guesses unverified answers)
"""

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.evaluation.dataset import BenchmarkCase
from app.evaluation.tracer import AbstractChatExecutor, ChatExecutionTrace

VerdictLiteral = Literal[
    "correct",
    "partial",
    "incorrect",
    "appropriate_refusal",
    "pending_verification",
]

_REFUSAL_OR_CLARIFY_PATTERNS = (
    "could not find",
    "no ipl final match record",
    "no ipl statistics found",
    "no database record",
    "no leaderboard records",
    "no head-to-head records",
    "please specify",
    "unavailable",
    "not available",
    "do not have information",
    "cannot answer",
    "only answer ipl",
    "outside the scope",
)


class CitationAudit(BaseModel):
    """Extracted inline citations and source attribution markers from an answer."""

    inline_sql: bool = False
    inline_rag_indices: List[int] = Field(default_factory=list)
    inline_gemini_historical: bool = False
    has_sources_footer: bool = False
    phantom_rag_indices: List[int] = Field(default_factory=list)


class CaseEvaluationResult(BaseModel):
    """Per-case evaluation output combining trace telemetry and deterministic checks."""

    case_id: str
    category: str
    question: str
    ground_truth_status: str
    selected_route: Optional[str] = None
    expected_route: str
    cutoff_scope: Optional[str] = None
    expected_cutoff_scope: Optional[str] = None
    http_status: int = 200
    route_ok: Optional[bool] = None
    facts_ok: Optional[bool] = None
    forbidden_ok: Optional[bool] = None
    rag_ok: Optional[bool] = None
    citation_ok: Optional[bool] = None
    refusal_ok: Optional[bool] = None
    citations: CitationAudit = Field(default_factory=CitationAudit)
    missing_facts: List[str] = Field(default_factory=list)
    missing_numbers: List[str] = Field(default_factory=list)
    matched_forbidden: List[str] = Field(default_factory=list)
    verdict: VerdictLiteral
    failure_reasons: List[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    """Aggregate benchmark accuracy metrics across all evaluated cases."""

    total_cases: int
    correct: int
    partial: int
    incorrect: int
    appropriate_refusals: int
    pending_verification: int
    routing_accuracy: Optional[float] = None
    sql_fact_accuracy: Optional[float] = None
    rag_retrieval_quality: Optional[float] = None
    citation_quality: Optional[float] = None
    refusal_accuracy: Optional[float] = None
    by_category: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    pending_case_ids: List[str] = Field(default_factory=list)
    failed_case_ids: List[str] = Field(default_factory=list)


def extract_citations(answer: str, retrieved_count: int = 0) -> CitationAudit:
    """Parse inline citations and footer attribution markers from an answer."""
    text = answer or ""
    raw_indices = [int(m.group(1)) for m in re.finditer(r"\[S(\d+)\]", text)]
    unique_indices = list(dict.fromkeys(raw_indices))
    phantom = [idx for idx in unique_indices if idx < 1 or idx > retrieved_count]

    return CitationAudit(
        inline_sql="[SQL]" in text,
        inline_rag_indices=unique_indices,
        inline_gemini_historical="[Gemini Historical Knowledge]" in text,
        has_sources_footer=("### Sources" in text or "Source: CricketGPT" in text),
        phantom_rag_indices=phantom,
    )


def _contains_fact(answer_lower: str, fact: str) -> bool:
    return fact.lower() in answer_lower


def _contains_number(answer: str, number_token: str) -> bool:
    pattern = rf"(?<!\w){re.escape(number_token)}(?!\w)"
    return bool(re.search(pattern, answer))


def _looks_like_refusal_or_clarification(answer_lower: str) -> bool:
    return any(p in answer_lower for p in _REFUSAL_OR_CLARIFY_PATTERNS)


def _ratio(passed: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return round(passed / total, 4)


def evaluate_case(case: BenchmarkCase, trace: ChatExecutionTrace) -> CaseEvaluationResult:
    """Deterministically score a single `BenchmarkCase` against its `ChatExecutionTrace`."""
    answer = trace.answer or ""
    answer_lower = answer.lower()
    failure_reasons: List[str] = []

    citation_audit = extract_citations(answer, retrieved_count=len(trace.rag_chunks))

    # Pending-verification cases never fabricate passes; flag server errors if raised.
    if case.ground_truth_status == "pending_verification":
        if trace.http_status >= 500:
            return CaseEvaluationResult(
                case_id=case.id,
                category=case.category,
                question=case.question,
                ground_truth_status=case.ground_truth_status,
                selected_route=trace.selected_route,
                expected_route=case.expected_route,
                cutoff_scope=trace.cutoff_scope,
                expected_cutoff_scope=case.expected_cutoff_scope,
                http_status=trace.http_status,
                route_ok=(trace.selected_route == case.expected_route),
                citations=citation_audit,
                verdict="incorrect",
                failure_reasons=[f"HTTP {trace.http_status}: {trace.error or 'server error'}"],
            )
        route_match = (
            trace.selected_route == case.expected_route
            if trace.selected_route is not None
            else None
        )
        return CaseEvaluationResult(
            case_id=case.id,
            category=case.category,
            question=case.question,
            ground_truth_status=case.ground_truth_status,
            selected_route=trace.selected_route,
            expected_route=case.expected_route,
            cutoff_scope=trace.cutoff_scope,
            expected_cutoff_scope=case.expected_cutoff_scope,
            http_status=trace.http_status,
            route_ok=route_match,
            citations=citation_audit,
            verdict="pending_verification",
            failure_reasons=["Ground truth pending live database verification."],
        )

    # HTTP / empty response check
    if trace.http_status >= 400 or not answer.strip():
        return CaseEvaluationResult(
            case_id=case.id,
            category=case.category,
            question=case.question,
            ground_truth_status=case.ground_truth_status,
            selected_route=trace.selected_route,
            expected_route=case.expected_route,
            cutoff_scope=trace.cutoff_scope,
            expected_cutoff_scope=case.expected_cutoff_scope,
            http_status=trace.http_status,
            route_ok=(trace.selected_route == case.expected_route),
            facts_ok=False,
            forbidden_ok=True,
            rag_ok=False if case.requires_rag else None,
            citation_ok=False if case.expected_citations else None,
            refusal_ok=False if case.must_refuse_or_clarify else None,
            citations=citation_audit,
            verdict="incorrect",
            failure_reasons=[trace.error or f"Empty answer or HTTP {trace.http_status}"],
        )

    # 1. Route & cutoff scope check
    route_ok = trace.selected_route == case.expected_route
    if case.expected_cutoff_scope and trace.cutoff_scope is not None:
        route_ok = route_ok and (trace.cutoff_scope == case.expected_cutoff_scope)
    if not route_ok:
        failure_reasons.append(
            f"Route/scope mismatch: expected ({case.expected_route}, {case.expected_cutoff_scope}), "
            f"got ({trace.selected_route}, {trace.cutoff_scope})."
        )

    # 2. Required facts & numbers check
    missing_facts = [f for f in case.required_facts if not _contains_fact(answer_lower, f)]
    missing_numbers = [n for n in case.required_numbers if not _contains_number(answer, n)]
    facts_ok = not missing_facts and not missing_numbers
    if missing_facts:
        failure_reasons.append(f"Missing required facts: {', '.join(missing_facts)}")
    if missing_numbers:
        failure_reasons.append(f"Missing required numbers: {', '.join(missing_numbers)}")

    # 3. Forbidden / hallucination check
    matched_forbidden = [p for p in case.forbidden_patterns if _contains_fact(answer_lower, p)]
    forbidden_ok = not matched_forbidden
    if matched_forbidden:
        failure_reasons.append(f"Matched forbidden hallucinated patterns: {', '.join(matched_forbidden)}")

    # 4. RAG retrieval check
    rag_ok: Optional[bool] = None
    if case.requires_rag:
        if case.must_refuse_or_clarify:
            rag_ok = len(trace.rag_chunks) == 0
            if not rag_ok:
                failure_reasons.append("Expected 0 retrieved RAG chunks for refusal control case.")
        else:
            rag_ok = len(trace.rag_chunks) > 0
            if rag_ok and case.expected_rag_season:
                rag_ok = any(ch.season == case.expected_rag_season for ch in trace.rag_chunks)
            if rag_ok and case.expected_rag_doc_type:
                rag_ok = any(ch.doc_type == case.expected_rag_doc_type for ch in trace.rag_chunks)
            if rag_ok and case.expected_rag_match_id:
                rag_ok = any(ch.match_id == case.expected_rag_match_id for ch in trace.rag_chunks)
            if not rag_ok:
                failure_reasons.append("Retrieved RAG chunks missed expected document/season/match_id.")

    # 5. Citation quality check
    citation_ok: Optional[bool] = None
    if case.expected_citations or citation_audit.inline_rag_indices:
        missing_cits = [c for c in case.expected_citations if c.lower() not in answer_lower]
        citation_ok = (not missing_cits) and (not citation_audit.phantom_rag_indices)
        if missing_cits:
            failure_reasons.append(f"Missing expected citations: {', '.join(missing_cits)}")
        if citation_audit.phantom_rag_indices:
            failure_reasons.append(
                f"Phantom [S#] citations beyond retrieved chunks: {citation_audit.phantom_rag_indices}"
            )

    # 6. Refusal / clarification check
    looks_refused = _looks_like_refusal_or_clarification(answer_lower)
    refusal_ok: Optional[bool] = None
    if case.must_refuse_or_clarify:
        refusal_ok = looks_refused and facts_ok and forbidden_ok
        if not looks_refused:
            failure_reasons.append("Expected clean refusal or clarification, but model answered normally.")

    # Verdict assignment
    if case.must_refuse_or_clarify:
        verdict: VerdictLiteral = (
            "appropriate_refusal"
            if (refusal_ok and route_ok)
            else ("partial" if refusal_ok else "incorrect")
        )
    else:
        false_refusal = looks_refused and not facts_ok
        if false_refusal or not facts_ok or not forbidden_ok:
            verdict = "incorrect"
        elif (
            route_ok
            and (rag_ok is None or rag_ok)
            and (citation_ok is None or citation_ok)
        ):
            verdict = "correct"
        else:
            verdict = "partial"

    return CaseEvaluationResult(
        case_id=case.id,
        category=case.category,
        question=case.question,
        ground_truth_status=case.ground_truth_status,
        selected_route=trace.selected_route,
        expected_route=case.expected_route,
        cutoff_scope=trace.cutoff_scope,
        expected_cutoff_scope=case.expected_cutoff_scope,
        http_status=trace.http_status,
        route_ok=route_ok,
        facts_ok=facts_ok,
        forbidden_ok=forbidden_ok,
        rag_ok=rag_ok,
        citation_ok=citation_ok,
        refusal_ok=refusal_ok,
        citations=citation_audit,
        missing_facts=missing_facts,
        missing_numbers=missing_numbers,
        matched_forbidden=matched_forbidden,
        verdict=verdict,
        failure_reasons=failure_reasons,
    )


def summarize_evaluations(results: List[CaseEvaluationResult]) -> EvaluationSummary:
    """Compute aggregate accuracy, routing, SQL, RAG, citation, and refusal metrics."""
    by_category: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
            "partial": 0,
            "incorrect": 0,
            "appropriate_refusal": 0,
            "pending_verification": 0,
        }
    )

    correct = partial = incorrect = appropriate_refusals = pending = 0
    route_pass = route_total = 0
    sql_pass = sql_total = 0
    rag_pass = rag_total = 0
    cit_pass = cit_total = 0
    ref_pass = ref_total = 0

    pending_ids: List[str] = []
    failed_ids: List[str] = []

    for r in results:
        cat_bucket = by_category[r.category]
        cat_bucket["total"] += 1
        cat_bucket[r.verdict] += 1

        if r.verdict == "correct":
            correct += 1
        elif r.verdict == "partial":
            partial += 1
        elif r.verdict == "incorrect":
            incorrect += 1
            failed_ids.append(r.case_id)
        elif r.verdict == "appropriate_refusal":
            appropriate_refusals += 1
        elif r.verdict == "pending_verification":
            pending += 1
            pending_ids.append(r.case_id)

        if r.route_ok is not None:
            route_total += 1
            if r.route_ok:
                route_pass += 1

        if r.ground_truth_status == "verified" and r.refusal_ok is None and r.facts_ok is not None:
            sql_total += 1
            if r.facts_ok and (r.forbidden_ok is not False):
                sql_pass += 1

        if r.ground_truth_status == "verified" and r.rag_ok is not None:
            rag_total += 1
            if r.rag_ok:
                rag_pass += 1

        if r.ground_truth_status == "verified" and r.citation_ok is not None:
            cit_total += 1
            if r.citation_ok:
                cit_pass += 1

        if r.refusal_ok is not None:
            ref_total += 1
            if r.refusal_ok:
                ref_pass += 1

    return EvaluationSummary(
        total_cases=len(results),
        correct=correct,
        partial=partial,
        incorrect=incorrect,
        appropriate_refusals=appropriate_refusals,
        pending_verification=pending,
        routing_accuracy=_ratio(route_pass, route_total),
        sql_fact_accuracy=_ratio(sql_pass, sql_total),
        rag_retrieval_quality=_ratio(rag_pass, rag_total),
        citation_quality=_ratio(cit_pass, cit_total),
        refusal_accuracy=_ratio(ref_pass, ref_total),
        by_category=dict(by_category),
        pending_case_ids=pending_ids,
        failed_case_ids=failed_ids,
    )


def evaluate_dataset(
    cases: List[BenchmarkCase],
    executor: AbstractChatExecutor,
) -> Dict[str, Any]:
    """Execute and score an entire benchmark dataset cleanly using an executor."""
    results: List[CaseEvaluationResult] = []
    for case in cases:
        trace = executor.execute(case)
        results.append(evaluate_case(case, trace))

    summary = summarize_evaluations(results)
    return {
        "summary": summary,
        "results": results,
    }


def _fmt_pct(val: Optional[float]) -> str:
    return f"{val * 100:.1f}%" if val is not None else "N/A"


def render_markdown_report(
    summary: EvaluationSummary,
    results: List[CaseEvaluationResult],
    mode_label: str = "offline_mock",
) -> str:
    """Format an evaluation run as a human-readable Markdown report."""
    lines = [
        f"# CricketGPT Evaluation Report ({mode_label})",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total questions evaluated | {summary.total_cases} |",
        f"| Correct | {summary.correct} |",
        f"| Partially correct | {summary.partial} |",
        f"| Incorrect | {summary.incorrect} |",
        f"| Appropriate refusals / clarifications | {summary.appropriate_refusals} |",
        f"| Pending ground-truth verification | {summary.pending_verification} |",
        f"| Routing accuracy | {_fmt_pct(summary.routing_accuracy)} |",
        f"| Fact / SQL accuracy (verified cases) | {_fmt_pct(summary.sql_fact_accuracy)} |",
        f"| RAG retrieval quality | {_fmt_pct(summary.rag_retrieval_quality)} |",
        f"| Citation quality | {_fmt_pct(summary.citation_quality)} |",
        f"| Refusal accuracy | {_fmt_pct(summary.refusal_accuracy)} |",
        "",
        "## Category Breakdown",
        "",
        "| Category | Total | Correct | Partial | Incorrect | Appropriate Refusal | Pending Verification |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cat, counts in sorted(summary.by_category.items()):
        lines.append(
            f"| {cat} | {counts['total']} | {counts['correct']} | {counts['partial']} | "
            f"{counts['incorrect']} | {counts['appropriate_refusal']} | {counts['pending_verification']} |"
        )

    lines.extend([
        "",
        "## Per-Case Results",
        "",
        "| ID | Category | Route (Expected -> Actual) | Verdict | Notes / Failures |",
        "|---|---|---|---|---|",
    ])
    for r in results:
        actual_route = r.selected_route or "N/A"
        notes = "; ".join(r.failure_reasons) if r.failure_reasons else "OK"
        lines.append(
            f"| `{r.case_id}` | {r.category} | `{r.expected_route}` -> `{actual_route}` | **{r.verdict}** | {notes} |"
        )

    return "\n".join(lines) + "\n"


def save_evaluation_reports(
    summary: EvaluationSummary,
    results: List[CaseEvaluationResult],
    output_dir: str | Path,
    mode_label: str = "offline_mock",
) -> Dict[str, Path]:
    """Write JSON and Markdown evaluation reports to `output_dir`."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "evaluation_report.json"
    md_path = out / "evaluation_report.md"

    payload = {
        "mode": mode_label,
        "summary": summary.model_dump(),
        "results": [r.model_dump() for r in results],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(
        render_markdown_report(summary, results, mode_label=mode_label),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": md_path}

