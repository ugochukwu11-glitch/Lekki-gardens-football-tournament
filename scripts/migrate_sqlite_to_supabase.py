from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from supabase import create_client


BASE_DIR = Path(__file__).resolve().parents[1]
SQLITE_DB_PATH = BASE_DIR / "data" / "tournament.db"


def main() -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")

    if not SQLITE_DB_PATH.exists():
        raise SystemExit(f"SQLite database not found at {SQLITE_DB_PATH}")

    client = create_client(supabase_url, supabase_key)
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        settings = [dict(row) for row in conn.execute("SELECT key, value FROM settings").fetchall()]
        rules = [dict(row) for row in conn.execute("SELECT key, value, description FROM qualification_rules").fetchall()]
        teams = [dict(row) for row in conn.execute("SELECT * FROM teams ORDER BY sort_order ASC").fetchall()]
        players = [dict(row) for row in conn.execute("SELECT * FROM players ORDER BY team_id, slot_number ASC").fetchall()]
        fixtures = [dict(row) for row in conn.execute("SELECT * FROM fixtures ORDER BY kickoff_at ASC").fetchall()]

    client.table("fixtures").delete().gte("id", 0).execute()
    client.table("players").delete().gte("id", 0).execute()
    client.table("teams").delete().gte("id", 0).execute()
    client.table("qualification_rules").delete().neq("key", "__never__").execute()
    client.table("settings").delete().neq("key", "__never__").execute()

    if settings:
        client.table("settings").insert(settings).execute()
    if rules:
        client.table("qualification_rules").insert(rules).execute()
    if teams:
        client.table("teams").insert(teams).execute()
    if players:
        client.table("players").insert(players).execute()
    if fixtures:
        client.table("fixtures").insert(fixtures).execute()

    print("SQLite data migrated to Supabase.")


if __name__ == "__main__":
    main()
