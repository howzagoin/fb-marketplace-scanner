# Facebook Marketplace Scanner & Web UI

Automated local Facebook Marketplace scanner designed to detect free items (or targeted search terms) within a customizable radius (e.g., Postcode 3011, 50km radius), filter results, and display them in a modern web dashboard with email alerts.

## Features

- **Web Dashboard**: Modern, responsive UI to inspect scraped Marketplace items, filter by keywords, star favorites, and dismiss viewed items.
- **Dynamic Search Rules & Filters Editor**:
  - Add and edit custom search terms (e.g. *Free Tools*, *Lawn Mowers*, *Furniture*, or empty for general feed).
  - Configurable Postcode (default `3011` / Footscray) and radius (default `50km`).
  - Price constraints (default `$0` for 100% Free items).
  - Per-rule toggles and notification switches.
- **Facebook 2FA Session Persistence**:
  - Launch an interactive browser session (`Connect Facebook (2FA)` in the UI) to complete login and 2-Factor Authentication safely once.
  - Automatically captures and saves authentication state locally to `data/session/fb_session.json` (excluded from git via `.gitignore`).
  - Reuses authenticated session for background headless scrapes without stalling.
- **Alert Dispatcher**:
  - Sends email notifications for newly found items to configured recipient (`maclatchy@gmail.com`).
  - Formatted HTML listing previews with image, title, price, location, and direct listing link.
- **Automated Scheduling**:
  - Built-in background scheduler for automated scans while running locally.
  - Hourly GitHub Actions runner workflow included in `.github/workflows/marketplace-scan.yml`.

---

## Architecture & File Structure

```
fb-marketplace-scanner/
├── app.py                      # Flask backend API & static server
├── backend/
│   ├── config.py               # Settings, directories, and .env parser
│   ├── db.py                   # SQLite storage for filters, listings, and logs
│   ├── scraper.py              # Playwright scraper with session & stealth support
│   ├── notifier.py             # Email notification engine
│   └── scheduler.py           # Background scan thread manager
├── schema.py                   # Data schema definitions for filters & listings
├── static/
│   ├── index.html              # Single-page web dashboard
│   ├── css/
│   │   └── styles.css          # Responsive styling & themes
│   └── js/
│       └── main.js             # Client-side reactivity and API connectors
├── data/                       # Local SQLite DB and session storage (gitignored)
├── .github/workflows/          # GitHub Actions hourly scan workflow
└── requirements.txt            # Python dependencies
```

---

## Local Setup & Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run Web Dashboard
```bash
python app.py
```
Open your browser to: **`http://127.0.0.1:5055`**

---

## Facebook 2FA Setup

1. In the Web UI, click the **"🔑 Connect Facebook (2FA)"** button in the header.
2. A browser window will open to Facebook.
3. Enter your Facebook credentials, complete 2-Factor Authentication (2FA), and confirm "Trust this device".
4. Once you are logged in, the scanner automatically detects the authenticated cookies and saves your session to `data/session/fb_session.json`.
5. The session indicator in the header will turn green: **"Facebook: Connected"**.

---

## Configuring Email Alerts

Copy `.env.example` to `.env` (optional for local SMTP):
```ini
ALERT_EMAIL=maclatchy@gmail.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
```
If SMTP credentials are not configured, the app simulates notifications and logs formatted email payloads to the console/activity log.

---

## Hourly GitHub Actions Automation

The repository includes `.github/workflows/marketplace-scan.yml`. To enable automated hourly scanning on GitHub:
1. In your GitHub repository, navigate to **Settings > Secrets and variables > Actions**.
2. Add the following secrets if email delivery is required:
   - `ALERT_EMAIL`: `maclatchy@gmail.com`
   - `SMTP_USER`: your sending email address
   - `SMTP_PASS`: your sending app password
3. The workflow runs on an hourly cron (`0 * * * *`) and can also be manually triggered via `Run workflow`.
