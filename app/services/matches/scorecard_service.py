from typing import Any, Dict, List, Optional
from app.database.connection import get_db_connection
from app.services.matches.match_service import get_match_details


def _overs_string(legal_balls: int) -> str:
    """Format total legal balls into standard cricket overs string (e.g. 24 -> '4.0', 25 -> '4.1')."""
    return f"{legal_balls // 6}.{legal_balls % 6}"


def _format_dismissal_text(
    is_out: bool,
    dismissal_kind: Optional[str],
    bowler_name: Optional[str],
    fielders: Optional[List[str]],
) -> str:
    """Generate human-readable dismissal text matching professional cricket scorecards."""
    kind = (dismissal_kind or "").strip().lower()
    if not is_out:
        if kind == "retired hurt":
            return "retired hurt"
        return "not out"

    fielders_list = fielders if isinstance(fielders, list) else []

    if kind == "bowled":
        return f"b {bowler_name}" if bowler_name else "b"
    if kind in ("caught", "caught and bowled"):
        if kind == "caught and bowled" or not fielders_list:
            return f"c & b {bowler_name}" if bowler_name else "c & b"
        return f"c {fielders_list[0]} b {bowler_name}" if bowler_name else f"c {fielders_list[0]}"
    if kind == "lbw":
        return f"lbw b {bowler_name}" if bowler_name else "lbw"
    if kind == "stumped":
        if fielders_list:
            return f"st {fielders_list[0]} b {bowler_name}" if bowler_name else f"st {fielders_list[0]}"
        return f"st b {bowler_name}" if bowler_name else "st"
    if kind == "run out":
        if fielders_list:
            return f"run out ({'/'.join(str(f) for f in fielders_list)})"
        return "run out"
    if kind == "retired hurt":
        return "retired hurt"
    if kind == "hit wicket":
        return f"hit wicket b {bowler_name}" if bowler_name else "hit wicket"

    return f"{dismissal_kind} b {bowler_name}" if bowler_name else str(dismissal_kind)


def get_match_scorecard(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the full match scorecard including innings summaries, batter figures,
    bowler figures, and extras. Separates regular innings and Super Overs.
    """
    if not isinstance(match_id, int) or isinstance(match_id, bool) or match_id <= 0:
        raise ValueError("A valid positive integer match ID is required.")

    match_info = get_match_details(match_id)
    if not match_info:
        return None

    query_innings = """
        SELECT
            i.innings_id,
            i.innings_number,
            i.batting_team_id,
            bt.canonical_name AS batting_team,
            i.bowling_team_id,
            bw.canonical_name AS bowling_team,
            i.total_runs,
            i.total_wickets,
            i.legal_balls_bowled,
            i.is_super_over,
            i.target_runs
        FROM innings i
        JOIN teams bt ON bt.team_id = i.batting_team_id
        JOIN teams bw ON bw.team_id = i.bowling_team_id
        WHERE i.match_id = %s
        ORDER BY i.innings_number ASC;
    """

    query_batting = """
        WITH innings_batters AS (
            SELECT
                batter_id AS player_id,
                batter_name AS fallback_name,
                MIN(delivery_id) AS first_ball_id
            FROM deliveries
            WHERE innings_id = %s AND batter_id IS NOT NULL
            GROUP BY batter_id, batter_name
            UNION
            SELECT
                non_striker_id AS player_id,
                non_striker_name AS fallback_name,
                MIN(delivery_id) AS first_ball_id
            FROM deliveries
            WHERE innings_id = %s AND non_striker_id IS NOT NULL
            GROUP BY non_striker_id, non_striker_name
        ),
        batter_appearance AS (
            SELECT
                ib.player_id,
                COALESCE(p.canonical_name, MAX(ib.fallback_name)) AS player_name,
                MIN(ib.first_ball_id) AS first_appearance_id
            FROM innings_batters ib
            LEFT JOIN players p ON p.player_id = ib.player_id
            GROUP BY ib.player_id, p.canonical_name
        ),
        batter_stats AS (
            SELECT
                d.batter_id AS player_id,
                SUM(d.batter_runs) AS runs,
                COUNT(*) FILTER (WHERE d.wide_runs = 0) AS balls,
                COUNT(*) FILTER (WHERE d.batter_runs = 4) AS fours,
                COUNT(*) FILTER (WHERE d.batter_runs = 6) AS sixes
            FROM deliveries d
            WHERE d.innings_id = %s AND d.batter_id IS NOT NULL
            GROUP BY d.batter_id
        ),
        wicket_stats AS (
            SELECT
                w.player_dismissed_id AS player_id,
                COUNT(*) FILTER (WHERE LOWER(w.dismissal_kind) <> 'retired hurt') AS dismissals,
                (ARRAY_AGG(w.dismissal_kind ORDER BY w.wicket_id DESC))[1] AS dismissal_kind,
                (ARRAY_AGG(d.bowler_name ORDER BY w.wicket_id DESC))[1] AS bowler_name,
                (ARRAY_AGG(w.fielders ORDER BY w.wicket_id DESC))[1] AS fielders
            FROM delivery_wickets w
            JOIN deliveries d ON d.delivery_id = w.delivery_id
            WHERE d.innings_id = %s
            GROUP BY w.player_dismissed_id
        )
        SELECT
            ba.player_id,
            ba.player_name,
            COALESCE(b.runs, 0) AS runs,
            COALESCE(b.balls, 0) AS balls,
            COALESCE(b.fours, 0) AS fours,
            COALESCE(b.sixes, 0) AS sixes,
            ROUND(COALESCE(b.runs, 0)::NUMERIC * 100 / NULLIF(COALESCE(b.balls, 0), 0), 2) AS strike_rate,
            (COALESCE(w.dismissals, 0) > 0) AS is_out,
            w.dismissal_kind,
            w.bowler_name,
            w.fielders
        FROM batter_appearance ba
        LEFT JOIN batter_stats b ON b.player_id = ba.player_id
        LEFT JOIN wicket_stats w ON w.player_id = ba.player_id
        ORDER BY ba.first_appearance_id ASC;
    """

    query_bowling = """
        WITH bowling_stats AS (
            SELECT
                d.bowler_id AS player_id,
                COALESCE(p.canonical_name, d.bowler_name) AS player_name,
                COUNT(*) FILTER (WHERE d.is_legal_ball = TRUE) AS legal_balls,
                SUM(d.batter_runs + COALESCE(d.wide_runs, 0) + COALESCE(d.no_ball_runs, 0)) AS runs_conceded,
                COUNT(*) FILTER (WHERE d.wide_runs > 0) AS wides,
                COUNT(*) FILTER (WHERE d.no_ball_runs > 0) AS no_balls,
                MIN(d.delivery_id) AS first_delivery_id
            FROM deliveries d
            LEFT JOIN players p ON p.player_id = d.bowler_id
            WHERE d.innings_id = %s
            GROUP BY d.bowler_id, p.canonical_name, d.bowler_name
        ),
        over_stats AS (
            SELECT
                d.bowler_id AS player_id,
                d.over_number,
                COUNT(*) FILTER (WHERE d.is_legal_ball = TRUE) AS legal_balls,
                SUM(d.batter_runs + COALESCE(d.wide_runs, 0) + COALESCE(d.no_ball_runs, 0)) AS runs_conceded
            FROM deliveries d
            WHERE d.innings_id = %s
            GROUP BY d.bowler_id, d.over_number
        ),
        maidens AS (
            SELECT
                player_id,
                COUNT(*) AS maiden_overs
            FROM over_stats
            WHERE legal_balls = 6 AND runs_conceded = 0
            GROUP BY player_id
        ),
        wicket_stats AS (
            SELECT
                d.bowler_id AS player_id,
                COUNT(*) AS wickets
            FROM delivery_wickets w
            JOIN deliveries d ON d.delivery_id = w.delivery_id
            WHERE d.innings_id = %s
              AND w.is_bowler_credit = TRUE
            GROUP BY d.bowler_id
        )
        SELECT
            b.player_id,
            b.player_name,
            b.legal_balls,
            COALESCE(m.maiden_overs, 0) AS maidens,
            b.runs_conceded,
            COALESCE(w.wickets, 0) AS wickets,
            ROUND(b.runs_conceded::NUMERIC * 6 / NULLIF(b.legal_balls, 0), 2) AS economy,
            b.wides,
            b.no_balls
        FROM bowling_stats b
        LEFT JOIN maidens m ON m.player_id = b.player_id
        LEFT JOIN wicket_stats w ON w.player_id = b.player_id
        ORDER BY b.first_delivery_id ASC;
    """

    query_extras = """
        SELECT
            COALESCE(SUM(wide_runs), 0) AS wides,
            COALESCE(SUM(no_ball_runs), 0) AS no_balls,
            COALESCE(SUM(bye_runs), 0) AS byes,
            COALESCE(SUM(leg_bye_runs), 0) AS leg_byes,
            COALESCE(SUM(penalty_runs), 0) AS penalty,
            COALESCE(SUM(extra_runs), 0) AS total_extras
        FROM deliveries
        WHERE innings_id = %s;
    """

    regular_innings = []
    super_overs = []
    has_super_over = False

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query_innings, (match_id,))
            innings_rows = cur.fetchall()

            for i_row in innings_rows:
                (
                    inn_id, inn_num, bat_id, bat_name, bowl_id, bowl_name,
                    tot_runs, tot_wickets, legal_balls, is_so, target_runs
                ) = i_row

                if is_so:
                    has_super_over = True

                # Batting
                cur.execute(query_batting, (inn_id, inn_id, inn_id, inn_id))
                batting_rows = cur.fetchall()
                batting_list = []
                for b in batting_rows:
                    is_out = bool(b[7])
                    dismissal_text = _format_dismissal_text(is_out, b[8], b[9], b[10])
                    batting_list.append({
                        "player_id": b[0],
                        "player_name": b[1],
                        "runs": b[2],
                        "balls": b[3],
                        "fours": b[4],
                        "sixes": b[5],
                        "strike_rate": float(b[6]) if b[6] is not None else 0.0,
                        "is_out": is_out,
                        "dismissal": dismissal_text,
                    })

                # Bowling
                cur.execute(query_bowling, (inn_id, inn_id, inn_id))
                bowling_rows = cur.fetchall()
                bowling_list = []
                for bw in bowling_rows:
                    bowling_list.append({
                        "player_id": bw[0],
                        "player_name": bw[1],
                        "overs": _overs_string(bw[2]),
                        "legal_balls": bw[2],
                        "maidens": bw[3],
                        "runs_conceded": bw[4],
                        "wickets": bw[5],
                        "economy": float(bw[6]) if bw[6] is not None else 0.0,
                        "wides": bw[7],
                        "no_balls": bw[8],
                    })

                # Extras
                cur.execute(query_extras, (inn_id,))
                ex = cur.fetchone()
                extras_dict = {
                    "wides": ex[0] if ex else 0,
                    "no_balls": ex[1] if ex else 0,
                    "byes": ex[2] if ex else 0,
                    "leg_byes": ex[3] if ex else 0,
                    "penalty": ex[4] if ex else 0,
                    "total_extras": ex[5] if ex else 0,
                }

                run_rate = (
                    round(tot_runs * 6 / legal_balls, 2)
                    if legal_balls > 0
                    else 0.0
                )

                innings_obj = {
                    "innings_id": inn_id,
                    "innings_number": inn_num,
                    "batting_team_id": bat_id,
                    "batting_team": bat_name,
                    "bowling_team_id": bowl_id,
                    "bowling_team": bowl_name,
                    "total_runs": tot_runs,
                    "total_wickets": tot_wickets,
                    "legal_balls_bowled": legal_balls,
                    "overs": _overs_string(legal_balls),
                    "run_rate": run_rate,
                    "is_super_over": is_so,
                    "target_runs": target_runs,
                    "batting": batting_list,
                    "bowling": bowling_list,
                    "extras": extras_dict,
                }

                if is_so:
                    super_overs.append(innings_obj)
                else:
                    regular_innings.append(innings_obj)

    return {
        "match": match_info,
        "has_super_over": has_super_over or match_info["result"]["is_super_over"],
        "innings": regular_innings,
        "super_overs": super_overs,
    }


def get_match_wickets(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve chronological fall-of-wickets details for all innings of a match.
    Separates regular innings and Super Overs.
    Computes running cumulative team runs and legal balls bowled at each dismissal.
    """
    if not isinstance(match_id, int) or isinstance(match_id, bool) or match_id <= 0:
        raise ValueError("A valid positive integer match ID is required.")

    query_check = "SELECT 1 FROM matches WHERE match_id = %s;"
    query_innings = """
        SELECT
            i.innings_id,
            i.innings_number,
            bt.team_id AS batting_team_id,
            bt.canonical_name AS batting_team,
            i.is_super_over,
            i.total_runs,
            i.total_wickets
        FROM innings i
        JOIN teams bt ON bt.team_id = i.batting_team_id
        WHERE i.match_id = %s
        ORDER BY i.innings_number ASC;
    """

    query_wickets = """
        WITH delivery_running AS (
            SELECT
                d.innings_id,
                d.delivery_id,
                d.over_number,
                d.delivery_sequence,
                d.bowler_id,
                d.bowler_name,
                SUM(d.total_runs) OVER (
                    PARTITION BY d.innings_id
                    ORDER BY d.over_number, d.delivery_sequence
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS score,
                COUNT(*) FILTER (WHERE d.is_legal_ball = TRUE) OVER (
                    PARTITION BY d.innings_id
                    ORDER BY d.over_number, d.delivery_sequence
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS legal_balls
            FROM deliveries d
            WHERE d.match_id = %s
        )
        SELECT
            dr.innings_id,
            ROW_NUMBER() OVER (
                PARTITION BY dr.innings_id
                ORDER BY dr.over_number, dr.delivery_sequence, w.wicket_id
            ) AS wicket_number,
            w.player_dismissed_id AS player_id,
            w.player_dismissed_name AS player_name,
            w.dismissal_kind,
            dr.bowler_id,
            dr.bowler_name,
            w.fielders,
            dr.score,
            dr.legal_balls,
            dr.over_number,
            dr.delivery_sequence
        FROM delivery_wickets w
        JOIN delivery_running dr ON dr.delivery_id = w.delivery_id
        WHERE w.match_id = %s
        ORDER BY dr.innings_id, dr.over_number, dr.delivery_sequence, w.wicket_id;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query_check, (match_id,))
            if not cur.fetchone():
                return None

            cur.execute(query_innings, (match_id,))
            innings_rows = cur.fetchall()

            cur.execute(query_wickets, (match_id, match_id))
            wicket_rows = cur.fetchall()

    wickets_by_innings: Dict[int, List[Dict[str, Any]]] = {}
    for w in wicket_rows:
        inn_id = w[0]
        fielders_list = w[7] if isinstance(w[7], list) else []
        legal_b = w[9]
        w_dict = {
            "wicket_number": w[1],
            "player_id": w[2],
            "player_name": w[3],
            "dismissal_kind": w[4],
            "bowler_id": w[5],
            "bowler_name": w[6],
            "fielders": fielders_list,
            "score": w[8],
            "overs": _overs_string(legal_b),
            "over_number": w[10],
            "delivery_sequence": w[11],
        }
        wickets_by_innings.setdefault(inn_id, []).append(w_dict)

    regular_innings = []
    super_overs = []
    has_super_over = False

    for inn in innings_rows:
        inn_id, inn_num, bat_id, bat_name, is_so, tot_runs, tot_wickets = inn
        if is_so:
            has_super_over = True
        inn_obj = {
            "innings_id": inn_id,
            "innings_number": inn_num,
            "batting_team_id": bat_id,
            "batting_team": bat_name,
            "is_super_over": is_so,
            "total_runs": tot_runs,
            "total_wickets": tot_wickets,
            "fall_of_wickets": wickets_by_innings.get(inn_id, []),
        }
        if is_so:
            super_overs.append(inn_obj)
        else:
            regular_innings.append(inn_obj)

    return {
        "match_id": match_id,
        "has_super_over": has_super_over,
        "innings": regular_innings,
        "super_overs": super_overs,
    }
