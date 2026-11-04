import os
import sys
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import Config
from backend.scraper import get_browser_executable

def attempt_login(email: str, password: str) -> bool:
    profile_dir = Config.DATA_DIR / f"profile_{email.split('@')[0]}"
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    browser_exe = get_browser_executable()
    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run",
            "--window-size=1280,800"
        ]
    }
    if browser_exe:
        launch_kwargs["executable_path"] = browser_exe

    print(f"[*] Attempting login for {email} with profile at {profile_dir}...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()

        print("[*] Navigating to Facebook login...")
        page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)

        # Check if already logged in
        cookies = context.cookies(["https://www.facebook.com/", "https://facebook.com/"])
        names = {c.get("name") for c in cookies}
        if {"c_user", "xs"}.issubset(names):
            print("[+] Already logged in!")
        else:
            print("[*] Filling login form...")
            try:
                for btn_text in ["Allow all cookies", "Only allow essential cookies", "Accept all"]:
                    banner_btn = page.locator(f"button:has-text('{btn_text}')")
                    if banner_btn.count() > 0 and banner_btn.first.is_visible():
                        banner_btn.first.click()
                        time.sleep(1)
            except Exception:
                pass

            email_input = page.locator("input[name='email'], input#email")
            pass_input = page.locator("input[name='pass'], input#pass")

            if email_input.count() > 0:
                email_input.first.fill(email)
                time.sleep(0.5)

            if pass_input.count() > 0:
                pass_input.first.fill(password)
                time.sleep(0.5)

            login_btn = page.locator("button[name='login'], button#loginbutton, button[type='submit']")
            if login_btn.count() > 0 and login_btn.first.is_visible():
                login_btn.first.click()
            else:
                pass_input.first.press("Enter")

            print("[*] Form submitted. Waiting for response...")

        deadline = time.time() + 30
        logged_in = False
        while time.time() < deadline:
            cookies = context.cookies(["https://www.facebook.com/", "https://facebook.com/"])
            fb_cookies = [c for c in cookies if c.get("domain", "").lstrip(".") in ("facebook.com", "www.facebook.com")]
            names = {c.get("name") for c in fb_cookies if c.get("value") and (c.get("expires", -1) <= 0 or c["expires"] > time.time())}
            
            if {"c_user", "xs"}.issubset(names):
                logged_in = True
                print(f"[+] Login SUCCESS! Found c_user and xs cookies.")
                c_user_val = next((c.get("value") for c in fb_cookies if c.get("name") == "c_user"), None)
                print(f"[+] User ID (c_user): {c_user_val}")
                
                Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
                session_data = {
                    "cookies": fb_cookies,
                    "origins": [],
                    "account": email,
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(Config.SESSION_FILE, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, indent=2)
                print(f"[+] Saved session to {Config.SESSION_FILE}")
                break

            try:
                err_el = page.locator("div._9ay7, div[role='alert']")
                if err_el.count() > 0 and err_el.first.is_visible():
                    print(f"[-] Facebook Alert: {err_el.first.inner_text()}")
            except Exception:
                pass

            time.sleep(2)

        if not logged_in:
            print("[-] Login not achieved. Current URL:", page.url)
            screenshot_path = Config.DATA_DIR / f"login_{email.split('@')[0]}.png"
            page.screenshot(path=str(screenshot_path))
            print(f"[-] Screenshot saved to {screenshot_path}")

        context.close()
        return logged_in

if __name__ == "__main__":
    target_email = sys.argv[1] if len(sys.argv) > 1 else "aussiebloke31@gmail.com"
    target_pass = sys.argv[2] if len(sys.argv) > 2 else "barkleystreet"
    success = attempt_login(target_email, target_pass)
    sys.exit(0 if success else 1)
