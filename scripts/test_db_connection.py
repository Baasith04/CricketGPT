"""
CricketGPT — Standalone Database Connectivity Test Script

This script tests your live Supabase PostgreSQL connection using the credentials
defined in your local .env file.

Usage:
    python scripts/test_db_connection.py
"""

import sys
import os

# Add parent directory to Python path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import (
    check_database_connection,
    get_sanitized_host,
    get_database_url,
    DatabaseConfigurationError,
    DatabaseConnectionError,
)


def main():
    print("=" * 60)
    print("CricketGPT — Supabase Connection Test")
    print("=" * 60)

    try:
        url = get_database_url()
        host = get_sanitized_host(url)
        print(f"Target host: {host}")
        print("Connecting to Supabase PostgreSQL (SSL enforced)...")

        result = check_database_connection()

        print("\nSUCCESS!")
        print(f"Status:   {result['status']}")
        print(f"Database: {result['database']}")
        print("\nYour Supabase PostgreSQL database is connected and ready.")
        print("=" * 60)

    except DatabaseConfigurationError as e:
        print("\nCONFIGURATION ERROR:")
        print(f"-> {e}")
        print("\nTroubleshooting steps:")
        print("1. Ensure you created a .env file inside CricketGPT-Backend/")
        print("2. Set DATABASE_URL=postgresql://postgres.[project-ref]:[pass]@[host]:5432/postgres?sslmode=require")
        print("=" * 60)
        sys.exit(1)

    except DatabaseConnectionError as e:
        print("\nCONNECTION FAILED:")
        print(f"-> {e}")
        print("\nTroubleshooting steps:")
        print("1. Check if your database password is correct.")
        print("2. Ensure your internet connection is active.")
        print("3. In Supabase Dashboard, verify your project is not paused.")
        print("4. Use port 5432 (Session pooler) or 6543 (Transaction pooler).")
        print("=" * 60)
        sys.exit(1)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

