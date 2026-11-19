# CricketGPT — Query Router

## Responsibility
Classifies user intent and routes incoming natural language questions to the appropriate retrieval backend.

### Routing Logic
1. **SQL Path:** For exact numerical, statistical, or leaderboard queries:
   - *"How many runs did Virat Kohli score in 2016?"*
   - *"Top 5 wicket takers in IPL 2024."*
2. **RAG Path:** For descriptive, contextual, or narrative queries:
   - *"What was the controversy in the 2019 RR vs CSK match?"*
   - *"Explain the IPL Impact Player rule introduced in 2023."*
3. **Hybrid Path:** For questions requiring both numbers and context:
   - *"How did KKR win the 2024 final and who was their key bowler?"*

