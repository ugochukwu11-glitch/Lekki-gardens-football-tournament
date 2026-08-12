from __future__ import annotations

import base64
import hashlib
import html
import json
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st


APP_TITLE = "LEKKI GARDENS PH1 ESTATE FOOTBALL TOURNAMENT"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "tournament_state.json"


def get_admin_code() -> str:
    try:
        secret_code = st.secrets.get("admin_code", "")
    except Exception:
        secret_code = ""
    return str(secret_code or os.environ.get("ADMIN_CODE", "LGPH1-ADMIN"))


DEFAULT_SETTINGS = {
    "provisional_schedule": "Weekends, with 3:00 PM, 4:30 PM, and 6:00 PM kickoff windows",
    "match_length": "70 minutes of play + 20 minutes turnaround",
    "format": "Single round-robin league phase",
    "venue_note": "One pitch, three fixtures per matchday",
}


RAW_TEAMS = [
    {
        "name": "CP FC",
        "players": ["C P", "Solomon", "Check Up", "Sammy", "Daniel", "Cheatanna"],
    },
    {
        "name": "P MONEY FC",
        "players": ["HDT", "YG", "Ugunna", "P Money", "Dennis", "Akpanya"],
    },
    {
        "name": "YOLOS FC",
        "players": ["Chika", "Hustle", "Steven", "Vardy", "Kante", "Ikenna"],
    },
    {
        "name": "H.I REAL ESTATE FC",
        "players": ["Mr Henry", "Mr Muri", "Mr Denis", "Mr Okikiola", "Emma", "Daniel"],
    },
    {
        "name": "ASIAMONEY FC",
        "players": ["Shedi", "Paul", "Ekom", "Gotze", "Moris", "Asiamoney"],
    },
    {
        "name": "KELVIN FC",
        "players": ["Mr Kelvin", "Mr Mofe", "Mr OBO", "Mr Pato", "Mr Tmaxee", ""],
    },
]


LOGO_STYLES = [
    ("#0f0f10", "#4a4a4f", "#d7d7d9"),
    ("#141414", "#2f2f33", "#f0f0f0"),
    ("#222224", "#6b6b72", "#cfcfd3"),
    ("#18181b", "#44444a", "#ffffff"),
    ("#101012", "#39393f", "#dddddf"),
    ("#1b1b1e", "#58585f", "#f7f7f7"),
]


def normalize_team_name(value: str) -> str:
    cleaned = " ".join(str(value).replace("\n", " ").split())
    return cleaned.upper()


def initials(name: str) -> str:
    tokens = [part for part in normalize_team_name(name).split() if part.isalnum() or part.replace(".", "").isalnum()]
    picks = []
    for token in tokens:
        letters = "".join(ch for ch in token if ch.isalpha())
        if letters:
            picks.append(letters[0])
    joined = "".join(picks[:3])
    if not joined:
        joined = "FC"
    return joined[:3]


def stable_index(text: str, size: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % size


def build_logo_svg(team_name: str) -> str:
    primary, secondary, light = LOGO_STYLES[stable_index(team_name, len(LOGO_STYLES))]
    monogram = html.escape(initials(team_name))
    safe_name = html.escape(team_name)
    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-label="{safe_name}">
      <defs>
        <linearGradient id="g" x1="18" y1="18" x2="220" y2="220" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="{primary}"/>
          <stop offset="100%" stop-color="{secondary}"/>
        </linearGradient>
      </defs>
      <path d="M120 14 L197 47 L214 126 L176 201 L120 226 L64 201 L26 126 L43 47 Z" fill="url(#g)" stroke="#0a0a0a" stroke-width="7" />
      <path d="M120 38 L171 60 L183 114 L158 161 L120 177 L82 161 L57 114 L69 60 Z" fill="#111111" opacity="0.18" />
      <circle cx="120" cy="106" r="42" fill="none" stroke="{light}" stroke-width="8" />
      <circle cx="120" cy="106" r="16" fill="{light}" opacity="0.92" />
      <path d="M120 90 L129 98 L126 110 L114 110 L111 98 Z" fill="#111111" opacity="0.8" />
      <path d="M95 108 L104 101 L112 105 L108 115 L98 117 Z" fill="#111111" opacity="0.45" />
      <path d="M145 108 L136 101 L128 105 L132 115 L142 117 Z" fill="#111111" opacity="0.45" />
      <text x="120" y="196" text-anchor="middle" fill="{light}" font-family="Arial, sans-serif" font-size="28" font-weight="700" letter-spacing="2">{monogram}</text>
    </svg>
    """


def svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def logo_markup(team_name: str) -> str:
    return f"""
    <div class="crest-wrap">
      <img class="crest" src="{svg_data_uri(build_logo_svg(team_name))}" alt="{html.escape(team_name)} logo" />
    </div>
    """


def default_teams() -> list[dict]:
    teams = []
    for idx, raw in enumerate(RAW_TEAMS, start=1):
        team_id = f"team_{idx}"
        teams.append(
            {
                "id": team_id,
                "name": normalize_team_name(raw["name"]),
                "players": [str(player).strip() for player in raw["players"]],
            }
        )
    return teams


def default_state() -> dict:
    teams = default_teams()
    fixtures = build_fixtures(teams)
    return {
        "settings": deepcopy(DEFAULT_SETTINGS),
        "teams": teams,
        "fixtures": fixtures,
    }


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            with STATE_PATH.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict) and "teams" in loaded and "fixtures" in loaded:
                return loaded
        except Exception:
            pass
    return default_state()


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)


def build_fixtures(teams: list[dict]) -> list[dict]:
    team_ids = [team["id"] for team in teams]
    team_names = {team["id"]: team["name"] for team in teams}
    nodes = team_ids[:]
    if len(nodes) % 2:
        nodes.append(None)
    rounds = len(nodes) - 1
    half = len(nodes) // 2
    fixtures = []
    pair_counter = 1

    for round_number in range(1, rounds + 1):
        left = nodes[:half]
        right = list(reversed(nodes[half:]))
        for match_index, (home_id, away_id) in enumerate(zip(left, right), start=1):
            if home_id is None or away_id is None:
                continue
            if round_number % 2 == 0:
                home_id, away_id = away_id, home_id
            fixtures.append(
                {
                    "id": f"match_{pair_counter}",
                    "round": round_number,
                    "match_index": match_index,
                    "home_id": home_id,
                    "away_id": away_id,
                    "home": team_names[home_id],
                    "away": team_names[away_id],
                    "home_score": None,
                    "away_score": None,
                    "status": "Scheduled",
                }
            )
            pair_counter += 1
        nodes = [nodes[0]] + [nodes[-1]] + nodes[1:-1]

    return fixtures


def refresh_team_names(state: dict) -> None:
    mapping = {team["id"]: team["name"] for team in state["teams"]}
    for fixture in state["fixtures"]:
        fixture["home"] = mapping.get(fixture["home_id"], fixture["home"])
        fixture["away"] = mapping.get(fixture["away_id"], fixture["away"])


def coerce_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def coerce_int(value: object) -> int | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def team_dataframe(state: dict) -> pd.DataFrame:
    rows = []
    for team in state["teams"]:
        row = {"team_name": team["name"]}
        for idx in range(6):
            key = f"player_{idx + 1}"
            row[key] = team["players"][idx] if idx < len(team["players"]) else ""
        rows.append(row)
    return pd.DataFrame(rows)


def fixture_dataframe(state: dict) -> pd.DataFrame:
    rows = []
    for fixture in state["fixtures"]:
        rows.append(
            {
                "round": fixture["round"],
                "match": f"{fixture['home']} vs {fixture['away']}",
                "home_team": fixture["home"],
                "away_team": fixture["away"],
                "home_score": fixture["home_score"],
                "away_score": fixture["away_score"],
                "status": fixture["status"],
            }
        )
    return pd.DataFrame(rows)


def update_teams_from_editor(state: dict, edited_df: pd.DataFrame) -> None:
    updated = []
    for index, (_, row) in enumerate(edited_df.iterrows(), start=0):
        source_team = state["teams"][index]
        players = [coerce_text(row.get(f"player_{slot}")) for slot in range(1, 7)]
        updated.append(
            {
                "id": source_team["id"],
                "name": normalize_team_name(coerce_text(row.get("team_name")) or source_team["name"]),
                "players": players,
            }
        )
    state["teams"] = updated
    refresh_team_names(state)


def update_fixtures_from_editor(state: dict, edited_df: pd.DataFrame) -> None:
    for index, (_, row) in enumerate(edited_df.iterrows(), start=0):
        state["fixtures"][index]["home_score"] = coerce_int(row.get("home_score"))
        state["fixtures"][index]["away_score"] = coerce_int(row.get("away_score"))
        state["fixtures"][index]["status"] = coerce_text(row.get("status")) or "Scheduled"

        if state["fixtures"][index]["home_score"] is not None and state["fixtures"][index]["away_score"] is not None:
            if state["fixtures"][index]["status"] == "Scheduled":
                state["fixtures"][index]["status"] = "Played"


def compute_standings(state: dict) -> list[dict]:
    table = {
        team["id"]: {
            "team": team["name"],
            "pld": 0,
            "w": 0,
            "d": 0,
            "l": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "pts": 0,
        }
        for team in state["teams"]
    }

    for fixture in state["fixtures"]:
        home_score = fixture.get("home_score")
        away_score = fixture.get("away_score")
        if home_score is None or away_score is None:
            continue

        home = table[fixture["home_id"]]
        away = table[fixture["away_id"]]
        home["pld"] += 1
        away["pld"] += 1
        home["gf"] += home_score
        home["ga"] += away_score
        away["gf"] += away_score
        away["ga"] += home_score

        if home_score > away_score:
            home["w"] += 1
            away["l"] += 1
            home["pts"] += 3
        elif away_score > home_score:
            away["w"] += 1
            home["l"] += 1
            away["pts"] += 3
        else:
            home["d"] += 1
            away["d"] += 1
            home["pts"] += 1
            away["pts"] += 1

    rows = []
    for row in table.values():
        row["gd"] = row["gf"] - row["ga"]
        rows.append(row)

    rows.sort(key=lambda item: (-item["pts"], -item["gd"], -item["gf"], item["team"]))
    return rows


def make_schedule_note() -> str:
    return (
        "Suggested until the organizers confirm the final plan: "
        f"{DEFAULT_SETTINGS['provisional_schedule']}. "
        f"{DEFAULT_SETTINGS['match_length']}."
    )


def inject_styles() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

          html, body, [class*="st-"] {
            font-family: 'IBM Plex Sans', sans-serif;
          }

          .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2rem;
            max-width: 980px;
          }

          .app-shell {
            background: linear-gradient(180deg, #f7f7f7 0%, #ffffff 24%, #f2f2f2 100%);
            border: 1px solid #dedede;
            border-radius: 24px;
            padding: 1rem;
          }

          .hero-title {
            font-size: clamp(2rem, 6vw, 3.4rem);
            line-height: 1.02;
            letter-spacing: -0.04em;
            font-weight: 700;
            color: #111111;
            margin: 0;
          }

          .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: #6b6b6b;
            font-size: 0.78rem;
            margin-bottom: 0.45rem;
          }

          .hero-copy {
            color: #404040;
            max-width: 62ch;
            margin-top: 0.65rem;
            margin-bottom: 0;
          }

          .crest-wrap {
            width: 104px;
            height: 104px;
            margin-bottom: 0.65rem;
          }

          .crest {
            width: 100%;
            height: 100%;
            display: block;
            filter: drop-shadow(0 8px 18px rgba(0, 0, 0, 0.18));
          }

          .muted-card {
            border: 1px solid #d8d8d8;
            border-radius: 20px;
            padding: 0.9rem 1rem;
            background: linear-gradient(180deg, #ffffff 0%, #f7f7f7 100%);
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.04);
          }

          .label-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.25rem;
          }

          .team-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid #cdcdcd;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.8rem;
            color: #272727;
            background: #fbfbfb;
          }

          .player-list {
            margin-top: 0.5rem;
            display: grid;
            gap: 0.35rem;
          }

          .player-line {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            border-bottom: 1px dashed #dfdfdf;
            padding-bottom: 0.3rem;
          }

          .empty-spot {
            color: #8a8a8a;
            font-style: italic;
          }

          .fixture-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            border: 1px solid #cfcfcf;
            border-radius: 999px;
            padding: 0.28rem 0.7rem;
            color: #333333;
            background: #fafafa;
            margin-bottom: 0.45rem;
          }

          .score-box {
            border-radius: 16px;
            background: #111111;
            color: #ffffff;
            padding: 0.6rem 0.8rem;
            font-weight: 700;
            letter-spacing: 0.02em;
          }

          .subtle-rule {
            height: 1px;
            background: linear-gradient(90deg, rgba(17,17,17,0) 0%, rgba(17,17,17,0.12) 50%, rgba(17,17,17,0) 100%);
            margin: 1rem 0;
          }

          [data-testid="stMetricValue"] {
            color: #111111;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(state: dict, standings: list[dict]) -> None:
    total_players = sum(1 for team in state["teams"] for player in team["players"] if coerce_text(player))
    completed_matches = sum(1 for fixture in state["fixtures"] if fixture["home_score"] is not None and fixture["away_score"] is not None)
    total_matches = len(state["fixtures"])
    empty_slots = sum(1 for team in state["teams"] for player in team["players"] if not coerce_text(player))

    with st.container(border=True):
        st.markdown('<div class="hero-kicker">Estate football tournament</div>', unsafe_allow_html=True)
        st.markdown(f'<h1 class="hero-title">{html.escape(APP_TITLE)}</h1>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="hero-copy">A simple mobile-first dashboard for fixtures, team rosters, player registration, and match updates. '
            f'{html.escape(make_schedule_note())}</p>',
            unsafe_allow_html=True,
        )

        row1_col1, row1_col2 = st.columns(2, vertical_alignment="center")
        row1_col1.metric("Teams", len(state["teams"]))
        row1_col2.metric("Players listed", total_players)
        row2_col1, row2_col2 = st.columns(2, vertical_alignment="center")
        row2_col1.metric("Open spots", empty_slots)
        row2_col2.metric("Matches played", f"{completed_matches}/{total_matches}")

    top_team = standings[0] if standings else None
    if top_team:
        st.caption(f"Current table leader: {top_team['team']} on {top_team['pts']} points.")


def render_teams_view(state: dict) -> None:
    st.subheader("Teams and players")
    for team in state["teams"]:
        with st.container(border=True):
            st.markdown(logo_markup(team["name"]), unsafe_allow_html=True)
            roster_lines = []
            for index, player in enumerate(team["players"], start=1):
                display = coerce_text(player) or "Empty spot"
                class_name = "empty-spot" if display == "Empty spot" else ""
                roster_lines.append(
                    f'<div class="player-line"><span>Slot {index}</span><span class="{class_name}">{html.escape(display)}</span></div>'
                )

            team_html = f"""
            <h3 style="margin:0 0 0.35rem 0; color:#111111;">{html.escape(team['name'])}</h3>
            <div class="label-row">
              <span class="team-pill">6-player squad</span>
              <span class="team-pill">football crest</span>
            </div>
            <div class="player-list">
              {''.join(roster_lines)}
            </div>
            """
            st.markdown(team_html, unsafe_allow_html=True)


def render_fixtures_view(state: dict) -> None:
    st.subheader("Fixtures")
    rounds = sorted({fixture["round"] for fixture in state["fixtures"]})
    for round_number in rounds:
        matches = [fixture for fixture in state["fixtures"] if fixture["round"] == round_number]
        expanded = round_number == 1
        with st.expander(f"Round {round_number}", expanded=expanded):
            for fixture in matches:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="fixture-chip">Round {fixture["round"]} | '
                        f'{html.escape(DEFAULT_SETTINGS["provisional_schedule"])}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{html.escape(fixture['home'])}** vs **{html.escape(fixture['away'])}**")
                    home_score = fixture.get("home_score")
                    away_score = fixture.get("away_score")
                    if home_score is None or away_score is None:
                        st.caption("Provisional fixture - score pending")
                    else:
                        st.markdown(
                            f'<div class="score-box">{home_score} - {away_score}</div>',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"Status: {fixture['status']}")


def render_standings_view(standings: list[dict]) -> None:
    st.subheader("Standings")
    if not standings:
        st.caption("Standings will appear once match results are entered.")
        return

    df = pd.DataFrame(
        standings,
        columns=["team", "pld", "w", "d", "l", "gf", "ga", "gd", "pts"],
    )
    df.columns = ["Team", "Pld", "W", "D", "L", "GF", "GA", "GD", "Pts"]
    st.dataframe(df, hide_index=True, use_container_width=True)


def render_overview(state: dict, standings: list[dict]) -> None:
    st.subheader("Overview")
    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
        st.markdown(
            """
            <div class="muted-card">
              <strong>Provisional tournament rhythm</strong><br/>
              Keep the tournament on weekends for now, with 3:00 PM, 4:30 PM, and 6:00 PM kickoff windows.
              That gives you a clean matchday pattern for a six-team round robin while the organizers confirm the exact cadence.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='subtle-rule'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="muted-card">
              <strong>Suggested structure</strong><br/>
              {html.escape(DEFAULT_SETTINGS["format"])}<br/>
              {html.escape(DEFAULT_SETTINGS["match_length"])}<br/>
              {html.escape(DEFAULT_SETTINGS["venue_note"])}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="muted-card">
              <strong>Admin access</strong><br/>
              The edit panel stays hidden unless the admin code is entered in the sidebar.
              That keeps roster edits and score updates away from the public view.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("If you want, I can later help add a stronger auth layer or a proper backend database.")

    st.markdown("<div class='subtle-rule'></div>", unsafe_allow_html=True)
    if standings:
        leader = standings[0]
        st.caption(f"Leader right now: {leader['team']} with {leader['pts']} points.")


def render_admin_panel(state: dict) -> None:
    with st.expander("Admin controls", expanded=False):
        st.caption("Only the admin should unlock this section.")

        tab_teams, tab_fixtures = st.tabs(["Teams", "Fixtures"])

        with tab_teams:
            st.caption("Edit team names and player slots, then save.")
            teams_df = team_dataframe(state)
            edited_teams = st.data_editor(
                teams_df,
                key="teams_editor",
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
            )
            if st.button("Save team changes", key="save_teams", use_container_width=True):
                update_teams_from_editor(state, edited_teams)
                save_state(state)
                st.success("Team list updated.")
                st.rerun()

        with tab_fixtures:
            st.caption("Enter match scores and status, then save.")
            fixtures_df = fixture_dataframe(state)
            edited_fixtures = st.data_editor(
                fixtures_df,
                key="fixtures_editor",
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                column_config={
                    "round": st.column_config.NumberColumn("Round", disabled=True),
                    "match": st.column_config.TextColumn("Match", disabled=True),
                    "home_team": st.column_config.TextColumn("Home", disabled=True),
                    "away_team": st.column_config.TextColumn("Away", disabled=True),
                    "home_score": st.column_config.NumberColumn("Home score", min_value=0, step=1),
                    "away_score": st.column_config.NumberColumn("Away score", min_value=0, step=1),
                    "status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["Scheduled", "Played", "Postponed", "Confirmed"],
                    ),
                },
                disabled=["round", "match", "home_team", "away_team"],
            )
            if st.button("Save fixture updates", key="save_fixtures", use_container_width=True):
                update_fixtures_from_editor(state, edited_fixtures)
                save_state(state)
                st.success("Fixture updates saved.")
                st.rerun()


def unlock_admin() -> None:
    if st.session_state.get("admin_code_input", "") == get_admin_code():
        st.session_state.admin_unlocked = True
        st.session_state.admin_error = ""
    else:
        st.session_state.admin_error = "That code does not match."


def lock_admin() -> None:
    st.session_state.admin_unlocked = False


def ensure_session_defaults() -> None:
    st.session_state.setdefault("admin_unlocked", False)
    st.session_state.setdefault("admin_error", "")
    st.session_state.setdefault("view", "Overview")
    st.session_state.setdefault("admin_code_input", "")


def inject_sidebar(state: dict) -> None:
    with st.sidebar:
        st.markdown("### View")
        st.segmented_control(
            "Select a section",
            options=["Overview", "Fixtures", "Teams", "Standings"],
            key="view",
            label_visibility="collapsed",
        )

        st.markdown("### Admin")
        if st.session_state.admin_unlocked:
            st.success("Admin unlocked")
            if st.button("Lock admin", use_container_width=True):
                lock_admin()
                st.rerun()
        else:
            st.text_input("Admin code", type="password", key="admin_code_input", placeholder="Enter code")
            if st.button("Unlock admin", use_container_width=True):
                unlock_admin()
                if st.session_state.admin_error:
                    st.error(st.session_state.admin_error)
                else:
                    st.success("Admin unlocked")

        st.caption("Recommended host: Streamlit Community Cloud.")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=":material/sports_soccer:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_defaults()
    inject_styles()

    state = load_state()
    standings = compute_standings(state)

    inject_sidebar(state)

    render_hero(state, standings)
    st.markdown("<br/>", unsafe_allow_html=True)

    view = st.session_state.view
    if view == "Overview":
        render_overview(state, standings)
    elif view == "Fixtures":
        render_fixtures_view(state)
    elif view == "Teams":
        render_teams_view(state)
    elif view == "Standings":
        render_standings_view(standings)

    if st.session_state.admin_unlocked:
        st.markdown("<div class='subtle-rule'></div>", unsafe_allow_html=True)
        render_admin_panel(state)


if __name__ == "__main__":
    main()
