import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SESSION_DIR = DATA_DIR / "session"
SESSION_FILE = SESSION_DIR / "fb_session.json"
DB_FILE = DATA_DIR / "marketplace.db"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Load environment
load_dotenv(BASE_DIR / ".env")

class Config:
    # Web server
    PORT = int(os.environ.get("MARKETPLACE_PORT") or os.environ.get("PORT_MARKETPLACE") or 5080)
    HOST = os.environ.get("HOST", "127.0.0.1")
    SECRET_KEY = os.environ.get("SECRET_KEY", "fb-marketplace-scanner-dev-key")

    # Facebook Defaults
    DEFAULT_POSTCODE = os.environ.get("DEFAULT_POSTCODE", "3011")  # Footscray, VIC
    DEFAULT_RADIUS_KM = int(os.environ.get("DEFAULT_RADIUS_KM", 50))
    DEFAULT_MAX_PRICE = int(os.environ.get("DEFAULT_MAX_PRICE", 0))  # 0 = Free
    
    # Notification settings
    DEFAULT_ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "maclatchy@gmail.com")
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")

    # Scraper settings
    HEADLESS = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")
    DATA_DIR = DATA_DIR
    SESSION_DIR = SESSION_DIR
    SESSION_FILE = SESSION_FILE
    DB_FILE = DB_FILE
