import os
import re
import time
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from backend.config import Config
from schema import SearchFilter, ListingItem

logger = logging.getLogger(__name__)

# Map Australian postcode ranges to major Facebook Marketplace city slugs
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
    params = []
    
    if f.query:
        params.append(f"query={quote(f.query)}")
    
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

def capture_interactive_login(timeout_seconds: int = 180) -> Dict[str, Any]:
    """
    Opens a visible browser for the user to log into Facebook.
    Waits for authentication cookies (c_user) to be stored, then saves the storage state.
    """
    result = {"success": False, "message": ""}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/login/")

        start_time = time.time()
        authenticated = False

        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            cookies = context.cookies()
            if any(c.get("name") == "c_user" for c in cookies):
                authenticated = True
                break

        if authenticated:
            # Save storage state
            context.storage_state(path=str(Config.SESSION_FILE))
            result["success"] = True
            result["message"] = "Facebook session captured successfully with active login!"
        else:
            result["success"] = False
            result["message"] = "Login timed out before c_user session was verified."

        browser.close()
    return result

def scrape_marketplace_listings(f: SearchFilter, max_scrolls: int = 5) -> List[ListingItem]:
    """
    Scrapes Facebook Marketplace listings for the given filter using Playwright.
    """
    target_url = build_marketplace_url(f)
    items: List[ListingItem] = []
    seen_ids = set()
    coords = get_approx_coordinates(f.postcode)

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars"
        ]
        
        browser = p.chromium.launch(
            headless=Config.HEADLESS,
            args=launch_args
        )

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
            # Facebook Marketplace item links look like /marketplace/item/1234567890/
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
                    # Strip extraneous query parameters from listing URL
                    clean_url = full_url.split("?")[0] if "?" in full_url else full_url

                    # Get inner text and image
                    text_content = link_elem.inner_text().strip()
                    lines = [line.strip() for line in text_content.split("\n") if line.strip()]

                    # Look for image
                    img_elem = link_elem.query_selector("img")
                    img_url = img_elem.get_attribute("src") if img_elem else ""

                    # Default fallback parsing
                    title = "Marketplace Item"
                    price_str = "Free" if (f.max_price == 0) else ""
                    location_str = f"Postcode {f.postcode}"

                    # Typical FB listing card lines:
                    # Line 0: Price (e.g., "Free" or "$50")
                    # Line 1: Title
                    # Line 2: Location
                    if len(lines) >= 3:
                        price_str = lines[0]
                        title = lines[1]
                        location_str = lines[2]
                    elif len(lines) == 2:
                        if any(char.isdigit() for char in lines[0]) or "free" in lines[0].lower():
                            price_str = lines[0]
                            title = lines[1]
                        else:
                            title = lines[0]
                            price_str = lines[1]
                    elif len(lines) == 1:
                        title = lines[0]

                    # Parse numeric price
                    price_num = 0.0
                    digits = re.findall(r"\d+", price_str.replace(",", ""))
                    if digits and "free" not in price_str.lower():
                        price_num = float(digits[0])

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
