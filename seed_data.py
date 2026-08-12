from __future__ import annotations

from datetime import datetime, timedelta


APP_TITLE = "LEKKI GARDENS PH1 ESTATE FOOTBALL TOURNAMENT"
APP_SUBTITLE = "Live fixtures and standings."
PITCH_NAME = "Lekki Gardens PH1 Pitch"

DEFAULT_SETTINGS = {
    "schedule_summary": "Weekends, 3:00 PM / 4:30 PM / 6:00 PM kickoff windows",
    "match_length": "70 minutes of play + 20 minutes turnaround",
    "venue_name": PITCH_NAME,
}

DEFAULT_RULES = {
    "qualify_spots": 4,
    "eliminate_spots": 2,
}

TEAMS_SEED = [
    {
        "id": 1,
        "name": "CP FC",
        "short_name": "CP",
        "primary_color": "#d7263d",
        "secondary_color": "#141414",
        "logo_kind": "shield",
        "players": ["C P", "Solomon", "Check Up", "Sammy", "Daniel", "Cheatanna"],
    },
    {
        "id": 2,
        "name": "P MONEY FC",
        "short_name": "PM",
        "primary_color": "#d4af37",
        "secondary_color": "#111111",
        "logo_kind": "bolt",
        "players": ["HDT", "YG", "Ugunna", "P Money", "Dennis", "Akpanya"],
    },
    {
        "id": 3,
        "name": "YOLOS FC",
        "short_name": "YO",
        "primary_color": "#13b8a6",
        "secondary_color": "#0b1320",
        "logo_kind": "hex",
        "players": ["Chika", "Hustle", "Steven", "Vardy", "Kante", "Ikenna"],
    },
    {
        "id": 4,
        "name": "H.I REAL ESTATE FC",
        "short_name": "HI",
        "primary_color": "#4f46e5",
        "secondary_color": "#111111",
        "logo_kind": "diamond",
        "players": ["Mr Henry", "Mr Muri", "Mr Denis", "Mr Okikiola", "", ""],
    },
    {
        "id": 5,
        "name": "ASIAMONEY FC",
        "short_name": "AM",
        "primary_color": "#8b5cf6",
        "secondary_color": "#151515",
        "logo_kind": "star",
        "players": ["Shedi", "Paul", "Ekom", "Gotze", "", ""],
    },
    {
        "id": 6,
        "name": "KELVIN FC",
        "short_name": "KF",
        "primary_color": "#10b981",
        "secondary_color": "#0e1116",
        "logo_kind": "circle",
        "players": ["Mr Kelvin", "Mr Mofe", "Mr OBO", "Mr Pato", "", ""],
    },
]


def next_saturday(dt: datetime) -> datetime:
    days_ahead = (5 - dt.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (dt + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)


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
