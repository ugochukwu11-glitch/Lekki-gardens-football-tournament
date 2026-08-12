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
        "players": ["Mr Henry", "Mr Muri", "Mr Denis", "Mr Okikiola", "Emma", "Daniel"],
    },
    {
        "id": 5,
        "name": "ASIAMONEY FC",
        "short_name": "AM",
        "primary_color": "#8b5cf6",
        "secondary_color": "#151515",
        "logo_kind": "star",
        "players": ["Shedi", "Paul", "Ekom", "Gotze", "Moris", "Asiamoney"],
    },
    {
        "id": 6,
        "name": "KELVIN FC",
        "short_name": "KF",
        "primary_color": "#10b981",
        "secondary_color": "#0e1116",
        "logo_kind": "circle",
        "players": ["Mr Kelvin", "Mr Mofe", "Mr OBO", "Mr Pato", "Mr Tmaxee", ""],
    },
]


def next_saturday(dt: datetime) -> datetime:
    days_ahead = (5 - dt.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (dt + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)


def build_round_robin_schedule(team_ids: list[int]) -> list[dict]:
    # Single round-robin (each pair once), mapped across 5 matchdays with 3 matches each
    ids = team_ids[:]
    if len(ids) % 2:
        ids.append(None)

    rounds = len(ids) - 1
    half = len(ids) // 2
    rotation = ids[:]

    # Explicit matchdays (first match of each day has a kickoff time of 18:30)
    matchdays = [
        datetime(2026, 8, 14),
        datetime(2026, 8, 15),
        datetime(2026, 8, 16),
        datetime(2026, 8, 21),
        datetime(2026, 8, 22),
    ]
    # Per-day kickoff slots: only the first match has a time (18:30)
    day_kickoff_slots = [(18, 30), None, None]

    fixtures: list[dict] = []
    match_count = 1

    for round_number in range(1, rounds + 1):
        left = rotation[:half]
        right = list(reversed(rotation[half:]))

        for match_number, (home_id, away_id) in enumerate(zip(left, right), start=1):
            if home_id is None or away_id is None:
                continue
            if round_number % 2 == 0:
                home_id, away_id = away_id, home_id

            # determine which matchday and which slot within the day this match occupies
            day_index = (match_count - 1) // 3
            slot_index = (match_count - 1) % 3
            if day_index < len(matchdays):
                match_date = matchdays[day_index]
            else:
                match_date = matchdays[-1] + timedelta(days=(day_index - (len(matchdays) - 1)) * 7)

            slot_time = day_kickoff_slots[slot_index]
            if slot_time is None:
                kickoff_at = match_date.date().isoformat()
            else:
                hour, minute = slot_time
                kickoff = match_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                kickoff_at = kickoff.isoformat(timespec="minutes")

            fixtures.append(
                {
                    "round_number": round_number,
                    "match_number": match_count,
                    "kickoff_at": kickoff_at,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                }
            )
            match_count += 1

        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    return fixtures
