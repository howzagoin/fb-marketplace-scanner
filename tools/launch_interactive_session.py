import os
import sys
import time
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import Config
from backend.scraper import get_browser_executable

SSH_KEY = r"C:\Users\Timothy.MacLatchy\.ssh\OracleKey"
VPS_HOST = "ubuntu@152.69.184.192"
REMOTE_SESSION = "/home/ubuntu/fb-marketplace-scanner/data/session/fb_session.json"

def sync_to_vps():
    local_session = str(Config.SESSION_FILE)
    print(f"[*] Syncing {local_session} to VPS...")
    cmd_scp = [
        "scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
        local_session, f"{VPS_HOST}:{REMOTE_SESSION}"
    ]
    subprocess.run(cmd_scp, check=True)
    print("[+] Session file transferred to VPS successfully.")

    print("[*] Restarting fb-marketplace service on VPS...")
    cmd_restart = [
        "ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
        VPS_HOST, "sudo systemctl restart fb-marketplace.service"
    ]
    subprocess.run(cmd_restart, check=True)
    print("[+] Service restarted on VPS.")

def main():
    profile_dir = Config.DATA_DIR / "scraper_fb_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    browser_exe = get_browser_executable()
    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run",
            "--window-size=1200,800"
        ]
    }
    if browser_exe:
        launch_kwargs["executable_path"] = browser_exe

    print("[*] Launching dedicated sign-in window in isolated profile...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=45000)
        print("[*] Window opened. Please complete the login/reCAPTCHA check in the opened window.")

        # Poll for c_user and xs cookies for up to 300 seconds
        deadline = time.time() + 300
        saved = False
        while time.time() < deadline:
            cookies = context.cookies(["https://www.facebook.com/", "https://facebook.com/"])
            fb_cookies = [c for c in cookies if c.get("domain", "").lstrip(".") in ("facebook.com", "www.facebook.com")]
            names = {c.get("name") for c in fb_cookies if c.get("value") and (c.get("expires", -1) <= 0 or c["expires"] > time.time())}
            
            if {"c_user", "xs"}.issubset(names):
                print("[+] Active login cookies detected!")
                Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
                session_data = {
                    "cookies": fb_cookies,
                    "origins": [],
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(Config.SESSION_FILE, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, indent=2)
                print(f"[+] Saved session to {Config.SESSION_FILE}")
                
                try:
                    sync_to_vps()
                    print("[+] Fully synchronized with VPS!")
                except Exception as e:
                    print(f"[-] VPS sync error: {e}")
                
                saved = True
                time.sleep(2)
                break
                
            time.sleep(2)

        context.close()
        return saved

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
