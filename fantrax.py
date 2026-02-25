import os
import requests
import json
import unicodedata

LEAGUES = {
    "premier_league": "34wnxersmc1y1272",
    "championship": "d9ykwqkbmc1y029m",
    "league_one": "jc4hm3twmc1xxwcv"
}

def normalize(s):
    return unicodedata.normalize('NFC', s.strip()) if s else s

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

    enriched = []
    for team in raw:
        parts = team["points"].split("-")
        w = int(parts[0]) if len(parts) > 0 else 0
        d = int(parts[1]) if len(parts) > 1 else 0
        l = int(parts[2]) if len(parts) > 2 else 0
        pts = (w * 3) + (d * 1)
        enriched.append({
            "teamName": normalize(team["teamName"]),
            "teamId": team["teamId"],
            "rank": team["rank"],
            "w": w, "d": d, "l": l,
            "pts": pts,
            "pf": team["totalPointsFor"],
            "pa": 0.0,
            "winPercentage": team["winPercentage"]
        })

    # Use teamId for PA matching — avoids emoji encoding mismatches
    schedule = get_schedule(league_key)
    pa_by_id = {}
    for gw_data in schedule:
        for row in gw_data["rows"]:
            cells = row["cells"]
            away_id = cells[0].get("teamId")
            home_id = cells[2].get("teamId")
            try:
                away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
                home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0
            except (ValueError, KeyError):
                continue
            if away_score == 0.0 and home_score == 0.0:
                continue
            if away_id:
                pa_by_id[away_id] = pa_by_id.get(away_id, 0.0) + home_score
            if home_id:
                pa_by_id[home_id] = pa_by_id.get(home_id, 0.0) + away_score

    for team in enriched:
        team["pa"] = round(pa_by_id.get(team["teamId"], 0.0), 2)
        team["pd"] = round(team["pf"] - team["pa"], 2)

    return enriched

def get_team_id_map(league_key):
    schedule = get_schedule(league_key)
    id_to_name = {}
    for gw_data in schedule:
        for row in gw_data["rows"]:
            cells = row["cells"]
            if "teamId" in cells[0]:
                id_to_name[cells[0]["teamId"]] = normalize(cells[0]["content"])
            if "teamId" in cells[2]:
                id_to_name[cells[2]["teamId"]] = normalize(cells[2]["content"])
    return id_to_name

def get_all_team_id_maps():
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
        away_team = normalize(cells[0]["content"])
        away_score = float(cells[1]["content"]) if cells[1]["content"] else 0.0
        home_team = normalize(cells[2]["content"])
        home_score = float(cells[3]["content"]) if cells[3]["content"] else 0.0
        scores[away_team] = away_score
        scores[home_team] = home_score
    return scores

def get_score_by_id(team_id, gw, league_key):
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
    for league_key, teams in cup_config["team_ids"].items():
        if team_id in teams.values():
            return league_key
    return None

def get_current_round(cup_config):
    rounds = ["playoff", "round_of_16", "quarter_final", "semi_final", "final"]
    current = "groups"
    for round_name in rounds:
        matches = cup_config.get(round_name, {}).get("matches", [])
        if matches:
            current = round_name
            if any(m["winner"] is None for m in matches):
                break
    return current

if __name__ == "__main__":
    print("Testing standings...")
    standings = get_standings("premier_league")
    for team in standings:
        print(f"{team['rank']}. {team['teamName']} — W{team['w']} D{team['d']} L{team['l']} | Pts:{team['pts']} | PF:{team['pf']} | PA:{team['pa']} | PD:{team['pd']}")