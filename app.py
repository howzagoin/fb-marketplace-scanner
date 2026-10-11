import os
import threading
from flask import Flask, jsonify, request, send_from_directory
from backend.config import Config
from backend.db import (
    init_db, get_filters, get_filter, save_filter, delete_filter,
    get_listings, update_listing_status, get_scan_logs,
    get_setting, set_setting
)
from backend.scraper import get_session_info, capture_interactive_login, save_raw_cookies
from backend.scheduler import scan_manager
from schema import SearchFilter

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["SECRET_KEY"] = Config.SECRET_KEY

# Initialize database
init_db()

# Start background scheduler
scan_manager.start_background_scheduler()

# ----------------- Static Frontend Routes -----------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/styles.css")
def serve_root_css():
    return send_from_directory(os.path.join(app.static_folder, "css"), "styles.css")

@app.route("/js/<path:path>")
def serve_js(path):
    return send_from_directory(os.path.join(app.static_folder, "js"), path)

@app.route("/css/<path:path>")
def serve_css(path):
    return send_from_directory(os.path.join(app.static_folder, "css"), path)

# ----------------- Filter API Routes -----------------

@app.route("/api/filters", methods=["GET"])
def api_get_filters():
    filters = get_filters()
    return jsonify({"success": True, "filters": filters})

@app.route("/api/filters/<int:filter_id>", methods=["GET"])
def api_get_filter(filter_id):
    f = get_filter(filter_id)
    if not f:
        return jsonify({"success": False, "error": "Filter not found"}), 404
    return jsonify({"success": True, "filter": f})

@app.route("/api/filters", methods=["POST"])
def api_save_filter():
    data = request.json or {}
    try:
        filter_id = save_filter(data)
        return jsonify({"success": True, "filter_id": filter_id, "message": "Filter saved successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/filters/<int:filter_id>", methods=["DELETE"])
def api_delete_filter(filter_id):
    try:
        delete_filter(filter_id)
        return jsonify({"success": True, "message": "Filter deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/filters/<int:filter_id>/toggle", methods=["POST"])
def api_toggle_filter(filter_id):
    f = get_filter(filter_id)
    if not f:
        return jsonify({"success": False, "error": "Filter not found"}), 404
    new_state = not bool(f.get("enabled"))
    f["enabled"] = new_state
    save_filter(f)
    return jsonify({"success": True, "enabled": new_state})

# ----------------- Listings API Routes -----------------

@app.route("/api/listings", methods=["GET"])
def api_get_listings():
    filter_id = request.args.get("filter_id", type=int)
    keyword = request.args.get("keyword", "")
    show_dismissed = request.args.get("show_dismissed", "0") in ("1", "true")
    only_favorites = request.args.get("only_favorites", "0") in ("1", "true")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    items = get_listings(
        filter_id=filter_id,
        keyword=keyword,
        show_dismissed=show_dismissed,
        only_favorites=only_favorites,
        limit=limit,
        offset=offset
    )
    return jsonify({"success": True, "listings": items, "count": len(items)})

@app.route("/api/listings/<listing_id>/favorite", methods=["POST"])
def api_toggle_favorite(listing_id):
    data = request.json or {}
    is_fav = data.get("is_favorite")
    update_listing_status(listing_id, is_favorite=is_fav)
    return jsonify({"success": True, "listing_id": listing_id, "is_favorite": is_fav})

@app.route("/api/listings/<listing_id>/dismiss", methods=["POST"])
def api_toggle_dismiss(listing_id):
    data = request.json or {}
    is_dis = data.get("is_dismissed")
    update_listing_status(listing_id, is_dismissed=is_dis)
    return jsonify({"success": True, "listing_id": listing_id, "is_dismissed": is_dis})

# ----------------- Scanner & Session API -----------------

@app.route("/api/scanner/status", methods=["GET"])
def api_scanner_status():
    status = scan_manager.get_status()
    session_info = get_session_info()
    status["session"] = session_info
    return jsonify({"success": True, "status": status})

@app.route("/api/scanner/run", methods=["POST"])
def api_scanner_run():
    data = request.json or {}
    filter_id = data.get("filter_id")
    if filter_id:
        scan_manager.run_scan_for_filter(int(filter_id))
    else:
        scan_manager.run_scan_all()
    return jsonify({"success": True, "message": "Scan started in background."})

@app.route("/api/session/status", methods=["GET"])
def api_session_status():
    info = get_session_info()
    return jsonify({"success": True, "session": info})

@app.route("/api/session/login", methods=["POST"])
def api_session_login():
    """Starts interactive login with real browser (Brave/Chrome) with desktop window station."""
    def run_interactive():
        import subprocess
        # On Windows, launching via explorer/start ensures interactive desktop focus
        try:
            bat_path = os.path.join(Config.BASE_DIR, "Connect-Facebook.bat")
            if os.path.exists(bat_path):
                subprocess.Popen(["cmd.exe", "/c", "start", "", bat_path], shell=True)
            else:
                capture_interactive_login(timeout_seconds=300)
        except Exception:
            capture_interactive_login(timeout_seconds=300)

    t = threading.Thread(target=run_interactive, daemon=True)
    t.start()
    return jsonify({
        "success": True,
        "message": "Interactive browser launched on your desktop. You can also paste your cookies below for instant connection."
    })

@app.route("/api/session/cookies", methods=["POST"])
def api_session_cookies():
    data = request.json or {}
    cookie_val = data.get("cookies") or data.get("raw") or data
    res = save_raw_cookies(cookie_val)
    if res.get("success"):
        return jsonify(res)
    return jsonify(res), 400

# ----------------- Settings & Logs API -----------------

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify({
        "success": True,
        "settings": {
            "alert_email": get_setting("alert_email", Config.DEFAULT_ALERT_EMAIL),
            "auto_scan_enabled": get_setting("auto_scan_enabled", "0") == "1",
            "scan_interval_minutes": int(get_setting("scan_interval_minutes", "60"))
        }
    })

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.json or {}
    if "alert_email" in data:
        set_setting("alert_email", str(data["alert_email"]).strip())
    if "auto_scan_enabled" in data:
        set_setting("auto_scan_enabled", "1" if data["auto_scan_enabled"] else "0")
    if "scan_interval_minutes" in data:
        set_setting("scan_interval_minutes", str(data["scan_interval_minutes"]))
    return jsonify({"success": True, "message": "Settings updated"})

@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    logs = get_scan_logs(limit=30)
    return jsonify({"success": True, "logs": logs})

if __name__ == "__main__":
    print(f"Starting Facebook Marketplace Scanner on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)
