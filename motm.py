import json
from fantrax import get_schedule

def load_motm_config():
    with open("config/motm.json") as f:
        return json.load(f)

def calculate_motm(league_key, month):
    config = load_motm_config()
    
    if month not in config:
        return {"error": f"Month '{month}' not found in config"}
    
    gameweeks = config[month]
    schedule = get_schedule(league_key)
    
    team_stats = {}

    for gw in gameweeks:
        gw_data = schedule[gw - 1]
        for row in gw_data["rows"]:
            cells = row["cells"]
            away_team = cells[0]["content"]
            away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
            home_team = cells[2]["content"]
            home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0

            # Initialise teams
            for team in [away_team, home_team]:
                if team not in team_stats:
                    team_stats[team] = {"pts": 0, "w": 0, "d": 0, "l": 0, "pf": 0.0, "pa": 0.0}

            # Award points
            if away_score > home_score:
                team_stats[away_team]["pts"] += 3
                team_stats[away_team]["w"] += 1
                team_stats[home_team]["l"] += 1
            elif home_score > away_score:
                team_stats[home_team]["pts"] += 3
                team_stats[home_team]["w"] += 1
                team_stats[away_team]["l"] += 1
            else:
                team_stats[away_team]["pts"] += 1
                team_stats[home_team]["pts"] += 1
                team_stats[away_team]["d"] += 1
                team_stats[home_team]["d"] += 1

            # Track PF and PA
            team_stats[away_team]["pf"] += away_score
            team_stats[away_team]["pa"] += home_score
            team_stats[home_team]["pf"] += home_score
            team_stats[home_team]["pa"] += away_score

    # Sort by points then PF
    ranked = sorted(team_stats.items(), key=lambda x: (x[1]["pts"], x[1]["pf"]), reverse=True)

    return {
        "month": month,
        "league": league_key,
        "gameweeks": gameweeks,
        "results": [
            {
                "rank": i + 1,
                "team": team,
                "pts": data["pts"],
                "w": data["w"],
                "d": data["d"],
                "l": data["l"],
                "pf": data["pf"],
                "pa": data["pa"],
                "winner": i == 0
            }
            for i, (team, data) in enumerate(ranked)
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
        