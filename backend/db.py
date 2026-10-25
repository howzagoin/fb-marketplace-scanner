import sqlite3
import time
import re
from typing import List, Dict, Any, Optional
from backend.config import Config
from schema import SearchFilter, ListingItem

def get_connection():
    conn = sqlite3.connect(Config.DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Search filters table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_filters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        query TEXT DEFAULT '',
        postcode TEXT DEFAULT '3011',
        radius_km INTEGER DEFAULT 50,
        min_price INTEGER DEFAULT NULL,
        max_price INTEGER DEFAULT 0,
        category TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        notify_email INTEGER DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """)

    # Listings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        listing_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        price TEXT NOT NULL,
        price_num REAL DEFAULT 0,
        location TEXT DEFAULT '',
        url TEXT NOT NULL,
        image_url TEXT DEFAULT '',
        search_filter_id INTEGER,
        first_seen REAL NOT NULL,
        is_favorite INTEGER DEFAULT 0,
        is_dismissed INTEGER DEFAULT 0,
        is_notified INTEGER DEFAULT 0,
        FOREIGN KEY(search_filter_id) REFERENCES search_filters(id)
    )
    """)

    # Scan logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filter_id INTEGER,
        filter_name TEXT DEFAULT '',
        timestamp REAL NOT NULL,
        status TEXT NOT NULL,
        count_found INTEGER DEFAULT 0,
        count_new INTEGER DEFAULT 0,
        error_message TEXT DEFAULT '',
        FOREIGN KEY(filter_id) REFERENCES search_filters(id)
    )
    """)

    # App settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # User product interest & exclusion profiles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL UNIQUE,
        instant_alert INTEGER DEFAULT 1,
        type TEXT DEFAULT 'interested',
        created_at REAL NOT NULL
    )
    """)

    conn.commit()

    # Column migrations for existing tables
    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN interest_status TEXT DEFAULT 'none'")
        conn.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE listings ADD COLUMN instant_match INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # Insert default filter if table is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM search_filters")
    if cursor.fetchone()["cnt"] == 0:
        default_filter = SearchFilter(
            name="Free Items 3011 (50km)",
            query="",
            postcode="3011",
            radius_km=50,
            min_price=None,
            max_price=0,
            enabled=True,
            notify_email=True
        )
        save_filter(default_filter.to_dict())

    # Insert default settings if not exists
    cursor.execute("SELECT COUNT(*) as cnt FROM app_settings WHERE key = 'alert_email'")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("INSERT INTO app_settings (key, value) VALUES ('alert_email', ?)", (Config.DEFAULT_ALERT_EMAIL,))
        cursor.execute("INSERT INTO app_settings (key, value) VALUES ('auto_scan_enabled', '0')")
        cursor.execute("INSERT INTO app_settings (key, value) VALUES ('scan_interval_minutes', '60')")
        cursor.execute("INSERT INTO app_settings (key, value) VALUES ('listing_retention_days', '14')")
        conn.commit()

    cursor.execute("SELECT COUNT(*) as cnt FROM app_settings WHERE key = 'listing_retention_days'")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("INSERT INTO app_settings (key, value) VALUES ('listing_retention_days', '14')")
        conn.commit()

    conn.close()

def get_filters() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM search_filters ORDER BY id ASC")
    rows = cursor.fetchall()
    filters = [dict(row) for row in rows]
    conn.close()
    return filters

def get_filter(filter_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM search_filters WHERE id = ?", (filter_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_filter(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = time.time()
    if data.get("id"):
        cursor.execute("""
        UPDATE search_filters
        SET name = ?, query = ?, postcode = ?, radius_km = ?, min_price = ?, max_price = ?,
            category = ?, enabled = ?, notify_email = ?, updated_at = ?
        WHERE id = ?
        """, (
            data.get("name", "Search Filter"),
            data.get("query", "").strip(),
            data.get("postcode", "3011").strip(),
            int(data.get("radius_km", 50)),
            data.get("min_price"),
            data.get("max_price"),
            data.get("category", "").strip(),
            1 if data.get("enabled", True) else 0,
            1 if data.get("notify_email", True) else 0,
            now,
            data["id"]
        ))
        filter_id = data["id"]
    else:
        cursor.execute("""
        INSERT INTO search_filters (name, query, postcode, radius_km, min_price, max_price, category, enabled, notify_email, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name", "Search Filter"),
            data.get("query", "").strip(),
            data.get("postcode", "3011").strip(),
            int(data.get("radius_km", 50)),
            data.get("min_price"),
            data.get("max_price"),
            data.get("category", "").strip(),
            1 if data.get("enabled", True) else 0,
            1 if data.get("notify_email", True) else 0,
            now,
            now
        ))
        filter_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return filter_id

def delete_filter(filter_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM search_filters WHERE id = ?", (filter_id,))
    conn.commit()
    conn.close()

def get_keyword_match_terms(kw: str) -> List[str]:
    """Expands a keyword or category phrase into exact match tokens and singular forms."""
    cleaned = kw.lower().strip()
    terms = [cleaned]
    parts = [p.strip().lower() for p in re.split(r"[/&,]", cleaned)]
    for p in parts:
        if len(p) >= 3 and p not in terms:
            terms.append(p)
        if p.endswith("s") and len(p) > 4:
            sing = p[:-1]
            if sing not in terms:
                terms.append(sing)
    return terms

def save_listings(items: List[ListingItem]) -> int:
    """Saves listings, applying user interest and exclusion rules, and returns count of newly inserted items."""
    conn = get_connection()
    cursor = conn.cursor()
    new_count = 0
    now = time.time()

    # Load current interest and exclusion keywords
    cursor.execute("SELECT keyword, instant_alert, type FROM user_interests")
    interests = [dict(r) for r in cursor.fetchall()]
    excluded_items = [i for i in interests if i["type"] in ("excluded", "disliked")]
    interested_items = [i for i in interests if i["type"] == "interested"]
    excluded_kws = {i["keyword"].lower() for i in excluded_items}

    # Expand match terms
    excluded_terms = []
    for ek in excluded_kws:
        excluded_terms.extend(get_keyword_match_terms(ek))

    from backend.product_analyzer import (
        PRODUCT_TAXONOMY, classify_listing_title, is_seeking_offers,
        is_priced_item, is_spam_or_wtb, is_generic_filler
    )

    excluded_patterns = []
    for entry in PRODUCT_TAXONOMY:
        if entry["slug"] in excluded_kws or entry["name"].lower() in excluded_kws:
            excluded_patterns.append(re.compile(entry["pattern"], flags=re.IGNORECASE))

    for item in items:
        cursor.execute("SELECT listing_id, interest_status, is_favorite, is_dismissed, instant_match FROM listings WHERE listing_id = ?", (item.listing_id,))
        exists = cursor.fetchone()
        
        # Calculate interest flags based on title, intelligent classification, and price/offer checks
        title_lower = f" {item.title.lower()} "
        classification = classify_listing_title(item.title, price=item.price, price_num=item.price_num or 0.0)
        c_name = classification["name"].lower()
        c_slug = classification["slug"]
        is_offer_seeker = is_seeking_offers(item.title)
        has_price = is_priced_item(title=item.title, price=item.price, price_num=item.price_num or 0.0)
        is_spam = is_spam_or_wtb(item.title)
        is_filler = is_generic_filler(item.title)

        if is_offer_seeker or has_price or is_spam or is_filler:
            auto_dismiss = True
            auto_interested = False
            instant_match = False
        else:
            auto_dismiss = (
                c_name in excluded_kws or
                c_slug in excluded_kws or
                c_slug in ("not-free-priced", "generic-filler-titles") or
                any(pat.search(title_lower) for pat in excluded_patterns) or
                any(re.search(rf"\b{re.escape(term)}\b", title_lower) for term in excluded_terms)
            )

            auto_interested = False
            instant_match = False

            if not auto_dismiss:
                for ii in interested_items:
                    ik = ii["keyword"].lower()
                    ik_terms = get_keyword_match_terms(ik)
                    if (ik in c_name or ik == c_slug or any(re.search(rf"\b{re.escape(t)}\b", title_lower) for t in ik_terms)):
                        auto_interested = True
                        if ii["instant_alert"]:
                            instant_match = True
                        break

        final_interest = "not_interested" if auto_dismiss else ("interested" if auto_interested else "none")
        final_dismissed = 1 if auto_dismiss else (1 if item.is_dismissed else 0)
        final_fav = 0 if auto_dismiss else (1 if item.is_favorite else 0)

        if not exists:
            cursor.execute("""
            INSERT INTO listings (
                listing_id, title, price, price_num, location, url, image_url,
                search_filter_id, first_seen, is_favorite, is_dismissed, is_notified,
                interest_status, instant_match
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.listing_id,
                item.title,
                item.price,
                item.price_num or 0,
                item.location,
                item.url,
                item.image_url,
                item.search_filter_id,
                item.first_seen or now,
                final_fav,
                final_dismissed,
                0,
                final_interest,
                1 if instant_match else 0
            ))
            # Only count as new if it is NOT dismissed/excluded
            if not auto_dismiss:
                new_count += 1
        else:
            existing_interest = exists["interest_status"] or "none"
            existing_fav = exists["is_favorite"]
            existing_dis = exists["is_dismissed"]

            if auto_dismiss:
                use_interest = "not_interested"
                use_fav = 0
                use_dis = 1
                instant_match = False
            elif auto_interested:
                use_interest = "interested"
                use_fav = existing_fav
                use_dis = 0
            else:
                use_interest = existing_interest if existing_interest != "none" else final_interest
                use_fav = existing_fav
                use_dis = existing_dis if existing_interest != "none" else final_dismissed

            cursor.execute("""
            UPDATE listings
            SET title = ?, price = ?, price_num = ?, location = ?, image_url = ?,
                interest_status = ?, is_favorite = ?, is_dismissed = ?, instant_match = ?
            WHERE listing_id = ?
            """, (
                item.title, item.price, item.price_num or 0, item.location, item.image_url,
                use_interest, use_fav, use_dis, 1 if instant_match else 0, item.listing_id
            ))

    conn.commit()
    conn.close()
    return new_count

def get_listings(
    filter_id: Optional[int] = None,
    keyword: Optional[str] = None,
    interest_status: Optional[str] = None,
    show_dismissed: bool = False,
    only_favorites: bool = False,
    include_expired: bool = False,
    max_age_days: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    if max_age_days is None:
        try:
            cursor.execute("SELECT value FROM app_settings WHERE key = 'listing_retention_days'")
            r = cursor.fetchone()
            max_age_days = int(r["value"]) if r else 14
        except Exception:
            max_age_days = 14

    conditions = []
    params = []

    if filter_id:
        conditions.append("l.search_filter_id = ?")
        params.append(filter_id)

    if interest_status == "not_interested":
        conditions.append("l.interest_status = 'not_interested'")
    else:
        if not show_dismissed:
            conditions.append("l.is_dismissed = 0")
            conditions.append("l.interest_status != 'not_interested'")
            if not include_expired and max_age_days > 0:
                cutoff = time.time() - (max_age_days * 86400)
                conditions.append("l.first_seen >= ?")
                params.append(cutoff)

        if interest_status and interest_status != "all":
            conditions.append("l.interest_status = ?")
            params.append(interest_status)

    if only_favorites:
        conditions.append("l.is_favorite = 1")

    if keyword and keyword.strip():
        conditions.append("(l.title LIKE ? OR l.location LIKE ?)")
        kw = f"%{keyword.strip()}%"
        params.extend([kw, kw])

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
    SELECT l.*, f.name as filter_name
    FROM listings l
    LEFT JOIN search_filters f ON l.search_filter_id = f.id
    {where_clause}
    ORDER BY l.instant_match DESC, l.is_favorite DESC, l.first_seen DESC
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    listings = [dict(r) for r in rows]
    conn.close()
    return listings

def update_listing_status(listing_id: str, is_favorite: Optional[bool] = None, is_dismissed: Optional[bool] = None):
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if is_favorite is not None:
        updates.append("is_favorite = ?")
        params.append(1 if is_favorite else 0)
    if is_dismissed is not None:
        updates.append("is_dismissed = ?")
        params.append(1 if is_dismissed else 0)
    if updates:
        params.append(listing_id)
        cursor.execute(f"UPDATE listings SET {', '.join(updates)} WHERE listing_id = ?", params)
        conn.commit()
    conn.close()

# ----------------- User Interests & Profile Matching -----------------

def get_interests(interest_type: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if interest_type:
        cursor.execute("SELECT * FROM user_interests WHERE type = ? ORDER BY instant_alert DESC, id DESC", (interest_type,))
    else:
        cursor.execute("SELECT * FROM user_interests ORDER BY type ASC, instant_alert DESC, id DESC")
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def add_interest(keyword: str, instant_alert: bool = True, interest_type: str = "interested") -> int:
    kw_clean = keyword.strip()
    if not kw_clean:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    now = time.time()
    # Check if keyword already exists case-insensitively
    cursor.execute("SELECT id FROM user_interests WHERE LOWER(keyword) = ?", (kw_clean.lower(),))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
        UPDATE user_interests
        SET keyword = ?, instant_alert = ?, type = ?
        WHERE id = ?
        """, (kw_clean, 1 if instant_alert else 0, interest_type, row["id"]))
        item_id = row["id"]
    else:
        cursor.execute("""
        INSERT INTO user_interests (keyword, instant_alert, type, created_at)
        VALUES (?, ?, ?, ?)
        """, (kw_clean, 1 if instant_alert else 0, interest_type, now))
        item_id = cursor.lastrowid

    # If an exclusion is added, retroactively dismiss matching listings
    if interest_type in ("excluded", "disliked"):
        from backend.product_analyzer import classify_listing_title
        match_terms = get_keyword_match_terms(kw_clean)
        cursor.execute("SELECT listing_id, title FROM listings WHERE interest_status != 'interested'")
        for row_l in cursor.fetchall():
            l_id = row_l["listing_id"]
            l_title = (row_l["title"] or "")
            l_title_lower = l_title.lower()
            cls = classify_listing_title(l_title)
            c_name = cls["name"].lower()
            c_slug = cls["slug"].lower()

            if (
                kw_clean.lower() in (c_name, c_slug)
                or any(re.search(rf"\b{re.escape(term)}\b", l_title_lower) for term in match_terms)
            ):
                cursor.execute("""
                UPDATE listings
                SET interest_status = 'not_interested', is_favorite = 0, is_dismissed = 1, instant_match = 0
                WHERE listing_id = ?
                """, (l_id,))

    conn.commit()
    conn.close()
    return item_id

def delete_interest(interest_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_interests WHERE id = ?", (interest_id,))
    conn.commit()
    conn.close()

def toggle_interest_instant_alert(interest_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT instant_alert FROM user_interests WHERE id = ?", (interest_id,))
    row = cursor.fetchone()
    new_state = False
    if row:
        new_state = not bool(row["instant_alert"])
        cursor.execute("UPDATE user_interests SET instant_alert = ? WHERE id = ?", (1 if new_state else 0, interest_id))
        conn.commit()
    conn.close()
    return new_state

def record_listing_interest(listing_id: str, status: str) -> Dict[str, Any]:
    """
    Sets interest status for a listing and updates user_interests using
    intelligent product classification instead of raw split words.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM listings WHERE listing_id = ?", (listing_id,))
    row = cursor.fetchone()
    title = row["title"] if row else ""

    if status == "interested":
        cursor.execute("""
        UPDATE listings
        SET interest_status = 'interested', is_dismissed = 0
        WHERE listing_id = ?
        """, (listing_id,))
    elif status == "not_interested":
        cursor.execute("""
        UPDATE listings
        SET interest_status = 'not_interested', is_favorite = 0, is_dismissed = 1
        WHERE listing_id = ?
        """, (listing_id,))
    else:
        cursor.execute("""
        UPDATE listings
        SET interest_status = 'none'
        WHERE listing_id = ?
        """, (listing_id,))

    conn.commit()
    conn.close()

    keywords_affected = []
    if title:
        from backend.product_analyzer import classify_listing_title
        classification = classify_listing_title(title)
        canonical_name = classification["name"]
        slug = classification["slug"]

        if status == "interested":
            add_interest(canonical_name, instant_alert=False, interest_type="interested")
            keywords_affected.append(canonical_name)
        elif status == "not_interested":
            add_interest(canonical_name, instant_alert=False, interest_type="excluded")
            keywords_affected.append(canonical_name)

            # Also dismiss other listings sharing this classified category
            conn2 = get_connection()
            c2 = conn2.cursor()
            c2.execute("SELECT listing_id, title FROM listings WHERE listing_id != ?", (listing_id,))
            for other in c2.fetchall():
                other_cls = classify_listing_title(other["title"] or "")
                if other_cls["slug"] == slug:
                    c2.execute("""
                    UPDATE listings
                    SET interest_status = 'not_interested', is_favorite = 0, is_dismissed = 1
                    WHERE listing_id = ?
                    """, (other["listing_id"],))
            conn2.commit()
            conn2.close()
        elif status == "none":
            conn2 = get_connection()
            c2 = conn2.cursor()
            c2.execute("DELETE FROM user_interests WHERE LOWER(keyword) = ?", (canonical_name.lower(),))
            conn2.commit()
            conn2.close()

    return {"success": True, "status": status, "keywords": keywords_affected}

def record_scan_log(filter_id: Optional[int], filter_name: str, status: str, count_found: int, count_new: int, error: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO scan_logs (filter_id, filter_name, timestamp, status, count_found, count_new, error_message)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (filter_id, filter_name, time.time(), status, count_found, count_new, error))
    conn.commit()
    conn.close()

def get_scan_logs(limit: int = 25) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scan_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    logs = [dict(r) for r in rows]
    conn.close()
    return logs

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()
    conn.close()
