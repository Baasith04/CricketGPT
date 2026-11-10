from app.database.connection import get_db_connection


def main():
    names = ["Ganguly", "Kohli"]

    query = """
        SELECT player_id, canonical_name
        FROM players
        WHERE canonical_name ILIKE %s
        ORDER BY canonical_name;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for name in names:
                cur.execute(query, (f"%{name}%",))
                print(f"\nMatches for {name}:")
                for player_id, canonical_name in cur.fetchall():
                    print(player_id, "-", canonical_name)


if __name__ == "__main__":
    main()