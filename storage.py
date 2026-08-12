from __future__ import annotations

import base64
import html
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from supabase import Client, create_client

from seed_data import APP_SUBTITLE, APP_TITLE, DEFAULT_RULES, DEFAULT_SETTINGS, PITCH_NAME, TEAMS_SEED, build_round_robin_schedule


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SQLITE_DB_PATH = DATA_DIR / "tournament.db"


def logo_svg(team: dict) -> str:
    primary = team["primary_color"]
    secondary = team["secondary_color"]
    kind = team["logo_kind"]
    monogram = team["short_name"]

    if kind == "shield":
        shape = '<path d="M120 14 L198 47 L214 127 L177 202 L120 226 L63 202 L26 127 L42 47 Z" />'
        inner = '<path d="M120 40 L170 62 L183 116 L158 160 L120 176 L82 160 L57 116 L70 62 Z" opacity="0.18" />'
    elif kind == "bolt":
        shape = '<path d="M104 18 L169 18 L131 96 L183 96 L98 226 L118 140 L72 140 Z" />'
        inner = '<path d="M109 35 L150 35 L122 88 L160 88 L104 182 L118 126 L83 126 Z" opacity="0.18" />'
    elif kind == "hex":
        shape = '<path d="M75 30 L165 30 L210 120 L165 210 L75 210 L30 120 Z" />'
        inner = '<path d="M75 52 L150 52 L187 120 L150 188 L75 188 L38 120 Z" opacity="0.18" />'
    elif kind == "diamond":
        shape = '<path d="M120 18 L214 120 L120 222 L26 120 Z" />'
        inner = '<path d="M120 48 L186 120 L120 192 L54 120 Z" opacity="0.18" />'
    elif kind == "star":
        shape = '<path d="M120 18 L144 77 L208 79 L158 118 L176 181 L120 145 L64 181 L82 118 L32 79 L96 77 Z" />'
        inner = '<path d="M120 42 L136 84 L180 86 L146 112 L158 156 L120 133 L82 156 L94 112 L60 86 L104 84 Z" opacity="0.18" />'
    else:
        shape = '<circle cx="120" cy="120" r="102" />'
        inner = '<circle cx="120" cy="120" r="72" opacity="0.18" />'

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-label="{html.escape(team['name'])} logo">
      <defs>
        <linearGradient id="grad-{team['id']}" x1="16" y1="18" x2="220" y2="224" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="{primary}"/>
          <stop offset="100%" stop-color="{secondary}"/>
        </linearGradient>
      </defs>
      <g fill="url(#grad-{team['id']})" stroke="#0b0b0b" stroke-width="6" stroke-linejoin="round">
        {shape}
      </g>
      <g fill="#ffffff" opacity="0.88">
        {inner}
      </g>
      <circle cx="120" cy="104" r="24" fill="#ffffff" opacity="0.95" />
      <path d="M120 86 L128 98 L123 112 L117 112 L112 98 Z" fill="#0b0b0b" opacity="0.88" />
      <text x="120" y="196" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="28" font-weight="700" letter-spacing="2">{html.escape(monogram)}</text>
    </svg>
    """
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def format_kickoff_label(raw_value: str) -> str:
    kickoff = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    return kickoff.strftime("%a %d %b, %I:%M %p")


def compute_standings(teams: list[dict], fixtures: list[dict]) -> list[dict]:
    stats = {
        team["id"]: {
            "team_id": team["id"],
            "name": team["name"],
            "short_name": team["short_name"],
            "primary_color": team["primary_color"],
            "secondary_color": team["secondary_color"],
            "logo_kind": team["logo_kind"],
            "logo_uri": team["logo_uri"],
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
            "remaining": 0,
            "status": "In contention",
        }
        for team in teams
    }

    for fixture in fixtures:
        home = stats[fixture["home_team"]["id"]]
        away = stats[fixture["away_team"]["id"]]
        if fixture["played"]:
            hs = int(fixture["home_score"])
            as_ = int(fixture["away_score"])
            home["played"] += 1
            away["played"] += 1
            home["gf"] += hs
            home["ga"] += as_
            away["gf"] += as_
            away["ga"] += hs
            if hs > as_:
                home["won"] += 1
                away["lost"] += 1
                home["points"] += 3
            elif as_ > hs:
                away["won"] += 1
                home["lost"] += 1
                away["points"] += 3
            else:
                home["drawn"] += 1
                away["drawn"] += 1
                home["points"] += 1
                away["points"] += 1
        else:
            home["remaining"] += 1
            away["remaining"] += 1

    standings = list(stats.values())
    for row in standings:
        row["gd"] = row["gf"] - row["ga"]

    standings.sort(key=lambda row: (-row["points"], -row["gd"], -row["gf"], row["name"]))

    if len(standings) >= 5:
        fifth_max_points = standings[4]["points"] + standings[4]["remaining"] * 3
        cutoff_points = standings[3]["points"]
        for row in standings:
            max_possible = row["points"] + row["remaining"] * 3
            if max_possible < cutoff_points:
                row["status"] = "Eliminated"
            elif row["points"] > fifth_max_points and standings.index(row) < 4:
                row["status"] = "Qualified"
            else:
                row["status"] = "In contention"
    else:
        for row in standings:
            row["status"] = "In contention"

    for rank, row in enumerate(standings, start=1):
        row["rank"] = rank
    return standings


def make_state(teams: list[dict], fixtures: list[dict]) -> dict:
    standings = compute_standings(teams, fixtures)
    upcoming = [fixture for fixture in fixtures if not fixture["played"]]
    latest_result = next((fixture for fixture in reversed(fixtures) if fixture["played"]), None)
    next_fixture = upcoming[0] if upcoming else None
    completed = [fixture for fixture in fixtures if fixture["played"]]

    return {
        "title": APP_TITLE,
        "subtitle": APP_SUBTITLE,
        "settings": DEFAULT_SETTINGS,
        "rules": DEFAULT_RULES,
        "teams": teams,
        "fixtures": fixtures,
        "upcoming_fixtures": upcoming,
        "latest_result": latest_result,
        "next_fixture": next_fixture,
        "standings": standings,
        "summary": {
            "teams": len(teams),
            "players": sum(1 for team in teams for player in team["players"] if not player["is_empty"]),
            "empty_slots": sum(1 for team in teams for player in team["players"] if player["is_empty"]),
            "completed_matches": len(completed),
            "total_matches": len(fixtures),
        },
    }


@dataclass
class SQLiteStore:
    db_path: Path = SQLITE_DB_PATH

    def bootstrap(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qualification_rules (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    short_name TEXT NOT NULL,
                    primary_color TEXT NOT NULL,
                    secondary_color TEXT NOT NULL,
                    logo_kind TEXT NOT NULL,
                    sort_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                    slot_number INTEGER NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    is_empty INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(team_id, slot_number)
                );

                CREATE TABLE IF NOT EXISTS fixtures (
                    id INTEGER PRIMARY KEY,
                    round_number INTEGER NOT NULL,
                    match_number INTEGER NOT NULL,
                    kickoff_at TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    home_team_id INTEGER NOT NULL REFERENCES teams(id),
                    away_team_id INTEGER NOT NULL REFERENCES teams(id),
                    home_score INTEGER,
                    away_score INTEGER,
                    status TEXT NOT NULL DEFAULT 'Scheduled'
                );
                """
            )
            if not self._has_rows(conn, "teams"):
                self._seed_sqlite(conn)

    def _has_rows(self, conn: sqlite3.Connection, table_name: str) -> bool:
        return conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone() is not None

    def _seed_sqlite(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM players")
        conn.execute("DELETE FROM fixtures")
        conn.execute("DELETE FROM teams")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM qualification_rules")

        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

        conn.executemany(
            "INSERT INTO qualification_rules (key, value, description) VALUES (?, ?, ?)",
            [
                ("qualify_spots", str(DEFAULT_RULES["qualify_spots"]), "Top four teams qualify for the next stage."),
                ("eliminate_spots", str(DEFAULT_RULES["eliminate_spots"]), "Bottom two teams are eliminated in this simulation."),
            ],
        )

        for sort_order, team in enumerate(TEAMS_SEED, start=1):
            conn.execute(
                """
                INSERT INTO teams (id, name, short_name, primary_color, secondary_color, logo_kind, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team["id"],
                    team["name"],
                    team["short_name"],
                    team["primary_color"],
                    team["secondary_color"],
                    team["logo_kind"],
                    sort_order,
                ),
            )
            for slot_number, player_name in enumerate(team["players"], start=1):
                conn.execute(
                    """
                    INSERT INTO players (team_id, slot_number, name, is_empty)
                    VALUES (?, ?, ?, ?)
                    """,
                    (team["id"], slot_number, player_name.strip(), 0 if player_name.strip() else 1),
                )

        for fixture in build_round_robin_schedule([team["id"] for team in TEAMS_SEED]):
            conn.execute(
                """
                INSERT INTO fixtures (
                    id, round_number, match_number, kickoff_at, venue, home_team_id, away_team_id, home_score, away_score, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fixture["match_number"],
                    fixture["round_number"],
                    fixture["match_number"],
                    fixture["kickoff_at"],
                    PITCH_NAME,
                    fixture["home_team_id"],
                    fixture["away_team_id"],
                    None,
                    None,
                    "Scheduled",
                ),
            )

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def fetch_state(self) -> dict:
        with self.connect() as conn:
            settings = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM settings")}
            rules = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value, description FROM qualification_rules")
            }
            teams = self._fetch_teams_sqlite(conn)
            fixtures = self._fetch_fixtures_sqlite(conn)
        state = make_state(teams, fixtures)
        state["settings"] = settings
        state["rules"] = {
            "qualify_spots": rules.get("qualify_spots", str(DEFAULT_RULES["qualify_spots"])),
            "eliminate_spots": rules.get("eliminate_spots", str(DEFAULT_RULES["eliminate_spots"])),
        }
        return state

    def _fetch_teams_sqlite(self, conn: sqlite3.Connection) -> list[dict]:
        teams_rows = conn.execute(
            "SELECT id, name, short_name, primary_color, secondary_color, logo_kind, sort_order FROM teams ORDER BY sort_order ASC"
        ).fetchall()
        result = []
        for team in teams_rows:
            players = conn.execute(
                "SELECT slot_number, name, is_empty FROM players WHERE team_id = ? ORDER BY slot_number ASC",
                (team["id"],),
            ).fetchall()
            team_dict = {
                "id": team["id"],
                "name": team["name"],
                "short_name": team["short_name"],
                "primary_color": team["primary_color"],
                "secondary_color": team["secondary_color"],
                "logo_kind": team["logo_kind"],
                "logo_uri": logo_svg(team),
                "players": [
                    {
                        "slot_number": player["slot_number"],
                        "name": player["name"],
                        "is_empty": bool(player["is_empty"]),
                    }
                    for player in players
                ],
            }
            result.append(team_dict)
        return result

    def _fetch_fixtures_sqlite(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """
            SELECT
                f.id,
                f.round_number,
                f.match_number,
                f.kickoff_at,
                f.venue,
                f.home_team_id,
                f.away_team_id,
                f.home_score,
                f.away_score,
                f.status,
                ht.name AS home_team_name,
                ht.short_name AS home_short_name,
                ht.primary_color AS home_primary_color,
                ht.secondary_color AS home_secondary_color,
                ht.logo_kind AS home_logo_kind,
                at.name AS away_team_name,
                at.short_name AS away_short_name,
                at.primary_color AS away_primary_color,
                at.secondary_color AS away_secondary_color,
                at.logo_kind AS away_logo_kind
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            ORDER BY f.kickoff_at ASC
            """
        ).fetchall()
        return self._shape_fixtures(rows)

    def _shape_fixtures(self, rows) -> list[dict]:
        fixtures = []
        for row in rows:
            fixtures.append(
                {
                    "id": row["id"],
                    "round_number": row["round_number"],
                    "match_number": row["match_number"],
                    "kickoff_at": row["kickoff_at"],
                    "kickoff_label": format_kickoff_label(row["kickoff_at"]),
                    "venue": row["venue"],
                    "status": row["status"],
                    "home_score": row["home_score"],
                    "away_score": row["away_score"],
                    "home_team": {
                        "id": row["home_team_id"],
                        "name": row["home_team_name"],
                        "short_name": row["home_short_name"],
                        "primary_color": row["home_primary_color"],
                        "secondary_color": row["home_secondary_color"],
                        "logo_kind": row["home_logo_kind"],
                        "logo_uri": logo_svg(
                            {
                                "id": row["home_team_id"],
                                "name": row["home_team_name"],
                                "short_name": row["home_short_name"],
                                "primary_color": row["home_primary_color"],
                                "secondary_color": row["home_secondary_color"],
                                "logo_kind": row["home_logo_kind"],
                            }
                        ),
                    },
                    "away_team": {
                        "id": row["away_team_id"],
                        "name": row["away_team_name"],
                        "short_name": row["away_short_name"],
                        "primary_color": row["away_primary_color"],
                        "secondary_color": row["away_secondary_color"],
                        "logo_kind": row["away_logo_kind"],
                        "logo_uri": logo_svg(
                            {
                                "id": row["away_team_id"],
                                "name": row["away_team_name"],
                                "short_name": row["away_short_name"],
                                "primary_color": row["away_primary_color"],
                                "secondary_color": row["away_secondary_color"],
                                "logo_kind": row["away_logo_kind"],
                            }
                        ),
                    },
                    "played": row["home_score"] is not None and row["away_score"] is not None,
                }
            )
        return fixtures

    def save_from_form(self, form) -> None:
        with self.connect() as conn:
            team_ids = [row["id"] for row in conn.execute("SELECT id FROM teams ORDER BY sort_order ASC").fetchall()]
            for team_id in team_ids:
                name = (form.get(f"team_name_{team_id}") or "").strip()
                short_name = (form.get(f"team_short_{team_id}") or "").strip().upper()
                primary_color = (form.get(f"team_primary_{team_id}") or "").strip()
                secondary_color = (form.get(f"team_secondary_{team_id}") or "").strip()
                logo_kind = (form.get(f"team_logo_{team_id}") or "").strip()
                conn.execute(
                    """
                    UPDATE teams
                    SET name = ?, short_name = ?, primary_color = ?, secondary_color = ?, logo_kind = ?
                    WHERE id = ?
                    """,
                    (
                        name or "Untitled FC",
                        short_name or "FC",
                        primary_color or "#111111",
                        secondary_color or "#444444",
                        logo_kind or "shield",
                        team_id,
                    ),
                )
                for slot in range(1, 7):
                    player_name = (form.get(f"player_{team_id}_{slot}") or "").strip()
                    conn.execute(
                        """
                        UPDATE players
                        SET name = ?, is_empty = ?
                        WHERE team_id = ? AND slot_number = ?
                        """,
                        (player_name, 0 if player_name else 1, team_id, slot),
                    )

            fixture_ids = [row["id"] for row in conn.execute("SELECT id FROM fixtures ORDER BY kickoff_at ASC").fetchall()]
            for fixture_id in fixture_ids:
                home_score_raw = (form.get(f"home_score_{fixture_id}") or "").strip()
                away_score_raw = (form.get(f"away_score_{fixture_id}") or "").strip()
                status = (form.get(f"status_{fixture_id}") or "Scheduled").strip() or "Scheduled"
                home_score = int(home_score_raw) if home_score_raw.isdigit() else None
                away_score = int(away_score_raw) if away_score_raw.isdigit() else None
                conn.execute(
                    """
                    UPDATE fixtures
                    SET home_score = ?, away_score = ?, status = ?
                    WHERE id = ?
                    """,
                    (home_score, away_score, status, fixture_id),
                )


class SupabaseStore:
    def __init__(self, url: str, service_key: str) -> None:
        self.client: Client = create_client(url, service_key)

    def bootstrap(self) -> None:
        try:
            teams = self.client.table("teams").select("id").limit(1).execute().data or []
        except Exception as exc:
            raise RuntimeError(
                "Supabase tables are missing. Run supabase/schema.sql in the Supabase SQL editor first."
            ) from exc

        if teams:
            return

        self._seed_supabase()

    def _seed_supabase(self) -> None:
        self.client.table("settings").upsert(
            [{"key": key, "value": value} for key, value in DEFAULT_SETTINGS.items()]
        ).execute()
        self.client.table("qualification_rules").upsert(
            [
                {
                    "key": "qualify_spots",
                    "value": str(DEFAULT_RULES["qualify_spots"]),
                    "description": "Top four teams qualify for the next stage.",
                },
                {
                    "key": "eliminate_spots",
                    "value": str(DEFAULT_RULES["eliminate_spots"]),
                    "description": "Bottom two teams are eliminated in this simulation.",
                },
            ]
        ).execute()

        for sort_order, team in enumerate(TEAMS_SEED, start=1):
            self.client.table("teams").upsert(
                [
                    {
                        "id": team["id"],
                        "name": team["name"],
                        "short_name": team["short_name"],
                        "primary_color": team["primary_color"],
                        "secondary_color": team["secondary_color"],
                        "logo_kind": team["logo_kind"],
                        "sort_order": sort_order,
                    }
                ]
            ).execute()
            for slot_number, player_name in enumerate(team["players"], start=1):
                self.client.table("players").upsert(
                    [
                        {
                            "team_id": team["id"],
                            "slot_number": slot_number,
                            "name": player_name.strip(),
                            "is_empty": not bool(player_name.strip()),
                        }
                    ]
                ).execute()

        for fixture in build_round_robin_schedule([team["id"] for team in TEAMS_SEED]):
            self.client.table("fixtures").upsert(
                [
                    {
                        "id": fixture["match_number"],
                        "round_number": fixture["round_number"],
                        "match_number": fixture["match_number"],
                        "kickoff_at": fixture["kickoff_at"],
                        "venue": PITCH_NAME,
                        "home_team_id": fixture["home_team_id"],
                        "away_team_id": fixture["away_team_id"],
                        "home_score": None,
                        "away_score": None,
                        "status": "Scheduled",
                    }
                ]
            ).execute()

    def fetch_state(self) -> dict:
        settings_rows = self.client.table("settings").select("*").execute().data or []
        rules_rows = self.client.table("qualification_rules").select("*").execute().data or []
        teams_rows = self.client.table("teams").select("*").order("sort_order").execute().data or []
        players_rows = self.client.table("players").select("*").order("slot_number").execute().data or []
        fixtures_rows = self.client.table("fixtures").select("*").order("kickoff_at").execute().data or []

        settings = {row["key"]: row["value"] for row in settings_rows}
        rules = {row["key"]: row["value"] for row in rules_rows}
        teams = self._shape_teams(teams_rows, players_rows)
        fixtures = self._shape_fixtures(fixtures_rows, teams)

        state = make_state(teams, fixtures)
        state["settings"] = settings
        state["rules"] = {
            "qualify_spots": rules.get("qualify_spots", str(DEFAULT_RULES["qualify_spots"])),
            "eliminate_spots": rules.get("eliminate_spots", str(DEFAULT_RULES["eliminate_spots"])),
        }
        return state

    def _shape_teams(self, teams_rows, players_rows) -> list[dict]:
        result = []
        grouped = {}
        for player in players_rows:
            grouped.setdefault(player["team_id"], []).append(player)

        for team in teams_rows:
            players = grouped.get(team["id"], [])
            result.append(
                {
                    "id": team["id"],
                    "name": team["name"],
                    "short_name": team["short_name"],
                    "primary_color": team["primary_color"],
                    "secondary_color": team["secondary_color"],
                    "logo_kind": team["logo_kind"],
                    "logo_uri": logo_svg(team),
                    "players": [
                        {
                            "slot_number": player["slot_number"],
                            "name": player["name"],
                            "is_empty": bool(player["is_empty"]),
                        }
                        for player in sorted(players, key=lambda item: item["slot_number"])
                    ],
                }
            )
        return result

    def _shape_fixtures(self, fixtures_rows, teams) -> list[dict]:
        team_map = {team["id"]: team for team in teams}
        fixtures = []
        for row in fixtures_rows:
            kickoff = row["kickoff_at"]
            fixtures.append(
                {
                    "id": row["id"],
                    "round_number": row["round_number"],
                    "match_number": row["match_number"],
                    "kickoff_at": kickoff,
                    "kickoff_label": format_kickoff_label(kickoff),
                    "venue": row["venue"],
                    "status": row["status"],
                    "home_score": row["home_score"],
                    "away_score": row["away_score"],
                    "home_team": team_map[row["home_team_id"]],
                    "away_team": team_map[row["away_team_id"]],
                    "played": row["home_score"] is not None and row["away_score"] is not None,
                }
            )
        return fixtures

    def save_from_form(self, form) -> None:
        teams_rows = self.client.table("teams").select("id").order("sort_order").execute().data or []
        for team in teams_rows:
            team_id = team["id"]
            name = (form.get(f"team_name_{team_id}") or "").strip()
            short_name = (form.get(f"team_short_{team_id}") or "").strip().upper()
            primary_color = (form.get(f"team_primary_{team_id}") or "").strip()
            secondary_color = (form.get(f"team_secondary_{team_id}") or "").strip()
            logo_kind = (form.get(f"team_logo_{team_id}") or "").strip()
            self.client.table("teams").update(
                {
                    "name": name or "Untitled FC",
                    "short_name": short_name or "FC",
                    "primary_color": primary_color or "#111111",
                    "secondary_color": secondary_color or "#444444",
                    "logo_kind": logo_kind or "shield",
                }
            ).eq("id", team_id).execute()

            for slot in range(1, 7):
                player_name = (form.get(f"player_{team_id}_{slot}") or "").strip()
                self.client.table("players").update(
                    {"name": player_name, "is_empty": not bool(player_name)}
                ).eq("team_id", team_id).eq("slot_number", slot).execute()

        fixture_rows = self.client.table("fixtures").select("id").order("kickoff_at").execute().data or []
        for fixture in fixture_rows:
            fixture_id = fixture["id"]
            home_score_raw = (form.get(f"home_score_{fixture_id}") or "").strip()
            away_score_raw = (form.get(f"away_score_{fixture_id}") or "").strip()
            status = (form.get(f"status_{fixture_id}") or "Scheduled").strip() or "Scheduled"
            home_score = int(home_score_raw) if home_score_raw.isdigit() else None
            away_score = int(away_score_raw) if away_score_raw.isdigit() else None
            self.client.table("fixtures").update(
                {"home_score": home_score, "away_score": away_score, "status": status}
            ).eq("id", fixture_id).execute()


def get_store():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        return SupabaseStore(supabase_url, supabase_key)
    return SQLiteStore()
