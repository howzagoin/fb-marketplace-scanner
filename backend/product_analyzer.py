import time
import re
from typing import List, Dict, Any, Optional
from backend.db import get_connection, get_interests, add_interest, delete_interest

# Comprehensive Product Normalization Taxonomy
PRODUCT_TAXONOMY = [
    # Furniture & Living
    {
        "slug": "couch-sofa",
        "name": "Couch / Sofa / Lounge",
        "category": "Furniture",
        "pattern": r"\b(couch|sofa|lounge|lounges|futon|chaise|modular|recliner|armchair|loveseat)\b"
    },
    {
        "slug": "shelving-bookshelf",
        "name": "Shelving Unit / Bookshelf",
        "category": "Furniture",
        "pattern": r"\b(shelf|shelves|bookshelf|bookcase|shelving|display shelf|storage cube|kallax)\b"
    },
    {
        "slug": "dining-table",
        "name": "Dining Table & Chairs",
        "category": "Furniture",
        "pattern": r"\b(dining table|kitchen table|dining chair|dining set|bar stool|bar stools)\b"
    },
    {
        "slug": "coffee-table",
        "name": "Coffee Table / Side Table",
        "category": "Furniture",
        "pattern": r"\b(coffee table|side table|nesting table|lamp table)\b"
    },
    {
        "slug": "desk-workstation",
        "name": "Office Desk & Chair",
        "category": "Furniture",
        "pattern": r"\b(desk|office chair|study desk|computer desk|workstation|gaming chair)\b"
    },
    {
        "slug": "cabinet-wardrobe",
        "name": "Wardrobe / Cabinet / Cupboard",
        "category": "Furniture",
        "pattern": r"\b(wardrobe|cabinet|cabinets|cupboard|sideboard|buffet|credenza|pantry|drawers|chest of drawers|tallboy|dresser|dressing table)\b"
    },
    {
        "slug": "bed-mattress",
        "name": "Bed Frame & Mattress",
        "category": "Furniture",
        "pattern": r"\b(bed frame|mattress|queen bed|double bed|single bed|king bed|bunk bed|slats|headboard|bed base)\b"
    },

    # Fitness & Sports
    {
        "slug": "gym-equipment",
        "name": "Gym & Fitness Equipment",
        "category": "Sports & Fitness",
        "pattern": r"\b(treadmill|elliptical|exercise bike|weights|dumbbell|dumbbells|barbell|bench press|gym equipment|squat rack|kettlebell|rower|pilates)\b"
    },
    {
        "slug": "bicycle-scooter",
        "name": "Bicycle & Scooter",
        "category": "Sports & Fitness",
        "pattern": r"\b(bike|bicycle|mountain bike|road bike|kids bike|scooter|skateboard|rollerblades)\b"
    },
    {
        "slug": "pool-table",
        "name": "Pool Table / Billiards",
        "category": "Games & Leisure",
        "pattern": r"\b(pool table|billiards|billiard table|snooker table|foosball|air hockey|ping pong|table tennis)\b"
    },

    # Music & Instruments
    {
        "slug": "piano-keyboard",
        "name": "Piano & Musical Instruments",
        "category": "Music & Hobbies",
        "pattern": r"\b(piano|upright piano|grand piano|keyboard|synthesizer|electric piano|guitar|drums|amplifier|violin)\b"
    },

    # Appliances
    {
        "slug": "washing-machine-dryer",
        "name": "Washing Machine & Dryer",
        "category": "Appliances",
        "pattern": r"\b(washing machine|clothes dryer|dryer|washer|laundry)\b"
    },
    {
        "slug": "fridge-freezer",
        "name": "Refrigerator & Freezer",
        "category": "Appliances",
        "pattern": r"\b(fridge|refrigerator|freezer|bar fridge|wine fridge)\b"
    },
    {
        "slug": "microwave-oven",
        "name": "Microwave & Oven",
        "category": "Appliances",
        "pattern": r"\b(microwave|convection oven|air fryer|toaster oven)\b"
    },
    {
        "slug": "dishwasher",
        "name": "Dishwasher",
        "category": "Appliances",
        "pattern": r"\b(dishwasher)\b"
    },

    # Pets
    {
        "slug": "dog-kennel",
        "name": "Dog Kennel & Crate",
        "category": "Pet Supplies",
        "pattern": r"\b(dog kennel|kennel|dog crate|dog bed|dog house|puppy pen|pet carrier)\b"
    },
    {
        "slug": "cat-scratcher",
        "name": "Cat Tree & Scratcher",
        "category": "Pet Supplies",
        "pattern": r"\b(cat scratcher|cat tree|scratching post|cat tower|cat bed|litter box)\b"
    },
    {
        "slug": "fish-tank",
        "name": "Fish Tank & Aquarium",
        "category": "Pet Supplies",
        "pattern": r"\b(fish tank|aquarium|fishtank|aquarium filter|terrarium)\b"
    },

    # Kids & Baby
    {
        "slug": "baby-cot",
        "name": "Baby Cot & Bassinet",
        "category": "Baby & Nursery",
        "pattern": r"\b(cot|cots|crib|bassinet|cot mattress|change table|high chair)\b"
    },
    {
        "slug": "pram-stroller",
        "name": "Pram & Stroller",
        "category": "Baby & Nursery",
        "pattern": r"\b(pram|stroller|buggy|baby capsule|car seat)\b"
    },
    {
        "slug": "kids-toys",
        "name": "Kids Toys & Play Sets",
        "category": "Toys & Games",
        "pattern": r"\b(toy kitchen|kids toys|box of toys|lego|action figures|dollhouse|puzzles|board games|toy car|nerf|playmat)\b"
    },
    {
        "slug": "costume-dress-up",
        "name": "Costumes & Dress-Ups",
        "category": "Clothing & Costumes",
        "pattern": r"\b(costume|costumes|fancy dress|cosplay|halloween costume|dress up)\b"
    },

    # Outdoor & Garden
    {
        "slug": "trampoline",
        "name": "Trampoline",
        "category": "Outdoor & Garden",
        "pattern": r"\b(trampoline|springfree)\b"
    },
    {
        "slug": "plants-trees",
        "name": "Plants, Pots & Trees",
        "category": "Outdoor & Garden",
        "pattern": r"\b(plant|plants|guava tree|fruit tree|succulent|succulents|garden pots|planter|cuttings|seedlings)\b"
    },
    {
        "slug": "bbq-outdoor-furniture",
        "name": "BBQ & Outdoor Furniture",
        "category": "Outdoor & Garden",
        "pattern": r"\b(bbq|barbecue|outdoor setting|outdoor table|patio chairs|fire pit|sun lounger)\b"
    },
    {
        "slug": "lawnmower-tools",
        "name": "Lawnmowers & Garden Tools",
        "category": "Outdoor & Garden",
        "pattern": r"\b(lawnmower|lawn mower|whipper snipper|hedge trimmer|wheelbarrow|rake|shovel)\b"
    },

    # Electronics & Media
    {
        "slug": "tv-monitor",
        "name": "Television & Monitor",
        "category": "Electronics",
        "pattern": r"\b(tv|television|smart tv|computer monitor|lcd monitor|display)\b"
    },
    {
        "slug": "printers-scanners",
        "name": "Printers & Scanners",
        "category": "Electronics",
        "pattern": r"\b(printer|printers|scanner|photocopier)\b"
    },

    # Kitchenware & Cookware
    {
        "slug": "cookware-kitchen",
        "name": "Cookware, Pots & Pans",
        "category": "Kitchen & Dining",
        "pattern": r"\b(skillet|skillets|cookware|pans|pots|saucepan|frying pan|casserole)\b"
    },
    {
        "slug": "kitchen-dispensers-drinkware",
        "name": "Drinkware & Kitchen Gadgets",
        "category": "Kitchen & Dining",
        "pattern": r"\b(juice dispenser|drink dispenser|dispenser|kettle|blender|toaster|glasses|mugs|dinner set)\b"
    },

    # Verge / Hard Rubbish
    {
        "slug": "hard-rubbish-verge",
        "name": "Verge / Hard Rubbish Collections",
        "category": "Street Finds",
        "pattern": r"\b(hard rubbish|nature strip|on verge|verge collection|kerbside|on the street)\b"
    }
]

def clean_title_noise(title: str) -> str:
    """Removes emojis, punctuation noise, and common listing fillers."""
    t = re.sub(r"[\U00010000-\U0010ffff]", "", title)  # remove high emojis
    t = re.sub(r"[^\w\s-]", " ", t)  # remove punctuation
    # Remove filler words
    t = re.sub(r"\b(free|urgent|pickup|pick up|today|moving out|hard rubbish|on verge|verge|nature strip|must go|good condition|working|tested|australia|au\$\d+)\b", " ", t, flags=re.I)
    t = re.sub(r"\b\d+x\d+cm\b", " ", t, flags=re.I)
    t = re.sub(r"\b\d+-seater\b", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def classify_listing_title(title: str) -> Dict[str, str]:
    """Matches a listing title against the taxonomy or generates a clean fallback product entity."""
    t_lower = f" {title.lower()} "

    for entry in PRODUCT_TAXONOMY:
        if re.search(entry["pattern"], t_lower):
            return {
                "slug": entry["slug"],
                "name": entry["name"],
                "category": entry["category"]
            }

    # Fallback to intelligent core phrase
    cleaned = clean_title_noise(title)
    words = [w for w in cleaned.split() if len(w) > 2]
    if words:
        slug = "-".join(words[:2]).lower()
        name = " ".join(words[:2]).title()
    else:
        slug = "misc-free-items"
        name = "Miscellaneous Free Items"

    return {
        "slug": slug,
        "name": name,
        "category": "General Items"
    }

def get_condensed_products(days: int = 365) -> List[Dict[str, Any]]:
    """
    Analyzes all free items listed over the last year, groups them into unique canonical products,
    and attaches user preference status (Interested / Not Interested / Starred).
    """
    cutoff = time.time() - (days * 86400)
    conn = get_connection()
    c = conn.cursor()

    # Query all free or $0 listings within the time window
    c.execute("""
    SELECT listing_id, title, price, price_num, location, url, image_url, first_seen, interest_status, instant_match, is_favorite, is_dismissed
    FROM listings
    WHERE (price_num = 0 OR LOWER(price) LIKE '%free%')
      AND (first_seen >= ? OR first_seen IS NULL OR first_seen = 0)
    ORDER BY first_seen DESC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()

    # Retrieve current user interests to check preference matches
    interests = get_interests()
    interested_keywords = [i["keyword"].lower() for i in interests if i["type"] == "interested"]
    starred_keywords = [i["keyword"].lower() for i in interests if i["type"] == "interested" and i["instant_alert"] == 1]
    excluded_keywords = [i["keyword"].lower() for i in interests if i["type"] == "excluded"]

    product_map: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        item = dict(r)
        title = item["title"] or ""
        classification = classify_listing_title(title)
        slug = classification["slug"]

        if slug not in product_map:
            # Determine interest status against user's profile
            name_lower = classification["name"].lower()
            slug_terms = [t for t in slug.split("-") if len(t) > 2]

            is_starred = any(kw in name_lower or any(kw == t for t in slug_terms) for kw in starred_keywords)
            is_interested = is_starred or any(kw in name_lower or any(kw == t for t in slug_terms) for kw in interested_keywords)
            is_excluded = any(kw in name_lower or any(kw == t for t in slug_terms) for kw in excluded_keywords)

            int_status = "none"
            if is_excluded:
                int_status = "not_interested"
            elif is_interested:
                int_status = "interested"

            product_map[slug] = {
                "slug": slug,
                "name": classification["name"],
                "category": classification["category"],
                "count": 0,
                "latest_seen": item.get("first_seen") or 0,
                "sample_image": item.get("image_url") or "",
                "interest_status": int_status,
                "instant_alert": is_starred,
                "listings": []
            }

        prod = product_map[slug]
        prod["count"] += 1
        if not prod["sample_image"] and item.get("image_url"):
            prod["sample_image"] = item["image_url"]

        if item.get("first_seen") and item["first_seen"] > prod["latest_seen"]:
            prod["latest_seen"] = item["first_seen"]

        prod["listings"].append({
            "listing_id": item["listing_id"],
            "title": item["title"],
            "price": item["price"],
            "location": item["location"],
            "url": item["url"],
            "image_url": item["image_url"],
            "first_seen": item["first_seen"],
            "interest_status": item.get("interest_status") or "none"
        })

    # Sort products by total occurrence count descending
    condensed_list = list(product_map.values())
    condensed_list.sort(key=lambda x: (x["interest_status"] == "interested" and x["instant_alert"], x["count"]), reverse=True)
    return condensed_list

def set_product_category_interest(product_slug: str, status: str, instant_alert: bool = False) -> Dict[str, Any]:
    """
    Sets the user interest preference for an entire condensed product category.
    - 'interested': adds the key terms to interested profile.
    - 'not_interested': adds to excluded profile and dismisses matching listings.
    - 'none': removes from profile.
    """
    # Find matching taxonomy entry or fallback slug
    target_name = product_slug.replace("-", " ").title()
    for entry in PRODUCT_TAXONOMY:
        if entry["slug"] == product_slug:
            target_name = entry["name"].split("/")[0].strip()
            break

    # Manage user_interests table
    interests = get_interests()
    existing = [i for i in interests if i["keyword"].lower() == target_name.lower()]
    for item in existing:
        delete_interest(item["id"])

    if status == "interested":
        add_interest(target_name, instant_alert=instant_alert, interest_type="interested")
    elif status == "not_interested":
        add_interest(target_name, instant_alert=False, interest_type="excluded")

    # Update listings matching this slug in DB
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT listing_id, title FROM listings")
    all_rows = c.fetchall()

    affected_count = 0
    for r in all_rows:
        cls = classify_listing_title(r["title"])
        if cls["slug"] == product_slug:
            affected_count += 1
            if status == "interested":
                c.execute("""
                UPDATE listings
                SET interest_status = 'interested', is_favorite = 1, is_dismissed = 0, instant_match = ?
                WHERE listing_id = ?
                """, (1 if instant_alert else 0, r["listing_id"]))
            elif status == "not_interested":
                c.execute("""
                UPDATE listings
                SET interest_status = 'not_interested', is_favorite = 0, is_dismissed = 1, instant_match = 0
                WHERE listing_id = ?
                """, (r["listing_id"],))
            else:
                c.execute("""
                UPDATE listings
                SET interest_status = 'none'
                WHERE listing_id = ?
                """, (r["listing_id"],))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "product_slug": product_slug,
        "name": target_name,
        "status": status,
        "instant_alert": instant_alert,
        "affected_listings": affected_count
    }
