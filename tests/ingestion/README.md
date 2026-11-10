# CricketGPT — Ingestion Tests

## Responsibility
Validates Cricsheet parsing, identity resolution, mathematical consistency, and transactional database imports.

### Test Focus Areas
- `test_parser.py`: Verifies Cricsheet JSON v1.3.0 parsing across different match formats.
- `test_resolver.py`: Verifies canonical team mapping (e.g. DD -> DC) and player hex ID resolution.
- `test_validators.py`: Verifies 6-way mathematical balance checks (runs, wickets, extras, balls).
- `test_importer.py`: Tests transactional single-match imports and rollback safety.

