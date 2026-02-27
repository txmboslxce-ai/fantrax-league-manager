import os
from flask import Flask, render_template, jsonify, request
from fantrax import get_standings, get_all_team_id_maps, get_team_fixtures, get_public_team_url, get_league_for_id, get_schedule
from motm import calculate_motm, load_motm_config
from cup import (
    load_cup_config,
    save_cup_config,
    calculate_group_standings,
    get_cup_round_scores,
    get_full_cup_status,
    get_draw_options,
    get_team_cup_progress
)

app = Flask(__name__)
RULES_FILE = "config/rules.md"

LEAGUES = {
    "premier_league": "Premier League",
    "championship": "Championship",
    "league_one": "League One"
}

MONTHS = [
    "August", "September", "October", "November",
    "December", "January", "February", "March", "April", "May"
]

def _require_admin():
    expected = os.environ.get("CUP_ADMIN_KEY", "fantrax13")
    provided = request.headers.get("X-Admin-Key", "")
    if provided != expected:
        return False, ("Unauthorized", 403)
    return True, None

def _load_rules_markdown():
    if not os.path.exists(RULES_FILE):
        return ""
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return f.read()

def _save_rules_markdown(markdown_text):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        f.write(markdown_text)

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

@app.route("/api/teams")
def api_teams():
    try:
        data = {}
        for league_key, league_name in LEAGUES.items():
            standings = get_standings(league_key)
            data[league_key] = {
                "league_name": league_name,
                "teams": [
                    {
                        "teamId": t["teamId"],
                        "teamName": t["teamName"],
                        "rank": t["rank"],
                        "pts": t["pts"]
                    }
                    for t in standings
                ]
            }
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

# ── RULES ──────────────────────────────────────────────────────────────────────

@app.route("/api/rules")
def api_rules():
    try:
        markdown = _load_rules_markdown()
        updated_at = None
        if os.path.exists(RULES_FILE):
            updated_at = int(os.path.getmtime(RULES_FILE))
        return jsonify({"success": True, "data": {"markdown": markdown, "updated_at": updated_at}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/rules/auth")
def api_rules_auth():
    ok, err = _require_admin()
    if not ok:
        message, status = err
        return jsonify({"success": False, "error": message}), status
    return jsonify({"success": True})

@app.route("/api/rules", methods=["POST"])
def api_rules_save():
    try:
        ok, err = _require_admin()
        if not ok:
            message, status = err
            return jsonify({"success": False, "error": message}), status

        payload = request.get_json(silent=True) or {}
        markdown = payload.get("markdown", "")
        if not isinstance(markdown, str):
            return jsonify({"success": False, "error": "Invalid markdown payload"}), 400
        _save_rules_markdown(markdown)
        return jsonify({"success": True, "message": "Rules saved"})
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
                "home_id": match["home"],
                "home": id_map.get(match["home"], match["home"]),
                "away_id": match["away"],
                "away": id_map.get(match["away"], match["away"]),
                "leg1_gw": match["leg1_gw"],
                "leg1_home": match["leg1_home"],
                "leg1_away": match["leg1_away"],
                "leg2_gw": match.get("leg2_gw"),
                "leg2_home": match.get("leg2_home"),
                "leg2_away": match.get("leg2_away"),
                "home_agg": (match["leg1_home"] or 0) + (match.get("leg2_home") or 0),
                "away_agg": (match["leg1_away"] or 0) + (match.get("leg2_away") or 0),
                "winner_id": match["winner"],
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
        ok, err = _require_admin()
        if not ok:
            message, status = err
            return jsonify({"success": False, "error": message}), status

        config = load_cup_config()
        payload = request.get_json(silent=True) or {}
        raw_matches = payload.get("matches", [])
        options = get_draw_options(config, round_name, get_all_team_id_maps())
        allowed_ids = {t["id"] for t in options["teams"]}
        if not raw_matches:
            return jsonify({"success": False, "error": "No matches provided"}), 400

        schedule = config.get("schedule", {}).get(round_name, {})
        leg1_gw = schedule.get("leg1")
        leg2_gw = schedule.get("leg2")

        used = set()
        matches = []
        for m in raw_matches:
            home = m.get("home")
            away = m.get("away")
            if not home or not away:
                return jsonify({"success": False, "error": "Each match must have home and away teams"}), 400
            if home == away:
                return jsonify({"success": False, "error": "A team cannot play itself"}), 400
            if home not in allowed_ids or away not in allowed_ids:
                return jsonify({"success": False, "error": "Draw includes teams that have not advanced"}), 400
            if home in used or away in used:
                return jsonify({"success": False, "error": "A team can only appear once in the draw"}), 400
            used.add(home)
            used.add(away)
            matches.append({
                "home": home,
                "away": away,
                "leg1_gw": leg1_gw,
                "leg1_home": None,
                "leg1_away": None,
                "leg2_gw": leg2_gw,
                "leg2_home": None,
                "leg2_away": None,
                "winner": None
            })

        if len(matches) * 2 != len(allowed_ids):
            return jsonify({"success": False, "error": "All advanced teams must be used exactly once"}), 400

        if round_name not in config:
            return jsonify({"success": False, "error": f"Unknown round: {round_name}"}), 400

        config[round_name]["matches"] = matches
        save_cup_config(config)
        return jsonify({"success": True, "message": "Draw saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/cup/draw/options/<round_name>")
def api_cup_draw_options(round_name):
    try:
        ok, err = _require_admin()
        if not ok:
            message, status = err
            return jsonify({"success": False, "error": message}), status

        config = load_cup_config()
        id_map = get_all_team_id_maps()
        options = get_draw_options(config, round_name, id_map)
        return jsonify({"success": True, "data": options})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/cup/current_round")
def api_cup_current_round():
    try:
        config = load_cup_config()
        from fantrax import get_current_round
        round_name = get_current_round(config)
        return jsonify({"success": True, "data": round_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/team/profile/<team_id>")
def api_team_profile(team_id):
    try:
        cup_config = load_cup_config()
        league_key = get_league_for_id(team_id, cup_config)
        if not league_key:
            return jsonify({"success": False, "error": "Team not found"}), 404

        standings = get_standings(league_key)
        team_row = next((t for t in standings if t["teamId"] == team_id), None)
        if not team_row:
            return jsonify({"success": False, "error": "Team not found in league standings"}), 404

        fixtures = get_team_fixtures(league_key, team_id, count=5)
        rank_by_team_id = {t["teamId"]: t["rank"] for t in standings}
        for bucket in ("last5", "next5"):
            for fx in fixtures.get(bucket, []):
                opp_id = fx.get("opponent_id")
                fx["opponent_rank"] = rank_by_team_id.get(opp_id)
        cup = get_team_cup_progress(cup_config, team_id, get_all_team_id_maps())

        motm_config = load_motm_config()
        schedule = get_schedule(league_key)
        awards = []
        for month in motm_config.keys():
            result = calculate_motm(league_key, month, schedule=schedule)
            if not result.get("month_complete"):
                continue
            winner = next((r for r in result["results"] if r.get("winner")), None)
            winner_played = (winner["w"] + winner["d"] + winner["l"]) if winner else 0
            if winner and winner_played > 0 and winner.get("teamId") == team_id:
                awards.append({
                    "month": month,
                    "league": LEAGUES[league_key]
                })

        played = team_row["w"] + team_row["d"] + team_row["l"]
        avg_ppg = round(team_row["pf"] / played, 2) if played else 0.0

        data = {
            "team": {
                "id": team_id,
                "name": team_row["teamName"],
                "league_key": league_key,
                "league_name": LEAGUES[league_key],
                "fantrax_url": get_public_team_url(league_key, team_id)
            },
            "league": {
                "rank": team_row["rank"],
                "played": played,
                "pf": team_row["pf"],
                "pa": team_row["pa"],
                "pd": team_row["pd"],
                "avg_ppg": avg_ppg
            },
            "fixtures": fixtures,
            "cup": cup,
            "motm": {
                "count": len(awards),
                "awards": awards
            }
        }
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
