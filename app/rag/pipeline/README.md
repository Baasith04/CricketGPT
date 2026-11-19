# CricketGPT — RAG Pipeline Orchestrator

## Responsibility
End-to-end coordinator delivering relevant knowledge context to Gemini.

### Pipeline Flow
```
User Query
    │
    ▼
[Generate Query Embedding] (app/rag/embeddings)
    │
    ▼
[Retrieve Top-K Chunks via pgvector] (app/rag/retrieval)
    │
    ▼
[Filter & Re-rank by Relevance]
    │
    ▼
[Assemble Grounded Context Prompt] (app/ai/prompts)
    │
    ▼
[Generate Grounded Answer with Gemini] (app/ai/llm)
```

