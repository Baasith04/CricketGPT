# CricketGPT — Document Chunking

## Responsibility
Segments raw cricket text into standardized chunks suitable for embedding and retrieval.

### Chunking Strategies
- Match summary chunking: Overlapping sliding window (e.g. 500 characters with 50-character overlap).
- Structural chunking: Chunking by match innings, award summaries, or editorial sections.
- Metadata attachment: Each chunk preserves `match_id`, `season`, `teams`, and source URL.

