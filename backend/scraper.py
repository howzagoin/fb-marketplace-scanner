import os
import re
import sys
import time
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from playwright.sync_api import sync_playwright

from backend.config import Config
from schema import SearchFilter, ListingItem

logger = logging.getLogger(__name__)

def get_browser_executable() -> Optional[str]:
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
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
    if not Config.SESSION_FILE.exists():
        return False
    try:
        with open(Config.SESSION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            cookies = data.get("cookies", [])
            has_c_user = any(c.get("name") == "c_user" for c in cookies)
            return has_c_user
    except Exception:
        return False

def get_session_info() -> Dict[str, Any]:
    valid = is_session_valid()
    modified_time = None
    if Config.SESSION_FILE.exists():
        modified_time = Config.SESSION_FILE.stat().st_mtime
    return {
        "valid": valid,
        "exists": Config.SESSION_FILE.exists(),
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
            except Exception:
                pass
        
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
    formatted_cookies = []
    has_c_user = False
    for c in cookie_list:
        name = c.get("name")
        val = c.get("value")
        if not name or val is None:
            continue
        if name == "c_user":
            has_c_user = True
        formatted_cookies.append({
            "name": str(name),
            "value": str(val),
            "domain": c.get("domain", ".facebook.com"),
            "path": c.get("path", "/"),
            "expires": float(c.get("expires", time.time() + 31536000)),
            "httpOnly": bool(c.get("httpOnly", name in ("xs", "sb", "fr"))),
            "secure": bool(c.get("secure", True)),
            "sameSite": c.get("sameSite", "None")
        })

    if not has_c_user:
        return {"success": False, "error": "Missing essential 'c_user' cookie. Please include c_user and xs."}

    storage_state = {
        "cookies": formatted_cookies,
        "origins": []
    }

    Config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    with open(Config.SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)

    return {"success": True, "message": f"Successfully imported {len(formatted_cookies)} cookies. Facebook session is active!"}

def capture_interactive_login(timeout_seconds: int = 300) -> Dict[str, Any]:
    """
    Opens a visible browser using Brave or Chrome with a persistent profile for user sign-in.
    Waits for authentication cookies (c_user) to be stored, then saves the storage state.
    """
    result = {"success": False, "message": ""}
    browser_exe = get_browser_executable()
    user_data_dir = str(Config.DATA_DIR / "browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)

    with sync_playwright() as p:
        launch_kwargs = {
            "user_data_dir": user_data_dir,
            "headless": False,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        }
        if browser_exe:
            launch_kwargs["executable_path"] = browser_exe

        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            page = context.pages[0] if context.pages else context.new_page()

            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page.goto("https://www.facebook.com/marketplace/", timeout=45000)

            start_time = time.time()
            authenticated = False

            while time.time() - start_time < timeout_seconds:
                time.sleep(2)
                try:
                    cookies = context.cookies()
                    if any(c.get("name") == "c_user" for c in cookies):
                        authenticated = True
                        break
                except Exception:
                    # User may have closed the page or browser
                    break

            if authenticated:
                context.storage_state(path=str(Config.SESSION_FILE))
                result["success"] = True
                result["message"] = "Facebook session verified and saved successfully!"
            else:
                result["success"] = False
                result["message"] = "Login timed out or window was closed before Facebook session was verified."

            try:
                context.close()
            except Exception:
                pass
        except Exception as e:
            result["success"] = False
            result["message"] = f"Interactive login error: {str(e)}"

    return result

def scrape_marketplace_listings(f: SearchFilter, max_scrolls: int = 5) -> List[ListingItem]:
    """
    Scrapes Facebook Marketplace listings for the given filter using Playwright.
    """
    target_url = build_marketplace_url(f)
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

            # Scroll multiple times to trigger lazy-loaded listings
            for _ in range(max_scrolls):
                page.evaluate("window.scrollBy(0, 1000);")
                page.wait_for_timeout(1500)

            # Extract listing links
            links = page.query_selector_all("a[href*='/marketplace/item/']")
            
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
                    img_url = img_elem.get_attribute("src") if img_elem else ""

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

        finally:
            browser.close()

    return items

if __name__ == "__main__":
    if "--login" in sys.argv:
        print("Starting interactive Facebook login with real browser...")
        res = capture_interactive_login(timeout_seconds=300)
        print("Result:", res)
    else:
        print("Facebook Marketplace Scraper Module")
