from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from storage import get_store


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tournament.db"

APP_TITLE = "LEKKI GARDENS PH1 ESTATE FOOTBALL TOURNAMENT"
APP_SUBTITLE = "Live fixtures and standings."
DEFAULT_ADMIN_CODE = os.environ.get("ADMIN_CODE", "LGPH1-ADMIN")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "lekki-gardens-ph1-secret")
PITCH_NAME = "Lekki Gardens PH1 Pitch"

TEAMS_SEED = [
    {
        "name": "CP FC",
        "short_name": "CP",
        "primary_color": "#d7263d",
        "secondary_color": "#141414",
        "logo_kind": "shield",
        "players": ["C P", "Solomon", "Check Up", "Sammy", "Daniel", "Cheatanna"],
    },
    {
        "name": "P MONEY FC",
        "short_name": "PM",
        "primary_color": "#d4af37",
        "secondary_color": "#111111",
        "logo_kind": "bolt",
        "players": ["HDT", "YG", "Ugunna", "P Money", "Dennis", "Akpanya"],
    },
    {
        "name": "YOLOS FC",
        "short_name": "YO",
        "primary_color": "#13b8a6",
        "secondary_color": "#0b1320",
        "logo_kind": "hex",
        "players": ["Chika", "Hustle", "Steven", "Vardy", "Kante", "Ikenna"],
    },
    {
        "name": "H.I REAL ESTATE FC",
        "short_name": "HI",
        "primary_color": "#4f46e5",
        "secondary_color": "#111111",
        "logo_kind": "diamond",
        "players": ["Mr Henry", "Mr Muri", "Mr Denis", "Mr Okikiola", "", ""],
    },
    {
        "name": "ASIAMONEY FC",
        "short_name": "AM",
        "primary_color": "#8b5cf6",
        "secondary_color": "#151515",
        "logo_kind": "star",
        "players": ["Shedi", "Paul", "Ekom", "Gotze", "", ""],
    },
    {
        "name": "KELVIN FC",
        "short_name": "KF",
        "primary_color": "#10b981",
        "secondary_color": "#0e1116",
        "logo_kind": "circle",
        "players": ["Mr Kelvin", "Mr Mofe", "Mr OBO", "Mr Pato", "", ""],
    },
]

DEFAULT_RULES = {
    "qualify_spots": 4,
    "eliminate_spots": 2,
}


STORE = get_store()


def make_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = FLASK_SECRET_KEY

    @app.before_request
    def ensure_db() -> None:
        init_database()

    @app.get("/")
    def index():
        state = build_state()
        return render_template(
            "index.html",
            title=APP_TITLE,
            subtitle=APP_SUBTITLE,
            state=state,
            admin_unlocked=session.get("admin_unlocked", False),
        )

    @app.get("/api/state")
    def api_state():
        return jsonify(build_state())

    @app.post("/api/admin/unlock")
    def admin_unlock():
        payload = request.get_json(silent=True) or {}
        code = str(payload.get("code", "")).strip()
        if code and code == DEFAULT_ADMIN_CODE:
            session["admin_unlocked"] = True
            return jsonify({"ok": True})
        return jsonify({"ok": False, "message": "Invalid admin code"}), 403

    @app.post("/api/admin/lock")
    def admin_lock():
        session["admin_unlocked"] = False
        return jsonify({"ok": True})

    @app.post("/admin/save")
    def admin_save():
        if not session.get("admin_unlocked"):
            return jsonify({"ok": False, "message": "Admin access required"}), 403
        STORE.save_from_form(request.form)
        return redirect(url_for("index"))

    return app


app = make_app()


def init_database() -> None:
    STORE.bootstrap()


def seed_database(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM players")
    conn.execute("DELETE FROM fixtures")
    conn.execute("DELETE FROM teams")
    conn.execute("DELETE FROM settings")
    conn.execute("DELETE FROM qualification_rules")

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("schedule_summary", "Weekends, 3:00 PM / 4:30 PM / 6:00 PM kickoff windows"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("match_length", "70 minutes of play + 20 minutes turnaround"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("venue_name", PITCH_NAME),
    )

    conn.executemany(
        "INSERT INTO qualification_rules (key, value, description) VALUES (?, ?, ?)",
        [
            ("qualify_spots", str(DEFAULT_RULES["qualify_spots"]), "Top four teams qualify for the next stage."),
            ("eliminate_spots", str(DEFAULT_RULES["eliminate_spots"]), "Bottom two teams are eliminated in this simulation."),
        ],
    )

    team_ids: list[int] = []
    for sort_order, team in enumerate(TEAMS_SEED, start=1):
        cursor = conn.execute(
            """
            INSERT INTO teams (name, short_name, primary_color, secondary_color, logo_kind, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                team["name"],
                team["short_name"],
                team["primary_color"],
                team["secondary_color"],
                team["logo_kind"],
                sort_order,
            ),
        )
        team_id = int(cursor.lastrowid)
        team_ids.append(team_id)
        for slot_number in range(1, 7):
            player_name = team["players"][slot_number - 1] if slot_number - 1 < len(team["players"]) else ""
            conn.execute(
                """
                INSERT INTO players (team_id, slot_number, name, is_empty)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, slot_number, player_name.strip(), 0 if player_name.strip() else 1),
            )

    fixtures = build_round_robin_schedule(team_ids)
    for fixture in fixtures:
        conn.execute(
            """
            INSERT INTO fixtures (
                round_number, match_number, kickoff_at, venue, home_team_id, away_team_id, home_score, away_score, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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


def build_round_robin_schedule(team_ids: list[int]) -> list[dict]:
    ids = team_ids[:]
    if len(ids) % 2:
        ids.append(None)

    rounds = len(ids) - 1
    half = len(ids) // 2
    rotation = ids[:]
    start_date = next_saturday(datetime.now())
    kickoff_times = [(15, 0), (16, 30), (18, 0)]
    fixtures: list[dict] = []
    match_count = 1

    for round_number in range(1, rounds + 1):
        left = rotation[:half]
        right = list(reversed(rotation[half:]))
        match_date = start_date + timedelta(days=(round_number - 1) * 7)

        for match_number, (home_id, away_id) in enumerate(zip(left, right), start=1):
            if home_id is None or away_id is None:
                continue
            if round_number % 2 == 0:
                home_id, away_id = away_id, home_id
            hour, minute = kickoff_times[match_number - 1]
            kickoff = match_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            fixtures.append(
                {
                    "round_number": round_number,
                    "match_number": match_count,
                    "kickoff_at": kickoff.isoformat(timespec="minutes"),
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                }
            )
            match_count += 1

        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    return fixtures


def next_saturday(dt: datetime) -> datetime:
    days_ahead = (5 - dt.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (dt + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)


def table_has_rows(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone()
    return row is not None


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def fetch_rules(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value, description FROM qualification_rules").fetchall()
    return {
        row["key"]: row["value"] if row["value"] is not None else ""
        for row in rows
    } | {"_descriptions": {row["key"]: row["description"] for row in rows}}


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
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-label="{team['name']} logo">
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
      <text x="120" y="196" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="28" font-weight="700" letter-spacing="2">{monogram}</text>
    </svg>
    """
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def fetch_teams(conn: sqlite3.Connection) -> list[dict]:
    teams = conn.execute(
        "SELECT id, name, short_name, primary_color, secondary_color, logo_kind, sort_order FROM teams ORDER BY sort_order ASC"
    ).fetchall()
    result: list[dict] = []
    for team in teams:
        players = conn.execute(
            """
            SELECT slot_number, name, is_empty
            FROM players
            WHERE team_id = ?
            ORDER BY slot_number ASC
            """,
            (team["id"],),
        ).fetchall()
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
                    for player in players
                ],
            }
        )
    return result


def fetch_fixtures(conn: sqlite3.Connection) -> list[dict]:
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

    fixtures: list[dict] = []
    for row in rows:
        kickoff = datetime.fromisoformat(row["kickoff_at"])
        fixtures.append(
            {
                "id": row["id"],
                "round_number": row["round_number"],
                "match_number": row["match_number"],
                "kickoff_at": row["kickoff_at"],
                "kickoff_label": kickoff.strftime("%a %d %b, %I:%M %p"),
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


def build_state() -> dict:
    return STORE.fetch_state()


def save_teams_from_form(conn: sqlite3.Connection, form: dict) -> None:
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


def save_fixtures_from_form(conn: sqlite3.Connection, form: dict) -> None:
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8502)), debug=False, use_reloader=False)
