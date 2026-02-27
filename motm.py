import json
from datetime import datetime, timezone
from fantrax import get_schedule

def load_motm_config():
    with open("config/motm.json") as f:
        return json.load(f)

def _parse_datetime(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Fantrax-style epochs may be milliseconds.
        ts = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        if raw.isdigit():
            return _parse_datetime(int(raw))

        iso = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

    return None

def _extract_gameweek_end(gw_data):
    end_candidates = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                lower = key.lower()
                likely_end = (
                    lower in {"enddate", "end_date", "endtime", "end_time", "end"}
                    or ("end" in lower and ("date" in lower or "time" in lower))
                    or "scoringperiodend" in lower
                )
                if likely_end:
                    parsed = _parse_datetime(value)
                    if parsed:
                        end_candidates.append(parsed)
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(gw_data)
    return max(end_candidates) if end_candidates else None

def calculate_motm(league_key, month, schedule=None):
    config = load_motm_config()
    
    if month not in config:
        return {"error": f"Month '{month}' not found in config"}
    
    gameweeks = config[month]
    if schedule is None:
        schedule = get_schedule(league_key)
    
    team_stats = {}
    month_complete = True

    now_utc = datetime.now(timezone.utc)

    for gw in gameweeks:
        gw_data = schedule[gw - 1]
        gw_complete = True
        gw_end = _extract_gameweek_end(gw_data)
        for row in gw_data["rows"]:
            cells = row["cells"]
            away_id = cells[0].get("teamId") or cells[0]["content"]
            away_team = cells[0]["content"]
            away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
            home_id = cells[2].get("teamId") or cells[2]["content"]
            home_team = cells[2]["content"]
            home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0

            # Initialise teams
            for team_id, team_name in [(away_id, away_team), (home_id, home_team)]:
                if team_id not in team_stats:
                    team_stats[team_id] = {"team": team_name, "pts": 0, "w": 0, "d": 0, "l": 0, "pf": 0.0, "pa": 0.0}

            # Fantrax represents unplayed fixtures as 0-0; ignore for MOTM stats
            if away_score == 0.0 and home_score == 0.0:
                gw_complete = False
                continue

            # Award points
            if away_score > home_score:
                team_stats[away_id]["pts"] += 3
                team_stats[away_id]["w"] += 1
                team_stats[home_id]["l"] += 1
            elif home_score > away_score:
                team_stats[home_id]["pts"] += 3
                team_stats[home_id]["w"] += 1
                team_stats[away_id]["l"] += 1
            else:
                team_stats[away_id]["pts"] += 1
                team_stats[home_id]["pts"] += 1
                team_stats[away_id]["d"] += 1
                team_stats[home_id]["d"] += 1

            # Track PF and PA
            team_stats[away_id]["pf"] += away_score
            team_stats[away_id]["pa"] += home_score
            team_stats[home_id]["pf"] += home_score
            team_stats[home_id]["pa"] += away_score

        if gw_end is not None:
            if now_utc < gw_end:
                month_complete = False
        elif not gw_complete:
            month_complete = False

    # Sort by points then PF
    ranked = sorted(team_stats.items(), key=lambda x: (x[1]["pts"], x[1]["pf"]), reverse=True)

    return {
        "month": month,
        "league": league_key,
        "gameweeks": gameweeks,
        "month_complete": month_complete,
        "results": [
            {
                "rank": i + 1,
                "teamId": team_id,
                "team": data["team"],
                "pts": data["pts"],
                "w": data["w"],
                "d": data["d"],
                "l": data["l"],
                "pf": data["pf"],
                "pa": data["pa"],
                "winner": i == 0
            }
            for i, (team_id, data) in enumerate(ranked)
        ]
    }

if __name__ == "__main__":
    print("Testing MOTM for January - Premier League...")
    result = calculate_motm("premier_league", "January")
    print(f"\nManager of the Month - {result['month']}")
    print(f"Gameweeks: {result['gameweeks']}")
    print(f"{'Rank':<6} {'Team':<30} {'Pts':>4} {'W':>3} {'D':>3} {'L':>3} {'PF':>8} {'PA':>8}")
    print("-" * 70)
    for r in result["results"]:
        winner = " 🏆" if r["winner"] else ""
        print(f"{r['rank']:<6} {r['team']:<30} {r['pts']:>4} {r['w']:>3} {r['d']:>3} {r['l']:>3} {r['pf']:>8} {r['pa']:>8}{winner}")
        
