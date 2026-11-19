"""Automated unit and evaluation tests for the Hybrid RAG pipeline and SQL+RAG routing."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.rag.chunking.chunker import (
    clean_text,
    compute_sha256,
    extract_text_from_file,
    prepare_document_chunks,
    recursive_chunk_text,
)
from app.rag.embeddings.embedder import (
    DailyQuotaExhaustedError,
    EmbeddingService,
    is_daily_quota_exhausted_error,
    retry_with_backoff,
)
from app.rag.pipeline.rag_pipeline import answer_rag_question, ingest_document
from app.rag.retrieval.hybrid_retriever import hybrid_retrieve


# ---------------------------------------------------------------------------
# Chunking, Cleaning & Safety Extraction Tests
# ---------------------------------------------------------------------------

def test_clean_text_normalizes_whitespace_and_control_chars():
    raw = "Hello   world\r\n\r\n\r\n\r\nLine\x00two  "
    assert clean_text(raw) == "Hello world\n\nLinetwo"


def test_recursive_chunk_text_respects_size_and_overlap():
    text = "\n\n".join(f"Paragraph {i}: " + ("cricket " * 25) for i in range(6))
    chunks = recursive_chunk_text(text, chunk_size=350, chunk_overlap=50)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 450


def test_extract_text_rejects_raw_cricsheet_ball_by_ball_json(tmp_path: Path):
    cricsheet_file = tmp_path / "335982.json"
    cricsheet_file.write_text(
        json.dumps({"meta": {"revision": 1}, "info": {"teams": ["A", "B"]}, "innings": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Refusing to chunk raw Cricsheet"):
        extract_text_from_file(cricsheet_file)


def test_extract_text_parses_markdown_frontmatter(tmp_path: Path):
    md = tmp_path / "rule.md"
    md.write_text(
        "---\ntitle: DLS Rule\ndoc_type: cricket_rule\nseason: 2024\nteams: [CSK, MI]\n---\n\nDLS explanation body.",
        encoding="utf-8",
    )
    text, meta = extract_text_from_file(md)
    assert text == "DLS explanation body."
    assert meta["title"] == "DLS Rule"
    assert meta["doc_type"] == "cricket_rule"
    assert meta["season"] == "2024"
    assert meta["teams"] == ["CSK", "MI"]


def test_prepare_document_chunks_attaches_metadata():
    chunks = prepare_document_chunks(
        text="Section one.\n\nSection two.",
        source_key="file:test.md",
        title="Test Doc",
        doc_type="cricket_rule",
        season="2024",
        teams=["CSK"],
    )
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["source_key"] == "file:test.md"
    assert chunks[0]["metadata"]["doc_type"] == "cricket_rule"
    assert chunks[0]["metadata"]["teams"] == ["CSK"]


# ---------------------------------------------------------------------------
# Embedding Caching & Exponential Backoff Retry Tests
# ---------------------------------------------------------------------------

def test_retry_with_backoff_recovers_after_transient_error():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("transient failure")
        return "ok"

    with patch("app.rag.embeddings.embedder.time.sleep") as mock_sleep:
        res = retry_with_backoff(flaky, max_attempts=3, base_delay=0.1)
    assert res == "ok"
    assert attempts["n"] == 3
    assert mock_sleep.call_count == 2


@patch.dict("os.environ", {"GEMINI_API_KEY": "valid-test-key"})
@patch("app.rag.embeddings.embedder.genai.Client")
def test_embedding_service_uses_gemini_sdk_768_and_caches(mock_client_cls):
    fake_client = mock_client_cls.return_value.__enter__.return_value
    fake_emb = MagicMock()
    fake_emb.values = [2.0] * 768
    fake_resp = MagicMock()
    fake_resp.embeddings = [fake_emb]
    fake_client.models.embed_content.return_value = fake_resp

    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768, cache_size=10)
    v1 = svc.embed_texts(["Explain DLS rules"], task_type="RETRIEVAL_DOCUMENT")
    v2 = svc.embed_texts(["Explain DLS rules"], task_type="RETRIEVAL_DOCUMENT")

    assert len(v1[0]) == 768
    assert v1 == v2
    # L2 normalized norm should be ~1.0
    assert abs(sum(x * x for x in v1[0]) - 1.0) < 1e-6
    fake_client.models.embed_content.assert_called_once()
    call_kwargs = fake_client.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-embedding-2"
    assert call_kwargs["config"].output_dimensionality == 768
    assert call_kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"

    # Separate task_type (query) misses doc cache and calls RETRIEVAL_QUERY
    q_vec = svc.embed_query("Explain DLS rules")
    assert len(q_vec) == 768
    assert fake_client.models.embed_content.call_count == 2
    assert fake_client.models.embed_content.call_args.kwargs["config"].task_type == "RETRIEVAL_QUERY"


@patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False)
def test_embedding_service_fails_closed_when_api_key_missing():
    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        svc.embed_texts(["Explain DLS rules"])


@patch.dict("os.environ", {"GEMINI_API_KEY": "valid-test-key"})
@patch("app.rag.embeddings.embedder.time.sleep")
@patch("app.rag.embeddings.embedder.genai.Client")
def test_embedding_service_retries_and_raises_on_persistent_api_failure(mock_client_cls, mock_sleep):
    fake_client = mock_client_cls.return_value.__enter__.return_value
    fake_client.models.embed_content.side_effect = ConnectionError("Gemini embedding outage")

    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768)
    with pytest.raises(ConnectionError, match="Gemini embedding outage"):
        svc.embed_texts(["Chunk text"])
    assert fake_client.models.embed_content.call_count == 3
    assert mock_sleep.call_count == 2


def test_embedding_service_rejects_invalid_dimension():
    with pytest.raises(ValueError, match="between 1 and 2000"):
        EmbeddingService(dimension=3072)


@patch("app.rag.embeddings.embedder.time.sleep")
@patch("app.rag.embeddings.embedder.genai.Client")
def test_embedding_service_does_not_retry_permanent_400_client_error(
    mock_client_cls, mock_sleep, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaRealLookingKeyForMockTest123")
    fake_client = mock_client_cls.return_value.__enter__.return_value

    class FakeBadRequest(Exception):
        code = 400

    fake_client.models.embed_content.side_effect = FakeBadRequest("400 INVALID_ARGUMENT")

    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768)
    with pytest.raises(FakeBadRequest):
        svc.embed_texts(["Bad request test"])
    assert fake_client.models.embed_content.call_count == 1
    mock_sleep.assert_not_called()


def test_embedding_service_rejects_gemini_embedding_001_and_enforces_gemini_embedding_2(monkeypatch):
    with pytest.raises(ValueError, match="gemini-embedding-2"):
        EmbeddingService(model_name="gemini-embedding-001", dimension=768)

    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "gemini-embedding-001")
    with pytest.raises(ValueError, match="gemini-embedding-2"):
        EmbeddingService()


@patch("app.rag.embeddings.embedder.time.sleep")
@patch("app.rag.embeddings.embedder.genai.Client")
def test_embedding_service_stops_immediately_on_daily_quota_exhaustion(
    mock_client_cls, mock_sleep, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaRealLookingKeyForMockTest123")
    fake_client = mock_client_cls.return_value.__enter__.return_value

    class FakeQuotaError(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        details = {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "violations": [
                            {
                                "quotaId": "EmbedContentRequestsPerDayPerProjectPerModel-FreeTier",
                                "quotaValue": "1000",
                            }
                        ]
                    }
                ],
            }
        }

    fake_client.models.embed_content.side_effect = FakeQuotaError(
        "429 RESOURCE_EXHAUSTED: You exceeded your current quota."
    )

    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768)
    with pytest.raises(DailyQuotaExhaustedError, match="daily embedding quota exhausted"):
        svc.embed_texts(["Match report text"])

    assert fake_client.models.embed_content.call_count == 1
    mock_sleep.assert_not_called()


@patch("app.rag.embeddings.embedder.time.sleep")
@patch("app.rag.embeddings.embedder.genai.Client")
def test_embedding_service_still_retries_transient_per_minute_429(
    mock_client_cls, mock_sleep, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaRealLookingKeyForMockTest123")
    fake_client = mock_client_cls.return_value.__enter__.return_value

    class FakeRateLimitError(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        details = {
            "violations": [
                {"quotaId": "EmbedContentRequestsPerMinutePerProjectPerModel-FreeTier"}
            ]
        }

    fake_emb = MagicMock()
    fake_emb.values = [1.0] * 768
    fake_resp = MagicMock()
    fake_resp.embeddings = [fake_emb]

    err = FakeRateLimitError("429 RESOURCE_EXHAUSTED: per minute rate limit")
    assert is_daily_quota_exhausted_error(err) is False
    fake_client.models.embed_content.side_effect = [err, fake_resp]

    svc = EmbeddingService(model_name="gemini-embedding-2", dimension=768)
    vecs = svc.embed_texts(["Match report text"])

    assert len(vecs) == 1
    assert len(vecs[0]) == 768
    assert fake_client.models.embed_content.call_count == 2
    assert mock_sleep.call_count == 1


def test_classify_match_stage_distinguishes_final_playoff_and_league():
    from app.rag.pipeline.rag_pipeline import classify_match_stage

    assert classify_match_stage("Final", None)["stage_category"] == "final"
    assert classify_match_stage("Final", None)["is_season_final"] is True

    q1 = classify_match_stage("Qualifier 1", None)
    assert q1["stage_category"] == "playoff"
    assert q1["is_season_final"] is False

    league = classify_match_stage(None, 70)
    assert league["stage_category"] == "league"
    assert league["stage_label"] == "League Match 70"
    assert league["is_season_final"] is False


@patch("app.rag.pipeline.rag_pipeline.ingest_document")
@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_ingest_db_match_summaries_match_ids_filter_and_stage_labels(mock_conn, mock_ingest):
    from datetime import date
    from app.rag.pipeline.rag_pipeline import ingest_db_match_summaries

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    col_names = [
        "match_id", "season", "match_number", "stage", "match_date", "venue", "city",
        "result_type", "result_method", "win_by_runs", "win_by_wickets",
        "toss_winner", "toss_decision", "winner", "eliminator_winner",
        "teams_label", "teams_arr", "innings_summary", "potm",
    ]
    cur.description = [MagicMock(name=n) for n in col_names]
    for c, n in zip(cur.description, col_names):
        c.name = n

    cur.fetchall.return_value = [
        (
            1535465, "2026", None, "Final", date(2026, 5, 31), "M Chinnaswamy Stadium", "Bengaluru",
            "wickets", None, None, 6, "Royal Challengers Bengaluru", "field",
            "Royal Challengers Bengaluru", None,
            "Sunrisers Hyderabad vs Royal Challengers Bengaluru",
            ["Sunrisers Hyderabad", "Royal Challengers Bengaluru"],
            "Sunrisers Hyderabad scored 190/7 (20.0 overs); Royal Challengers Bengaluru scored 191/4 (19.2 overs)",
            "V Kohli",
        ),
        (
            1529313, "2026", 70, None, date(2026, 5, 25), "Wankhede Stadium", "Mumbai",
            "runs", None, 15, None, "Mumbai Indians", "bat",
            "Mumbai Indians", None,
            "Mumbai Indians vs Chennai Super Kings",
            ["Mumbai Indians", "Chennai Super Kings"],
            "Mumbai Indians scored 205/4 (20.0 overs); Chennai Super Kings scored 190/8 (20.0 overs)",
            "SA Yadav",
        ),
    ]
    mock_ingest.side_effect = [
        {"source_key": "db:match:1535465", "doc_id": 101, "status": "ingested", "chunk_count": 1},
        {"source_key": "db:match:1529313", "doc_id": 102, "status": "updated", "chunk_count": 1},
    ]

    res = ingest_db_match_summaries(match_ids=[1535465, 1529313, 1535465])

    sql, params = cur.execute.call_args.args
    assert "WHERE m.match_id = ANY(%s)" in sql
    assert params == ([1535465, 1529313],)
    assert res["processed"] == 2
    assert res["counts"] == {"ingested": 1, "updated": 1, "unchanged": 0, "failed": 0}
    assert mock_ingest.call_args_list[0].kwargs["title"].startswith("IPL 2026 Final Match Report")
    assert mock_ingest.call_args_list[1].kwargs["title"].startswith("IPL 2026 Match 1529313:")
    assert mock_ingest.call_args_list[1].kwargs["extra_metadata"]["is_season_final"] is False
    assert mock_ingest.call_args_list[1].kwargs["extra_metadata"]["stage_category"] == "league"


def test_ingest_db_match_summaries_empty_match_ids_noop():
    from app.rag.pipeline.rag_pipeline import ingest_db_match_summaries
    res = ingest_db_match_summaries(match_ids=[])
    assert res["processed"] == 0
    assert res["counts"]["ingested"] == 0


@patch("app.rag.pipeline.rag_pipeline.ingest_db_match_summaries")
@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_backfill_historical_match_rag_dry_run_and_resumable_batches(mock_conn, mock_ingest_batch):
    from app.rag.pipeline.rag_pipeline import backfill_historical_match_rag

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    # dry_run queries: total_sql_matches, already_covered, missing_ids
    cur.fetchone.side_effect = [(1243,), (17,)]
    cur.fetchall.return_value = [(335982,), (335983,), (335984,)]

    dry = backfill_historical_match_rag(batch_size=2, dry_run=True)
    assert dry["dry_run"] is True
    assert dry["total_sql_matches"] == 1243
    assert dry["already_covered"] == 17
    assert dry["missing_matches"] == 1226
    assert dry["target_count"] == 3
    mock_ingest_batch.assert_not_called()

    # Execution run processes 2 batches (size 2 + size 1) and aggregates counts
    cur.fetchone.side_effect = [(1243,), (17,)]
    cur.fetchall.return_value = [(335982,), (335983,), (335984,)]
    mock_ingest_batch.side_effect = [
        {"processed": 2, "counts": {"ingested": 2, "updated": 0, "unchanged": 0, "failed": 0}, "failed_match_ids": [], "errors": []},
        {"processed": 1, "counts": {"ingested": 1, "updated": 0, "unchanged": 0, "failed": 0}, "failed_match_ids": [], "errors": []},
    ]
    res = backfill_historical_match_rag(batch_size=2, dry_run=False)
    assert res["batches_executed"] == 2
    assert res["counts"] == {"processed": 3, "ingested": 3, "updated": 0, "unchanged": 0, "failed": 0}
    assert mock_ingest_batch.call_args_list[0].kwargs["match_ids"] == [335982, 335983]
    assert mock_ingest_batch.call_args_list[0].kwargs["batch_embed"] is True
    assert mock_ingest_batch.call_args_list[1].kwargs["match_ids"] == [335984]


@patch("app.rag.pipeline.rag_pipeline.ingest_document")
@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_ingest_db_match_summaries_stops_immediately_without_per_doc_fallback_on_quota_exhaustion(
    mock_conn, mock_ingest
):
    from datetime import date
    from app.rag.pipeline.rag_pipeline import ingest_db_match_summaries

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    col_names = [
        "match_id", "season", "match_number", "stage", "match_date", "venue", "city",
        "result_type", "result_method", "win_by_runs", "win_by_wickets",
        "toss_winner", "toss_decision", "winner", "eliminator_winner",
        "teams_label", "teams_arr", "innings_summary", "potm",
    ]
    cur.description = [MagicMock(name=n) for n in col_names]
    for c, n in zip(cur.description, col_names):
        c.name = n

    cur.fetchall.side_effect = [
        [
            (
                335982, "2008", 1, None, date(2008, 4, 18), "M Chinnaswamy Stadium", "Bengaluru",
                "runs", None, 140, None, "Royal Challengers Bangalore", "field",
                "Kolkata Knight Riders", None,
                "Royal Challengers Bangalore vs Kolkata Knight Riders",
                ["Royal Challengers Bangalore", "Kolkata Knight Riders"],
                "Kolkata Knight Riders scored 222/3 (20.0 overs)",
                "BB McCullum",
            ),
            (
                335983, "2008", 2, None, date(2008, 4, 19), "PCA Stadium", "Chandigarh",
                "runs", None, 33, None, "Chennai Super Kings", "bat",
                "Chennai Super Kings", None,
                "Kings XI Punjab vs Chennai Super Kings",
                ["Kings XI Punjab", "Chennai Super Kings"],
                "Chennai Super Kings scored 240/5 (20.0 overs)",
                "MEK Hussey",
            ),
        ],
        [],  # existing hashes query in batch_embed=True
    ]

    fake_embedder = MagicMock()
    fake_embedder.model_name = "gemini-embedding-2"
    fake_embedder.embed_texts.side_effect = DailyQuotaExhaustedError(
        "Gemini daily embedding quota exhausted"
    )

    with pytest.raises(DailyQuotaExhaustedError):
        ingest_db_match_summaries(
            match_ids=[335982, 335983],
            embedder=fake_embedder,
            batch_embed=True,
        )

    fake_embedder.embed_texts.assert_called_once()
    mock_ingest.assert_not_called()


@patch("app.rag.pipeline.rag_pipeline.ingest_db_match_summaries")
@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_backfill_stops_immediately_on_daily_quota_exhaustion_and_reports_resume(
    mock_conn, mock_ingest_batch
):
    from app.rag.pipeline.rag_pipeline import backfill_historical_match_rag

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [(1243,), (983,)]
    missing_ids = [(100000 + i,) for i in range(260)]
    cur.fetchall.return_value = missing_ids

    mock_ingest_batch.side_effect = [
        {
            "processed": 50,
            "counts": {"ingested": 50, "updated": 0, "unchanged": 0, "failed": 0},
            "failed_match_ids": [],
            "errors": [],
        },
        DailyQuotaExhaustedError("429 RESOURCE_EXHAUSTED: EmbedContentRequestsPerDay"),
    ]

    res = backfill_historical_match_rag(batch_size=50, dry_run=False)

    assert res["status"] == "stopped_quota_exhausted"
    assert res["quota_exhausted"] is True
    assert res["stopped_reason"] == "daily_quota_exhausted"
    assert res["embedding_model"] == "gemini-embedding-2"
    assert res["previously_covered"] == 983
    assert res["target_count"] == 260
    assert res["batches_executed"] == 1
    assert res["counts"]["ingested"] == 50
    assert res["remaining_matches"] == 210
    assert res["resume_command"] == "python scripts/ingest_rag.py --backfill-rag"
    # Stopped after batch 2 failed without attempting batches 3..6
    assert mock_ingest_batch.call_count == 2


# ---------------------------------------------------------------------------
# Incremental Ingestion & Hybrid Retrieval (Mocked DB)
# ---------------------------------------------------------------------------

@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_ingest_document_skips_unchanged_hash(mock_conn):
    text = "DLS calculates revised target."
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (7, compute_sha256(text), 1)
    fake_embedder = MagicMock()
    fake_embedder.model_name = "gemini-embedding-2"
    fake_embedder.dimension = 768

    res = ingest_document(
        source_key="file:dls.md",
        title="DLS",
        text=text,
        doc_type="cricket_rule",
        embedder=fake_embedder,
    )
    assert res["status"] == "unchanged"
    assert res["doc_id"] == 7
    fake_embedder.embed_texts.assert_not_called()
    assert cur.execute.call_count == 1


@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_ingest_document_records_embedding_provenance_in_document_and_chunk_metadata(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    # 1st fetchone: check existing -> None (new doc); 2nd fetchone: INSERT RETURNING doc_id -> 984
    cur.fetchone.side_effect = [None, (984,)]

    fake_embedder = MagicMock()
    fake_embedder.model_name = "gemini-embedding-2"
    fake_embedder.dimension = 768
    fake_embedder.embed_texts.return_value = [[0.1] * 768]

    res = ingest_document(
        source_key="db:match:1426290",
        title="IPL 2024 Match 1426290",
        text="Match summary text for provenance verification.",
        doc_type="match_report",
        season="2024",
        match_id=1426290,
        extra_metadata={"generated_from": "cricsheet_sql"},
        embedder=fake_embedder,
    )

    assert res["status"] == "ingested"
    assert res["doc_id"] == 984

    doc_insert_call = cur.execute.call_args_list[1]
    doc_sql, doc_params = doc_insert_call.args
    assert "INSERT INTO rag_documents" in doc_sql
    doc_jsonb = doc_params[10]
    assert doc_jsonb.obj["embedding_model"] == "gemini-embedding-2"
    assert doc_jsonb.obj["embedding_dimension"] == 768
    assert doc_jsonb.obj["generated_from"] == "cricsheet_sql"

    chunk_insert_call = cur.execute.call_args_list[3]
    chunk_sql, chunk_params = chunk_insert_call.args
    assert "INSERT INTO rag_chunks" in chunk_sql
    chunk_jsonb = chunk_params[8]
    assert chunk_jsonb.obj["embedding_model"] == "gemini-embedding-2"
    assert chunk_jsonb.obj["embedding_dimension"] == 768


@patch("app.rag.pipeline.rag_pipeline.ingest_document")
@patch("app.rag.pipeline.rag_pipeline.get_db_connection")
def test_provenance_consistent_between_backfill_and_incremental_sync(mock_conn, mock_ingest):
    from datetime import date
    from app.rag.pipeline.rag_pipeline import ingest_db_match_summaries

    col_names = [
        "match_id", "season", "match_number", "stage", "match_date", "venue", "city",
        "result_type", "result_method", "win_by_runs", "win_by_wickets",
        "toss_winner", "toss_decision", "winner", "eliminator_winner",
        "teams_label", "teams_arr", "innings_summary", "potm",
    ]
    row = (
        1426290, "2024", 52, None, date(2024, 5, 4), "M Chinnaswamy Stadium", "Bengaluru",
        "wickets", None, None, 4, "Royal Challengers Bengaluru", "field",
        "Royal Challengers Bengaluru", None,
        "Gujarat Titans vs Royal Challengers Bengaluru",
        ["Gujarat Titans", "Royal Challengers Bengaluru"],
        "Gujarat Titans scored 147/10 (19.3 overs); Royal Challengers Bengaluru scored 152/6 (13.4 overs)",
        "Mohammed Siraj",
    )

    fake_embedder = MagicMock()
    fake_embedder.model_name = "gemini-embedding-2"
    fake_embedder.dimension = 768
    fake_embedder.embed_texts.return_value = [[0.2] * 768]

    mock_ingest.return_value = {
        "source_key": "db:match:1426290",
        "doc_id": 984,
        "status": "ingested",
        "chunk_count": 1,
    }

    # 1. Historical backfill path (batch_embed=True)
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.description = [MagicMock(name=n) for n in col_names]
    for c, n in zip(cur.description, col_names):
        c.name = n
    cur.fetchall.side_effect = [[row], []]

    ingest_db_match_summaries(match_ids=[1426290], batch_embed=True, embedder=fake_embedder)
    backfill_meta = mock_ingest.call_args.kwargs["extra_metadata"]

    # 2. Incremental Cricsheet sync path (batch_embed=False)
    cur.fetchall.side_effect = [[row]]
    ingest_db_match_summaries(match_ids=[1426290], batch_embed=False, embedder=fake_embedder)
    sync_meta = mock_ingest.call_args.kwargs["extra_metadata"]

    assert backfill_meta["embedding_model"] == "gemini-embedding-2"
    assert backfill_meta["embedding_dimension"] == 768
    assert sync_meta["embedding_model"] == "gemini-embedding-2"
    assert sync_meta["embedding_dimension"] == 768
    assert backfill_meta == sync_meta


@patch("app.rag.retrieval.hybrid_retriever.get_db_connection")
def test_hybrid_retrieve_passes_metadata_filters_and_formats_scores(mock_conn):
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.25] * 768

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.description = [
        MagicMock(name="col") for _ in range(17)
    ]
    names = [
        "chunk_id", "doc_id", "source_key", "title", "doc_type",
        "source_path", "source_url", "season", "match_id", "teams", "players",
        "chunk_index", "chunk_text", "metadata",
        "vector_similarity", "keyword_score", "hybrid_score",
    ]
    for col, n in zip(cur.description, names):
        col.name = n
    cur.fetchall.return_value = [(
        1, 10, "file:dls.md", "DLS Rules", "cricket_rule",
        "knowledge_base/rules/dls.md", None, None, None, [], [],
        0, "DLS relies on overs and wickets remaining.", {},
        0.8123, 0.45, 0.7217,
    )]

    rows = hybrid_retrieve(
        query="Explain DLS rules",
        top_k=3,
        similarity_threshold=0.3,
        doc_type="cricket_rule",
        embedder=fake_embedder,
    )
    assert len(rows) == 1
    assert rows[0]["title"] == "DLS Rules"
    assert rows[0]["hybrid_score"] == 0.7217
    sql_executed, params = cur.execute.call_args.args
    assert "c.doc_type = %s" in sql_executed
    assert "cricket_rule" in params


@patch("app.rag.retrieval.hybrid_retriever.get_db_connection")
def test_hybrid_retrieve_falls_back_to_keyword_search_on_daily_quota_exhaustion(mock_conn):
    fake_embedder = MagicMock()
    fake_embedder.embed_query.side_effect = DailyQuotaExhaustedError(
        "Gemini daily embedding quota exhausted"
    )

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.description = [MagicMock(name="col") for _ in range(17)]
    names = [
        "chunk_id", "doc_id", "source_key", "title", "doc_type",
        "source_path", "source_url", "season", "match_id", "teams", "players",
        "chunk_index", "chunk_text", "metadata",
        "vector_similarity", "keyword_score", "hybrid_score",
    ]
    for col, n in zip(cur.description, names):
        col.name = n
    cur.fetchall.return_value = [(
        1, 10, "file:dls.md", "DLS Rules", "cricket_rule",
        "knowledge_base/rules/dls.md", None, None, None, [], [],
        0, "DLS relies on overs and wickets remaining.", {},
        0.0, 0.45, 0.45,
    )]

    rows = hybrid_retrieve(
        query="Explain DLS rules",
        top_k=3,
        similarity_threshold=0.3,
        doc_type="cricket_rule",
        embedder=fake_embedder,
    )

    fake_embedder.embed_query.assert_called_once()
    assert len(rows) == 1
    assert rows[0]["title"] == "DLS Rules"
    assert rows[0]["vector_similarity"] == 0.0
    assert rows[0]["keyword_score"] == 0.45
    sql_executed, params = cur.execute.call_args.args
    assert "0.0::float8 AS vector_similarity" in sql_executed
    assert "WHERE keyword_score > 0.0" in sql_executed
    assert "cricket_rule" in params


@patch("app.rag.pipeline.rag_pipeline.generate_response")
@patch("app.rag.pipeline.rag_pipeline.hybrid_retrieve")
def test_answer_rag_question_cites_sql_and_retrieved_sources(mock_retrieve, mock_llm):
    mock_retrieve.return_value = [
        {
            "chunk_id": 1,
            "title": "IPL 2024 Season Narrative",
            "doc_type": "season_summary",
            "season": "2024",
            "match_id": None,
            "source_key": "file:ipl_2024.md",
            "source_path": "knowledge_base/summaries/ipl_2024.md",
            "source_url": None,
            "chunk_text": "CSK finished 7-7 under Ruturaj Gaikwad.",
            "hybrid_score": 0.78,
        }
    ]
    mock_llm.return_value = "CSK won 7 of 14 matches [SQL] under Ruturaj Gaikwad [S1]."

    answer = answer_rag_question(
        question="Explain CSK's 2024 performance using match statistics",
        sql_context="Matches played: 14, Wins: 7, Losses: 7",
        season="2024",
    )
    assert "[SQL]" in answer
    assert "[S1]" in answer
    assert "### Sources" in answer
    assert "IPL 2024 Season Narrative" in answer


@patch("app.rag.pipeline.rag_pipeline.hybrid_retrieve")
def test_answer_rag_question_no_sources_and_no_sql_refuses_to_hallucinate(mock_retrieve):
    mock_retrieve.return_value = []
    answer = answer_rag_question("Explain unknown obscure rule XYZ")
    assert "could not find relevant documents" in answer.lower()


# ---------------------------------------------------------------------------
# End-to-End Router Mode Tests (SQL vs RAG vs Hybrid SQL+RAG)
# ---------------------------------------------------------------------------

@patch("app.ai.query_router.router.answer_leaderboard_question")
def test_router_sql_only_most_ipl_runs(mock_sql):
    mock_sql.return_value = "SQL leaderboard"
    from app.ai.query_router.router import route_question
    res = route_question("Most IPL runs")
    mock_sql.assert_called_once()
    assert res == "SQL leaderboard"


@patch("app.ai.query_router.router.answer_historical_llm_question")
@patch("app.ai.query_router.router.answer_rag_narrative_question")
def test_router_rag_explain_ipl_2024_final(mock_rag, mock_hist, monkeypatch):
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_SEASON", "2023")
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_DATE", "2024-03-01")
    mock_rag.return_value = "RAG 2024 final"
    from app.ai.query_router.router import route_question
    res = route_question("Explain IPL 2024 final")
    mock_rag.assert_called_once_with("Explain IPL 2024 final", season="2024")
    mock_hist.assert_not_called()
    assert res == "RAG 2024 final"


@patch("app.ai.answer_service.generate_response")
@patch("app.ai.query_router.router.answer_rag_narrative_question")
def test_router_within_cutoff_explain_ipl_2024_final_uses_mocked_llm_provider(
    mock_rag, mock_generate, monkeypatch
):
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_SEASON", "2024")
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_DATE", "2025-03-01")
    mock_generate.return_value = "KKR defeated SRH in the IPL 2024 final."

    from app.ai.query_router.router import route_question
    res = route_question("Explain IPL 2024 final")

    mock_rag.assert_not_called()
    mock_generate.assert_called_once()
    assert "KKR defeated SRH in the IPL 2024 final." in res
    assert "<= IPL 2024 / 2025-03-01" in res


@pytest.mark.parametrize(
    ("cutoff_season", "cutoff_date", "query", "expected_season", "expected_mode"),
    [
        ("2023", "2024-03-01", "Explain IPL 2023 final", "2023", "historical_llm"),
        ("2023", "2024-03-01", "Explain IPL 2024 final", "2024", "rag"),
        ("2024", "2025-03-01", "Explain IPL 2024 final", "2024", "historical_llm"),
        ("2024", "2025-03-01", "Explain IPL 2025 final", "2025", "rag"),
    ],
)
@patch("app.ai.answer_service.generate_response")
@patch("app.ai.query_router.router.answer_rag_narrative_question")
def test_router_cutoff_boundary_routes_both_sides_deterministically(
    mock_rag,
    mock_generate,
    monkeypatch,
    cutoff_season,
    cutoff_date,
    query,
    expected_season,
    expected_mode,
):
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_SEASON", cutoff_season)
    monkeypatch.setenv("GEMINI_KNOWLEDGE_CUTOFF_DATE", cutoff_date)
    mock_rag.return_value = f"RAG {expected_season}"
    mock_generate.return_value = f"LLM {expected_season}"

    from app.ai.query_router.router import route_question
    res = route_question(query)

    if expected_mode == "rag":
        mock_rag.assert_called_once_with(query, season=expected_season)
        mock_generate.assert_not_called()
        assert res == f"RAG {expected_season}"
    else:
        mock_rag.assert_not_called()
        mock_generate.assert_called_once()
        assert f"LLM {expected_season}" in res
        assert f"<= IPL {cutoff_season} / {cutoff_date}" in res


@patch("app.ai.query_router.router.answer_rag_narrative_question")
def test_router_rag_explain_dls_rules(mock_rag):
    mock_rag.return_value = "RAG DLS"
    from app.ai.query_router.router import route_question
    res = route_question("Explain DLS rules")
    mock_rag.assert_called_once_with("Explain DLS rules", season=None)
    assert res == "RAG DLS"


@patch("app.ai.query_router.router.answer_hybrid_team_question")
def test_router_hybrid_explain_csk_2024_with_stats(mock_hybrid):
    mock_hybrid.return_value = "Hybrid CSK 2024"
    from app.ai.query_router.router import route_question
    res = route_question("Explain CSK's 2024 performance using match statistics")
    mock_hybrid.assert_called_once_with(
        "Explain CSK's 2024 performance using match statistics",
        "csk",
        season="2024",
    )
    assert res == "Hybrid CSK 2024"


@patch("app.ai.query_router.router.answer_hybrid_player_comparison_question")
def test_router_hybrid_compare_kohli_and_rohit_2024(mock_hybrid):
    mock_hybrid.return_value = "Hybrid Kohli vs Rohit 2024"
    from app.ai.query_router.router import route_question
    res = route_question("Compare Kohli and Rohit in IPL 2024 and explain the difference")
    mock_hybrid.assert_called_once_with(
        "Compare Kohli and Rohit in IPL 2024 and explain the difference",
        "Kohli",
        "Rohit",
        season="2024",
    )
    assert res == "Hybrid Kohli vs Rohit 2024"
