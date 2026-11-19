# CricketGPT — API Layer

## Responsibility
The `app/api/` package provides the external HTTP REST interface for CricketGPT.

### Components
- `routes/`: Individual FastAPI `APIRouter` instances organized by domain resource.
- Dependencies, authentication (if required), and request validation middleware.

### Guidelines
- Controllers remain thin: extract parameters, delegate to `app/services/` or `app/ai/`, and return typed Pydantic responses.
- All endpoints must include OpenAPI docstrings, tags, status codes, and response models.

