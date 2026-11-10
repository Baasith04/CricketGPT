"""
CricketGPT — Cricsheet Ingestion Engine

Parses official Cricsheet IPL JSON files, validates cricket data integrity,
resolves teams and players, and synchronizes records into Supabase PostgreSQL.
"""

from app.ingestion.importer import import_match
from app.ingestion.parser import parse_match
from app.ingestion.resolver import resolve_team_id

__all__ = ["import_match", "parse_match", "resolve_team_id"]

