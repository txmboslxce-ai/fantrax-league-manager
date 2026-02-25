import requests
import json

LEAGUES = {
    "premier_league": "34wnxersmc1y1272",
    "championship": "d9ykwqkbmc1y029m",
    "league_one": "jc4hm3twmc1xxwcv"
}

def get_schedule(league_key):
    league_id = LEAGUES[league_key]
    url = f"https://www.fantrax.com/fxpa/req?leagueId={league_id}"
    payload = json.dumps({
        "msgs": [{"method": "getStandings", "data": {"leagueId": league_id, "view": "SCHEDULE"}}],
        "at": 0, "av": "0.0", "dt": 1, "uiv": 3, "v": "179.0.1"
    })
    headers = {
        "Content-Type": "text/plain",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.fantrax.com/fantasy/league/{league_id}/standings;view=SCHEDULE"
    }
    response = requests.post(url, data=payload, headers=headers)
    return response.json()["responses"][0]["data"]["tableList"]

def get_standings(league_key):
    league_id = LEAGUES[league_key]
    url = "https://www.fantrax.com/fxea/general/getStandings"
    response = requests.get(url, params={"leagueId": league_id}, headers={"User-Agent": "Mozilla/5.0"})
    raw = response.json()

    # Parse "18-0-9" into W, D, L
    enriched = []
    for team in raw:
        parts = team["points"].split("-")
        w = int(parts[0]) if len(parts) > 0 else 0
        d = int(parts[1]) if len(parts) > 1 else 0
        l = int(parts[2]) if len(parts) > 2 else 0
        pts = (w * 3) + (d * 1)

        enriched.append({
            "teamName": team["teamName"],
            "teamId": team["teamId"],
            "rank": team["rank"],
            "w": w,
            "d": d,
            "l": l,
            "pts": pts,
            "pf": team["totalPointsFor"],
            "pa": None,
            "winPercentage": team["winPercentage"]
        })

    # Get PA from schedule data
    schedule = get_schedule(league_key)
    pa_map = {}
    for gw_data in schedule:
        for row in gw_data["rows"]:
            cells = row["cells"]
            away = cells[0]["content"]
            away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
            home = cells[2]["content"]
            home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0
            if away_score == 0.0 and home_score == 0.0:
                continue
            pa_map[away] = pa_map.get(away, 0.0) + home_score
            pa_map[home] = pa_map.get(home, 0.0) + away_score

    for team in enriched:
        team["pa"] = pa_map.get(team["teamName"], 0.0)
        team["pd"] = round(team["pf"] - team["pa"], 2)

    return enriched

def get_team_id_map(league_key):
    """Returns {team_id: current_name} for a league by reading GW1"""
    schedule = get_schedule(league_key)
    gw = schedule[0]
    id_to_name = {}
    for row in gw["rows"]:
        cells = row["cells"]
        if "teamId" in cells[0]:
            id_to_name[cells[0]["teamId"]] = cells[0]["content"]
        if "teamId" in cells[2]:
            id_to_name[cells[2]["teamId"]] = cells[2]["content"]
    return id_to_name

def get_all_team_id_maps():
    """Returns {team_id: current_name} across all 3 leagues"""
    combined = {}
    for league_key in LEAGUES:
        combined.update(get_team_id_map(league_key))
    return combined

def get_gw_scores(league_key, gw):
    schedule = get_schedule(league_key)
    gw_data = schedule[gw - 1]
    scores = {}
    for row in gw_data["rows"]:
        cells = row["cells"]
        away_team = cells[0]["content"]
        away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
        home_team = cells[2]["content"]
        home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0
        scores[away_team] = away_score
        scores[home_team] = home_score
    return scores

def get_score_by_id(team_id, gw, league_key):
    """Get a team's score for a GW using their team ID"""
    schedule = get_schedule(league_key)
    gw_data = schedule[gw - 1]
    for row in gw_data["rows"]:
        cells = row["cells"]
        if cells[0].get("teamId") == team_id:
            return float(cells[1]["content"]) if cells[1]["content"] else 0.0
        if cells[2].get("teamId") == team_id:
            return float(cells[3]["content"]) if cells[3]["content"] else 0.0
    return None

def get_league_for_id(team_id, cup_config):
    """Look up which league a team ID belongs to"""
    for league_key, teams in cup_config["team_ids"].items():
        if team_id in teams.values():
            return league_key
    return None

if __name__ == "__main__":
    print("Testing standings...")
    standings = get_standings("premier_league")
    for team in standings[:3]:
        print(f"{team['rank']}. {team['teamName']} — W{team['w']} D{team['d']} L{team['l']} | Pts:{team['pts']} | PF:{team['pf']} | PA:{team['pa']} | PD:{team['pd']}")

    print("\nTesting GW20 scores...")
    scores = get_gw_scores("premier_league", 20)
    for team, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        print(f"{team}: {score}")