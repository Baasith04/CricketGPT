# CricketGPT — Embeddings Module

## Responsibility
Interfaces with Gemini embedding endpoints to generate vector representations of text.

### Key Considerations
- Target Model: Google `text-embedding-004` (768 dimensions).
- Batch processing: Efficient bulk embedding generation during document ingestion.
- Normalization: Vector length normalization for cosine distance optimization.

