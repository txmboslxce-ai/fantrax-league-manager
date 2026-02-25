import os
from flask import Flask, render_template, jsonify, request
from fantrax import get_standings, get_all_team_id_maps
from motm import calculate_motm
from cup import load_cup_config, save_cup_config, calculate_group_standings, get_cup_round_scores, get_full_cup_status

app = Flask(__name__)

LEAGUES = {
    "premier_league": "Premier League",
    "championship": "Championship",
    "league_one": "League One"
}

MONTHS = [
    "August", "September", "October", "November",
    "December", "January", "February", "March", "April", "May"
]

# ── MAIN PAGE ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", leagues=LEAGUES, months=MONTHS)

# ── STANDINGS ──────────────────────────────────────────────────────────────────

@app.route("/api/standings/<league_key>")
def api_standings(league_key):
    try:
        data = get_standings(league_key)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── MOTM ───────────────────────────────────────────────────────────────────────

@app.route("/api/motm/<league_key>/<month>")
def api_motm(league_key, month):
    try:
        result = calculate_motm(league_key, month)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── CUP ────────────────────────────────────────────────────────────────────────

@app.route("/api/cup/groups")
def api_cup_groups():
    try:
        config = load_cup_config()
        id_map = get_all_team_id_maps()
        groups = calculate_group_standings(config, id_map)
        return jsonify({"success": True, "data": groups})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/cup/round/<round_name>")
def api_cup_round(round_name):
    try:
        config = load_cup_config()
        id_map = get_all_team_id_maps()
        round_data = get_cup_round_scores(config, round_name, id_map)
        
        # Resolve team names for display
        matches = []
        for match in round_data["matches"]:
            matches.append({
                "home": id_map.get(match["home"], match["home"]),
                "away": id_map.get(match["away"], match["away"]),
                "leg1_gw": match["leg1_gw"],
                "leg1_home": match["leg1_home"],
                "leg1_away": match["leg1_away"],
                "leg2_gw": match.get("leg2_gw"),
                "leg2_home": match.get("leg2_home"),
                "leg2_away": match.get("leg2_away"),
                "home_agg": (match["leg1_home"] or 0) + (match.get("leg2_home") or 0),
                "away_agg": (match["leg1_away"] or 0) + (match.get("leg2_away") or 0),
                "winner": id_map.get(match["winner"], match["winner"]) if match["winner"] else None
            })
        
        return jsonify({"success": True, "data": matches})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/cup/refresh/<round_name>", methods=["POST"])
def api_cup_refresh(round_name):
    try:
        config = load_cup_config()
        id_map = get_all_team_id_maps()
        get_cup_round_scores(config, round_name, id_map)
        return jsonify({"success": True, "message": f"{round_name} scores refreshed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/cup/draw/<round_name>", methods=["POST"])
def api_cup_draw(round_name):
    """Save a new draw for a future round"""
    try:
        config = load_cup_config()
        matches = request.json.get("matches", [])
        config[round_name]["matches"] = matches
        save_cup_config(config)
        return jsonify({"success": True, "message": "Draw saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)