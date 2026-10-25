import os
import time
import threading
import urllib.request
from flask import Flask, jsonify, request, send_from_directory, Response, send_file
from backend.config import Config
from backend.db import (
    init_db, get_filters, get_filter, save_filter, delete_filter,
    get_listings, update_listing_status, get_scan_logs,
    get_setting, set_setting,
    get_interests, add_interest, delete_interest,
    toggle_interest_instant_alert, record_listing_interest
)
from backend.scraper import get_session_info, capture_interactive_login, save_raw_cookies
from backend.scheduler import scan_manager
from backend.product_analyzer import (
    get_condensed_products, set_product_category_interest, reconcile_all_excluded_interests
)
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

@app.route("/login")
def login():
    return send_from_directory(app.static_folder, "login.html")

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
    interest_status = request.args.get("interest_status", "all")
    show_dismissed = request.args.get("show_dismissed", "0") in ("1", "true")
    only_favorites = request.args.get("only_favorites", "0") in ("1", "true")
    include_expired = request.args.get("include_expired", "0") in ("1", "true")
    
    retention_setting = int(get_setting("listing_retention_days", "14"))
    max_age_days = request.args.get("max_age_days", retention_setting, type=int)
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    items = get_listings(
        filter_id=filter_id,
        keyword=keyword,
        interest_status=interest_status,
        show_dismissed=show_dismissed,
        only_favorites=only_favorites,
        include_expired=include_expired,
        max_age_days=max_age_days,
        limit=limit,
        offset=offset
    )

    total_active = 0
    try:
        from backend.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cutoff = time.time() - (max_age_days * 86400) if max_age_days > 0 else 0
        cursor.execute("SELECT COUNT(*) as cnt FROM listings WHERE is_dismissed = 0 AND interest_status != 'not_interested' AND first_seen >= ?", (cutoff,))
        row = cursor.fetchone()
        if row:
            total_active = row["cnt"]
        conn.close()
    except Exception:
        pass

    return jsonify({"success": True, "listings": items, "count": len(items), "total_active": total_active})

@app.route("/api/image-proxy", methods=["GET"])
def api_image_proxy():
    image_url = request.args.get("url")
    listing_id = request.args.get("id") or ""
    placeholder_svg = b'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
        <rect width="300" height="300" fill="#1e293b"/>
        <text x="50%" y="46%" dominant-baseline="middle" text-anchor="middle" font-size="44" fill="#64748b">&#x1F4E6;</text>
        <text x="50%" y="64%" dominant-baseline="middle" text-anchor="middle" font-size="13" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" font-weight="600" fill="#94a3b8">Marketplace Item</text>
    </svg>'''

    # 1. Check local persistent disk cache
    cache_dir = Config.DATA_DIR / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if listing_id:
        cached_file = cache_dir / f"{listing_id}.jpg"
        if cached_file.exists() and cached_file.stat().st_size > 500:
            return send_file(str(cached_file), mimetype="image/jpeg", max_age=2592000)

    # 2. Download and save to disk if URL is available
    if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://www.facebook.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        try:
            req = urllib.request.Request(image_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                if len(data) > 500 and listing_id:
                    try:
                        with open(cache_dir / f"{listing_id}.jpg", "wb") as f:
                            f.write(data)
                    except Exception:
                        pass
                return Response(data, mimetype=content_type, headers={
                    "Cache-Control": "public, max-age=2592000",
                    "Access-Control-Allow-Origin": "*"
                })
        except Exception:
            pass

    return Response(placeholder_svg, mimetype="image/svg+xml", headers={
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*"
    })

@app.route("/api/listings/<listing_id>/interest", methods=["POST"])
def api_set_listing_interest(listing_id):
    data = request.json or {}
    status = data.get("status", "none")  # 'interested', 'not_interested', 'none'
    res = record_listing_interest(listing_id, status)
    return jsonify(res)

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

# ----------------- User Interest Profile API -----------------

@app.route("/api/interests", methods=["GET"])
def api_get_interests():
    itype = request.args.get("type")
    items = get_interests(interest_type=itype)
    return jsonify({"success": True, "interests": items})

@app.route("/api/interests", methods=["POST"])
def api_add_interest():
    data = request.json or {}
    kw = data.get("keyword", "").strip()
    instant = bool(data.get("instant_alert", True))
    itype = data.get("type", "interested")
    if not kw:
        return jsonify({"success": False, "error": "Keyword required"}), 400
    item_id = add_interest(kw, instant_alert=instant, interest_type=itype)
    return jsonify({"success": True, "id": item_id, "message": f"Added '{kw}' to {itype} list."})

@app.route("/api/interests/<int:interest_id>", methods=["DELETE"])
def api_delete_interest(interest_id):
    delete_interest(interest_id)
    return jsonify({"success": True, "message": "Interest removed."})

@app.route("/api/interests/<int:interest_id>/toggle-alert", methods=["POST"])
def api_toggle_interest_alert(interest_id):
    new_state = toggle_interest_instant_alert(interest_id)
    return jsonify({"success": True, "instant_alert": new_state})

@app.route("/api/interests/reconcile", methods=["POST"])
def api_reconcile_interests():
    res = reconcile_all_excluded_interests()
    return jsonify(res)

# ----------------- Condensed Products Catalog API -----------------

@app.route("/api/products/condensed", methods=["GET"])
def api_get_condensed_products():
    days = int(request.args.get("days", 365))
    prods = get_condensed_products(days=days)
    return jsonify({"success": True, "products": prods, "count": len(prods)})

@app.route("/api/products/<product_slug>/interest", methods=["POST"])
def api_set_product_interest(product_slug):
    data = request.json or {}
    status = data.get("status", "none")
    instant = bool(data.get("instant_alert", False))
    res = set_product_category_interest(product_slug, status=status, instant_alert=instant)
    return jsonify(res)

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
    try:
        if filter_id is not None and str(filter_id).isdigit():
            scan_manager.run_scan_for_filter(int(filter_id))
        else:
            scan_manager.run_scan_all()
        return jsonify({"success": True, "message": "Scan started in background."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(500)
def handle_500_error(e):
    return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(400)
def handle_400_error(e):
    return jsonify({"success": False, "error": str(e)}), 400

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
            "auto_scan_enabled": get_setting("auto_scan_enabled", "1") == "1",
            "scan_interval_minutes": int(get_setting("scan_interval_minutes", "60")),
            "listing_retention_days": int(get_setting("listing_retention_days", "14"))
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
    if "listing_retention_days" in data:
        set_setting("listing_retention_days", str(int(data["listing_retention_days"])))
    return jsonify({"success": True, "message": "Settings updated"})

@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    logs = get_scan_logs(limit=30)
    return jsonify({"success": True, "logs": logs})

if __name__ == "__main__":
    print(f"Starting Facebook Marketplace Scanner on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)
