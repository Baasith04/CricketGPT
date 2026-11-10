# CricketGPT Evaluation Framework (Phase 4 — Offline Harness)

This directory contains the offline benchmark dataset and generated evaluation artifacts
for CricketGPT answer accuracy testing.

## Architecture Overview

- `evaluation/datasets/ipl_benchmark.json`: Structured benchmark suite covering
  historical (<= configured cutoff), recent (> configured cutoff), deterministic SQL
  statistics, narrative/hybrid synthesis, and edge/refusal scenarios.
- Cases whose exact DB values have not yet been queried live are explicitly labeled
  `"ground_truth_status": "pending_verification"` so unverified ground truth is never fabricated.
- `app/evaluation/`: Standalone dataset loader, offline/mock trace recorder interface,
  and deterministic multi-dimensional scorer (routing, SQL factuality, RAG retrieval
  quality, citation hygiene, and refusal behavior).
- `scripts/evaluate_chatbot.py`: Generates JSON and Markdown evaluation reports from
  offline mock fixtures (with a clean interface reserved for post-backfill live execution).

## Offline Usage

```bash
python scripts/evaluate_chatbot.py --mode mock --output-dir evaluation/reports
```

