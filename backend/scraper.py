import os
import re
import sys
import time
import json
import logging
import math
import urllib.request
import tempfile
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urlsplit
from playwright.sync_api import sync_playwright

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Config
from schema import SearchFilter, ListingItem

logger = logging.getLogger(__name__)
_rejected_session = None
_verified_session = None

def _session_signature():
    try:
        stat = Config.SESSION_FILE.stat()
        return (str(Config.SESSION_FILE), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None

def mark_session_rejected():
    """Remember Facebook's rejection until the saved session is replaced."""
    global _rejected_session
    _rejected_session = _session_signature()

def get_browser_executable() -> Optional[str]:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def get_city_slug_for_postcode(postcode: str) -> str:
    try:
        pc = int(postcode.strip())
        if 3000 <= pc <= 3999 or 8000 <= pc <= 8999:
            return "melbourne"
        elif 2000 <= pc <= 2599 or 2619 <= pc <= 2899 or 2921 <= pc <= 2999:
            return "sydney"
        elif 4000 <= pc <= 4999 or 9000 <= pc <= 9999:
            return "brisbane"
        elif 5000 <= pc <= 5799:
            return "adelaide"
        elif 6000 <= pc <= 6797:
            return "perth"
        elif 7000 <= pc <= 7799:
            return "hobart"
        elif 2600 <= pc <= 2618 or 2900 <= pc <= 2920:
            return "canberra"
        elif 800 <= pc <= 899:
            return "darwin"
    except Exception:
        pass
    return "melbourne"

def get_approx_coordinates(postcode: str) -> Dict[str, float]:
    pc = str(postcode).strip()
    if pc.startswith("3"):  # Victoria / Melbourne (3011 is Footscray approx -37.80, 144.90)
        return {"latitude": -37.8000, "longitude": 144.9000}
    elif pc.startswith("2"):  # Sydney
        return {"latitude": -33.8688, "longitude": 151.2093}
    elif pc.startswith("4"):  # Brisbane
        return {"latitude": -27.4698, "longitude": 153.0251}
    elif pc.startswith("5"):  # Adelaide
        return {"latitude": -34.9285, "longitude": 138.6007}
    elif pc.startswith("6"):  # Perth
        return {"latitude": -31.9505, "longitude": 115.8605}
    return {"latitude": -37.8136, "longitude": 144.9631}

def build_marketplace_url(f: SearchFilter) -> str:
    city = get_city_slug_for_postcode(f.postcode)
    
    # Facebook has a dedicated /free/ category endpoint that accurately displays local free items
    if (f.max_price == 0 or (f.max_price is not None and f.max_price <= 0)) and (not f.query or not f.query.strip()):
        return f"https://www.facebook.com/marketplace/{city}/free/"

    params = []
    if f.query and f.query.strip():
        params.append(f"query={quote(f.query.strip())}")
    
    if f.max_price is not None:
        params.append(f"maxPrice={f.max_price}")
        
    if f.min_price is not None:
        params.append(f"minPrice={f.min_price}")
        
    if f.radius_km:
        params.append(f"radius={f.radius_km}")
        
    # Sort by creation time (newest first)
    params.append("sortBy=creation_time_descend")
    
    query_str = "&".join(params)
    url = f"https://www.facebook.com/marketplace/{city}/search/?{query_str}"
    return url

def is_session_valid() -> bool:
    """Checks if a saved session file exists and contains essential cookies."""
    if Config.SESSION_FILE.exists() and _session_signature() != _rejected_session:
        try:
            with open(Config.SESSION_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                cookies = data.get("cookies", [])
                essential = {
                    c.get("name") for c in cookies
                    if c.get("value")
                    and c.get("domain", "").lstrip(".") in ("facebook.com", "www.facebook.com")
                    and (c.get("expires", -1) <= 0 or c["expires"] > time.time())
                }
                if {"c_user", "xs"}.issubset(essential):
                    return True
        except Exception:
            pass
    return False

def get_session_info() -> Dict[str, Any]:
    valid = is_session_valid()
    verified = valid and _verified_session == _session_signature()
    modified_time = None
    if Config.SESSION_FILE.exists():
        modified_time = Config.SESSION_FILE.stat().st_mtime
    return {
        "valid": valid,
        "verified": verified,
        "status_text": "Active" if verified else ("Saved (not verified)" if valid else "Needs Login"),
        "exists": Config.SESSION_FILE.exists() or valid,
        "path": str(Config.SESSION_FILE),
        "last_saved": modified_time
    }

def save_raw_cookies(cookie_input: Any) -> Dict[str, Any]:
    """
    Parses and saves cookies from string, list, or dict into Playwright storage_state format.
    Accepts:
      - JSON list of cookie dicts
      - Semi-colon separated string (e.g. 'c_user=123; xs=abc...')
      - Dict with 'c_user', 'xs', etc.
    """
    cookie_list = []
    
    if isinstance(cookie_input, str):
        cookie_input = cookie_input.strip()
        if cookie_input.startswith("[") or cookie_input.startswith("{"):
            try:
                parsed = json.loads(cookie_input)
                if isinstance(parsed, list):
                    cookie_list = parsed
                elif isinstance(parsed, dict):
                    if "cookies" in parsed:
                        cookie_list = parsed["cookies"]
                    else:
                        for k, v in parsed.items():
                            cookie_list.append({"name": k, "value": str(v), "domain": ".facebook.com", "path": "/"})
            except (ValueError, TypeError):
                return {"success": False, "error": "Invalid cookie JSON."}
        
        if not cookie_list:
            # Parse header string: c_user=123; xs=abc
            pairs = cookie_input.split(";")
            for p in pairs:
                if "=" in p:
                    k, v = p.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k and v:
                        cookie_list.append({
                            "name": k,
                            "value": v,
                            "domain": ".facebook.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": k in ("xs", "sb", "fr"),
                            "sameSite": "None"
                        })
    elif isinstance(cookie_input, list):
        cookie_list = cookie_input
    elif isinstance(cookie_input, dict):
        if "cookies" in cookie_input:
            cookie_list = cookie_input["cookies"]
        else:
            for k, v in cookie_input.items():
                cookie_list.append({"name": k, "value": str(v), "domain": ".facebook.com", "path": "/"})

    # Standardize cookies for Playwright
    if not isinstance(cookie_list, list) or not all(isinstance(c, dict) for c in cookie_list):
        return {"success": False, "error": "Cookies must be a list of cookie objects."}
    formatted_cookies = []
    essential_names = set()
    for c in cookie_list:
        name = c.get("name")
        val = c.get("value")
        if not name or not val:
            continue
        try:
            expires = float(c.get("expires", -1))
        except (ValueError, TypeError, OverflowError):
            return {"success": False, "error": "Cookie expiry must be a finite number."}
        if not math.isfinite(expires):
            return {"success": False, "error": "Cookie expiry must be a finite number."}
        domain = c.get("domain", ".facebook.com")
        if not isinstance(domain, str) or domain.lstrip(".") not in ("facebook.com", "www.facebook.com"):
            continue
        if name in ("c_user", "xs") and (expires <= 0 or expires > time.time()):
            essential_names.add(name)
        same_site_raw = str(c.get("sameSite", "")).lower()
        if "strict" in same_site_raw:
            same_site = "Strict"
        elif "lax" in same_site_raw:
            same_site = "Lax"
        else:
            same_site = "None"

        formatted_cookies.append({
            "name": str(name),
            "value": str(val),
            "domain": domain,
            "path": c.get("path", "/"),
            "expires": expires,
            "httpOnly": bool(c.get("httpOnly", name in ("xs", "sb", "fr"))),
            "secure": bool(c.get("secure", True)),
            "sameSite": same_site
        })

    if not {"c_user", "xs"}.issubset(essential_names):
        return {"success": False, "error": "Include nonempty, unexpired Facebook c_user and xs cookies."}

    storage_state = {
        "cookies": formatted_cookies,
        "origins": []
    }

    Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    with open(Config.SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)

    return {"success": True, "message": f"Saved {len(formatted_cookies)} cookies. Run a scan to verify Facebook access."}

def capture_interactive_login(timeout_seconds: int = 600) -> Dict[str, Any]:
    """
    Safely captures Facebook session cookies for the dedicated secondary scraper account.
    Always uses an isolated browser profile (never touches or checks open daily browser tabs).
    """
    if sys.platform != "win32":
        return {"success": False, "message": "Connect Facebook from your Windows browser."}

    print("[+] Opening dedicated Facebook login window (isolated profile)...")
    user_data_dir = str(Config.DATA_DIR / "scraper_fb_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    browser_exe = get_browser_executable()
    launch_kwargs = {
        "user_data_dir": user_data_dir,
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

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=45000)
            print("[+] Dedicated login window opened. Please complete Facebook sign-in...")

            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                cookies = context.cookies(["https://www.facebook.com/", "https://facebook.com/"])
                fb_cookies = [c for c in cookies if c.get("domain", "").lstrip(".") in ("facebook.com", "www.facebook.com")]
                names = {c.get("name") for c in fb_cookies if c.get("value") and (c.get("expires", -1) <= 0 or c["expires"] > time.time())}
                if {"c_user", "xs"}.issubset(names):
                    print("[+] Successful login detected!")
                    Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
                    with open(Config.SESSION_FILE, "w", encoding="utf-8") as output:
                        json.dump({"cookies": fb_cookies, "origins": []}, output, indent=2)
                    context.close()
                    return {"success": True, "message": "Facebook connected successfully in dedicated window."}
                time.sleep(1.5)
            context.close()
            return {"success": False, "message": "Login timed out. Please try again."}
        except Exception as error:
            logger.error("Dedicated login error: %s", error)
            return {"success": False, "message": f"Login window error: {str(error)}"}

def valid_photo_bytes(data):
    if not 500 < len(data) <= 10 * 1024 * 1024:
        return False
    return (
        (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"))
        or (data.startswith(b"\x89PNG\r\n\x1a\n") and data[-12:] == b"\x00\x00\x00\x00IEND\xaeB`\x82")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP" and int.from_bytes(data[4:8], "little") + 8 == len(data))
    )

def is_cached_photo_valid(listing_id):
    try:
        return valid_photo_bytes((Config.DATA_DIR / "images" / f"{listing_id}.jpg").read_bytes())
    except OSError:
        return False

def save_photo_bytes(listing_id, data, content_type):
    if not str(listing_id).isascii() or not str(listing_id).isdigit():
        raise ValueError("Invalid listing ID")
    if not content_type.lower().startswith("image/") or not valid_photo_bytes(data):
        raise ValueError("Incomplete or invalid photo")
    directory = Config.DATA_DIR / "images"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as output:
            temporary = output.name
            output.write(data)
        os.replace(temporary, directory / f"{listing_id}.jpg")
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

def cache_listing_photo(context, listing_id, url):
    if is_cached_photo_valid(listing_id):
        return
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in ("fbcdn.net", "fbsbx.com")):
        raise ValueError("Unsupported photo source")
    for attempt in range(2):
        try:
            response = context.request.get(url, headers={"Referer": "https://www.facebook.com/"}, timeout=10000)
            if not response.ok:
                raise ValueError(f"Photo download failed: HTTP {response.status}")
            save_photo_bytes(listing_id, response.body(), response.headers.get("content-type", ""))
            return
        except Exception:
            if attempt == 1:
                raise

def recover_listing_photos(listings, context=None):
    """Capture only original listing photos; reuse the scan browser when provided."""
    pending = [str(row["listing_id"]) for row in listings
               if str(row["listing_id"]).isascii() and str(row["listing_id"]).isdigit()
               and not is_cached_photo_valid(row["listing_id"])]
    if not pending:
        return {"recovered": [], "unavailable": []}
    if context is None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                current = browser.new_context(storage_state=str(Config.SESSION_FILE), locale="en-AU")
                return recover_listing_photos(listings, context=current)
            finally:
                browser.close()
    recovered, unavailable = [], []
    page = context.new_page()
    try:
        for index, listing_id in enumerate(pending):
            try:
                page.goto(f"https://www.facebook.com/marketplace/item/{listing_id}/", wait_until="domcontentloaded", timeout=20000)
                if "login" in page.url or "checkpoint" in page.url:
                    unavailable.extend(pending[index:])
                    break
                if f"/marketplace/item/{listing_id}" not in page.url:
                    unavailable.append(listing_id)
                    continue
                photo = page.locator('img[alt^="Product photo of "]').first
                photo.wait_for(timeout=6000)
                cache_listing_photo(context, listing_id, photo.get_attribute("src") or "")
                recovered.append(listing_id)
            except Exception as error:
                logger.warning("Photo recovery failed for %s: %s", listing_id, type(error).__name__)
                unavailable.append(listing_id)
    finally:
        page.close()
    return {"recovered": recovered, "unavailable": unavailable}

def scrape_marketplace_listings(f: SearchFilter, max_scrolls: int = 5) -> List[ListingItem]:
    """
    Scrapes Facebook Marketplace listings for the given filter using Playwright.
    """
    global _verified_session
    target_url = build_marketplace_url(f)
    session_signature = _session_signature()
    items: List[ListingItem] = []
    seen_ids = set()
    coords = get_approx_coordinates(f.postcode)
    browser_exe = get_browser_executable()

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars"
        ]
        
        launch_kwargs = {
            "headless": Config.HEADLESS,
            "args": launch_args
        }
        if browser_exe:
            launch_kwargs["executable_path"] = browser_exe

        browser = p.chromium.launch(**launch_kwargs)

        context_kwargs = {
            "viewport": {"width": 1366, "height": 900},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "locale": "en-AU",
            "timezone_id": "Australia/Melbourne",
            "geolocation": coords,
            "permissions": ["geolocation"]
        }

        if Config.SESSION_FILE.exists():
            try:
                context_kwargs["storage_state"] = str(Config.SESSION_FILE)
            except Exception as e:
                logger.warning(f"Could not load session state: {e}")

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        # Stealth evasion touches
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Check if Facebook redirected to a login wall or checkpoint
            current_url = page.url.lower()
            if "login" in current_url or "checkpoint" in current_url or page.query_selector("input#email, input[name='email']"):
                mark_session_rejected()
                logger.warning(f"Facebook blocked request with login wall: {page.url}")
                raise RuntimeError("Facebook session missing or expired. Redirected to login wall (authentication required).")

            _verified_session = session_signature

            # Scroll multiple times to trigger lazy-loaded listings
            for _ in range(max_scrolls):
                page.evaluate("window.scrollBy(0, 1000);")
                page.wait_for_timeout(1500)

            # Extract listing links
            links = page.query_selector_all("a[href*='/marketplace/item/'], a[href*='/item/']")
            
            for link_elem in links:
                try:
                    href = link_elem.get_attribute("href") or ""
                    id_match = re.search(r"/marketplace/item/(\d+)", href)
                    if not id_match:
                        continue
                    
                    listing_id = id_match.group(1)
                    if listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)

                    full_url = href if href.startswith("http") else f"https://www.facebook.com{href}"
                    clean_url = full_url.split("?")[0] if "?" in full_url else full_url

                    text_content = link_elem.inner_text().strip()
                    raw_lines = [line.strip() for line in text_content.split("\n") if line.strip()]

                    # Remove noise badges like 'Just listed', 'Price reduced', etc.
                    badges = {"just listed", "price reduced", "ships to you", "free shipping", "top pick", "deal"}
                    lines = [l for l in raw_lines if l.lower() not in badges]

                    img_elem = link_elem.query_selector("img")
                    if not img_elem:
                        try:
                            parent_handle = link_elem.evaluate_handle("el => el.closest('[data-testid], [class*=\"x9f619\"]')?.querySelector('img')")
                            img_elem = parent_handle.as_element()
                        except Exception:
                            img_elem = None

                    img_url = ""
                    if img_elem:
                        img_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-src") or ""

                    # Preserve the photo while its Facebook URL is still usable.
                    if img_url:
                        try:
                            cache_listing_photo(context, listing_id, img_url)
                        except Exception as error:
                            logger.warning("Photo capture failed for %s; attempting original listing: %s", listing_id, type(error).__name__)

                    title = "Marketplace Item"
                    price_str = "Free" if (f.max_price == 0) else ""
                    location_str = f"Postcode {f.postcode}"
                    price_num = 0.0

                    # Find price line
                    price_idx = -1
                    for idx, l in enumerate(lines):
                        if "free" in l.lower() or "$" in l or re.match(r"^\d+$", l):
                            price_str = l
                            price_idx = idx
                            break

                    digits = re.findall(r"\d+", price_str.replace(",", ""))
                    if digits and "free" not in price_str.lower():
                        try:
                            price_num = float(digits[0])
                        except Exception:
                            pass

                    # Meaningful title and location from remaining lines
                    rem = [l for idx, l in enumerate(lines) if idx != price_idx]
                    if len(rem) >= 2:
                        title = rem[0]
                        location_str = rem[1]
                    elif len(rem) == 1:
                        title = rem[0]

                    # If title was mistakenly identified as a price (e.g. 'AU$180'), swap with location if location has actual item name
                    title_is_price = bool(re.search(r"^(?:au)?\$\s*[\d,]+(?:\.\d+)?$", title.strip(), flags=re.I))
                    if title_is_price:
                        price_str = title.strip()
                        p_digits = re.findall(r"\d+", price_str.replace(",", ""))
                        if p_digits:
                            price_num = float(p_digits[0])
                        if location_str and not re.search(r"\b(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT|\d{4})\b", location_str):
                            title = location_str
                            location_str = f"Postcode {f.postcode}"

                    item = ListingItem(
                        listing_id=listing_id,
                        title=title,
                        price=price_str,
                        price_num=price_num,
                        location=location_str,
                        url=clean_url,
                        image_url=img_url,
                        search_filter_id=f.id,
                        first_seen=time.time()
                    )
                    items.append(item)
                except Exception as ex:
                    logger.debug(f"Error parsing item element: {ex}")
                    continue

            missing_photos = [{"listing_id": item.listing_id} for item in items if not is_cached_photo_valid(item.listing_id)]
            if missing_photos:
                recovery = recover_listing_photos(missing_photos, context=context)
                if recovery["unavailable"]:
                    logger.warning("Scan finished with %d unavailable original photos", len(recovery["unavailable"]))

        finally:
            browser.close()

    return items

if __name__ == "__main__":
    if "--login" in sys.argv:
        print("\n========================================================")
        print("   Starting Interactive Facebook Login Launcher...")
        print("   A browser window will open shortly.")
        print("   Log in with your Facebook account and complete 2FA.")
        print("========================================================\n")
        res = capture_interactive_login(timeout_seconds=600)
        print("Result:", res)
        if res.get("success") and Config.SESSION_FILE.exists():
            print("\n[+] Facebook session captured successfully!")
            try:
                import subprocess
                ssh_key = os.path.expanduser("~/.ssh/OracleKey")
                if os.path.exists(ssh_key):
                    vps_dest = "ubuntu@152.69.184.192:/home/ubuntu/fb-marketplace-scanner/data/session/fb_session.json"
                    print(f"[+] Syncing session file to VPS ({vps_dest})...")
                    subprocess.run(["scp", "-i", ssh_key, str(Config.SESSION_FILE), vps_dest], check=True)
                    print("[+] Restarting background scanner service on VPS...")
                    subprocess.run(["ssh", "-i", ssh_key, "ubuntu@152.69.184.192", "sudo systemctl restart fb-marketplace.service"], check=True)
                    print("\n========================================================")
                    print(" SUCCESS! Facebook session is now ACTIVE on VPS!")
                    print(" 24/7 background marketplace scanning is running.")
                    print("========================================================\n")
            except Exception as sync_err:
                print(f"[!] Session saved locally, but error syncing to VPS: {sync_err}")
    else:
        print("Facebook Marketplace Scraper Module")
