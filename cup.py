import json
from fantrax import get_score_by_id, get_league_for_id, get_all_team_id_maps

def load_cup_config():
    with open("config/cup.json") as f:
        return json.load(f)

def save_cup_config(config):
    with open("config/cup.json", "w") as f:
        json.dump(config, f, indent=2)

def calculate_group_standings(config, id_map):
    groups = {}
    for group_name, group_data in config["groups"].items():
        team_stats = {}
        for team in group_data["teams"]:
            team_stats[team["id"]] = {
                "name": id_map.get(team["id"], team["name"]),
                "league": team["league"],
                "pts": 0, "w": 0, "d": 0, "l": 0,
                "pf": 0.0, "pa": 0.0
            }

        for match in group_data["matches"]:
            home_id = match["home"]
            away_id = match["away"]
            hs = match["home_score"]
            as_ = match["away_score"]

            team_stats[home_id]["pf"] += hs
            team_stats[home_id]["pa"] += as_
            team_stats[away_id]["pf"] += as_
            team_stats[away_id]["pa"] += hs

            if hs > as_:
                team_stats[home_id]["pts"] += 3
                team_stats[home_id]["w"] += 1
                team_stats[away_id]["l"] += 1
            elif as_ > hs:
                team_stats[away_id]["pts"] += 3
                team_stats[away_id]["w"] += 1
                team_stats[home_id]["l"] += 1
            else:
                team_stats[home_id]["pts"] += 1
                team_stats[away_id]["pts"] += 1
                team_stats[home_id]["d"] += 1
                team_stats[away_id]["d"] += 1

        ranked = sorted(team_stats.items(),
                       key=lambda x: (x[1]["pts"], x[1]["pf"]), reverse=True)
        groups[group_name] = [
            {"rank": i + 1, "id": tid, **stats}
            for i, (tid, stats) in enumerate(ranked)
        ]

    return groups

def get_cup_round_scores(config, round_name, id_map):
    """Pull API scores for a cup round and update config"""
    round_data = config[round_name]
    updated = False

    for match in round_data["matches"]:
        home_id = match["home"]
        away_id = match["away"]
        home_league = get_league_for_id(home_id, config)
        away_league = get_league_for_id(away_id, config)

        # Leg 1
        if match["leg1_home"] is None and home_league:
            score = get_score_by_id(home_id, match["leg1_gw"], home_league)
            if score is not None:
                match["leg1_home"] = score
                updated = True
        if match["leg1_away"] is None and away_league:
            score = get_score_by_id(away_id, match["leg1_gw"], away_league)
            if score is not None:
                match["leg1_away"] = score
                updated = True

        # Leg 2
        if match.get("leg2_gw") and match["leg2_home"] is None and home_league:
            score = get_score_by_id(home_id, match["leg2_gw"], home_league)
            if score is not None:
                match["leg2_home"] = score
                updated = True
        if match.get("leg2_gw") and match["leg2_away"] is None and away_league:
            score = get_score_by_id(away_id, match["leg2_gw"], away_league)
            if score is not None:
                match["leg2_away"] = score
                updated = True

        # Calculate winner if both legs complete
        if (match["leg1_home"] is not None and match["leg1_away"] is not None and
                match.get("leg2_home") is not None and match.get("leg2_away") is not None):
            home_agg = match["leg1_home"] + match["leg2_home"]
            away_agg = match["leg1_away"] + match["leg2_away"]
            if home_agg > away_agg:
                match["winner"] = home_id
            elif away_agg > home_agg:
                match["winner"] = away_id
            updated = True

    if updated:
        save_cup_config(config)

    return round_data

def get_full_cup_status(config, id_map):
    groups = calculate_group_standings(config, id_map)
    return {
        "groups": groups,
        "playoff": config["playoff"],
        "round_of_16": config["round_of_16"],
        "quarter_final": config["quarter_final"],
        "semi_final": config["semi_final"],
        "final": config["final"]
    }

if __name__ == "__main__":
    config = load_cup_config()
    id_map = get_all_team_id_maps()

    print("=== GROUP STANDINGS ===")
    groups = calculate_group_standings(config, id_map)
    for group_name, standings in groups.items():
        print(f"\nGroup {group_name}")
        print(f"{'Rank':<6} {'Team':<30} {'Pts':>4} {'W':>3} {'D':>3} {'L':>3} {'PF':>8} {'PA':>8}")
        print("-" * 65)
        for team in standings:
            print(f"{team['rank']:<6} {team['name']:<30} {team['pts']:>4} {team['w']:>3} {team['d']:>3} {team['l']:>3} {team['pf']:>8} {team['pa']:>8}")

    print("\n=== ROUND OF 16 ===")
    r16 = get_cup_round_scores(config, "round_of_16", id_map)
    for match in r16["matches"]:
        home_name = id_map.get(match["home"], match["home"])
        away_name = id_map.get(match["away"], match["away"])
        l1h = match["leg1_home"] or 0
        l1a = match["leg1_away"] or 0
        l2h = match["leg2_home"] or 0
        l2a = match["leg2_away"] or 0
        home_agg = l1h + l2h
        away_agg = l1a + l2a
        winner_id = match["winner"]
        winner = f" → {id_map.get(winner_id, winner_id)}" if winner_id else " (in progress)"
        print(f"{home_name} {home_agg} vs {away_agg} {away_name}{winner}")