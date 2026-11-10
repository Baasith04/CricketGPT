# CricketGPT — Synchronization Module

## Responsibility
Maintains the automatic synchronization of IPL match data from official Cricsheet archives.

### Capabilities & Workflow
1. Periodically fetch the latest IPL match zip or index from Cricsheet.
2. Compare each file's SHA-256 hash and revision number against `sync_files`.
3. If new: insert file into `sync_files`, parse, validate, and import.
4. If modified (revision bump or hash changed): execute safe transactional replacement.
5. If unchanged: skip to prevent duplicate processing.
6. Record all execution outcomes (inserted, updated, skipped, failed) in `sync_history`.

