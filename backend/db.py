import sqlite3
import time
from typing import List, Dict, Any, Optional
from backend.config import Config
from schema import SearchFilter, ListingItem

def get_connection():
    conn = sqlite3.connect(Config.DB_FILE)
    conn.row_factory = sqlite3.Row
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

    conn.commit()

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

def save_listings(items: List[ListingItem]) -> int:
    """Saves listings and returns count of newly inserted items."""
    conn = get_connection()
    cursor = conn.cursor()
    new_count = 0
    now = time.time()

    for item in items:
        cursor.execute("SELECT listing_id FROM listings WHERE listing_id = ?", (item.listing_id,))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("""
            INSERT INTO listings (listing_id, title, price, price_num, location, url, image_url, search_filter_id, first_seen, is_favorite, is_dismissed, is_notified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1 if item.is_favorite else 0,
                0,
                0
            ))
            new_count += 1
        else:
            # Update title, price, location in case they changed
            cursor.execute("""
            UPDATE listings
            SET title = ?, price = ?, price_num = ?, location = ?, image_url = ?
            WHERE listing_id = ?
            """, (item.title, item.price, item.price_num or 0, item.location, item.image_url, item.listing_id))

    conn.commit()
    conn.close()
    return new_count

def get_listings(
    filter_id: Optional[int] = None,
    keyword: Optional[str] = None,
    show_dismissed: bool = False,
    only_favorites: bool = False,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if filter_id:
        conditions.append("l.search_filter_id = ?")
        params.append(filter_id)

    if not show_dismissed:
        conditions.append("l.is_dismissed = 0")

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
    ORDER BY l.first_seen DESC
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
