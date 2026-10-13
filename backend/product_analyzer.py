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
        "slug": "bedside-tables",
        "name": "Bedside Tables & Nightstands",
        "category": "Furniture",
        "pattern": r"\b(bedside|bedside table|bedside tables|nightstand|nightstands)\b"
    },
    {
        "slug": "bed-mattress",
        "name": "Bed Frame & Mattress",
        "category": "Furniture",
        "pattern": r"\b(bed frame|mattress|queen bed|double bed|single bed|king bed|king single|bunk bed|slats|headboard|bed base|cot and mattress)\b"
    },
    {
        "slug": "furniture-general",
        "name": "General Furniture Items",
        "category": "Furniture",
        "pattern": r"\b(furniture)\b"
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
    {
        "slug": "boats-vehicles",
        "name": "Boats, Trailers & Vehicles",
        "category": "Vehicles & Watercraft",
        "pattern": r"\b(savage lancer|boat|canoe|kayak|trailer|caravan|dinghy|outboard motor)\b"
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
        "pattern": r"\b(cat scratcher|cat tree|scratching post|cat tower|cat bed|litter box|cat scratching)\b"
    },
    {
        "slug": "fish-tank",
        "name": "Fish Tank & Aquarium",
        "category": "Pet Supplies",
        "pattern": r"\b(fish tank|aquarium|fishtank|aquarium filter|terrarium)\b"
    },
    {
        "slug": "pet-bowls-feeders",
        "name": "Pet Bowls, Feeders & Accessories",
        "category": "Pet Supplies",
        "pattern": r"\b(slow feeder|dog bowl|cat bowl|pet bowl|pet dishes|water bowl|leash|pet collar|harness)\b"
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
        "pattern": r"\b(toy|toys|toy set|toy kitchen|kids\s*(?:free\s*)?kitchen|kids toys?|box of toys|lego|action figures?|dollhouse|dolls house|puzzles?|board games?|toy cars?|kids cars?|ride-on|nerf|playmat|pikler|pykler|play set|playpen)\b"
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
        "pattern": r"\b(plant|plants|guava tree|fruit tree|succulent|succulents|agave|cactus|indoor plant|fiddle leaf|monstera|garden pots|planter|cuttings|seedlings)\b"
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
        "pattern": r"\b(skillet|skillets|cookware|pans|pots|saucepan|frying pan|casserole|baking|tupperware)\b"
    },
    {
        "slug": "kitchen-dispensers-drinkware",
        "name": "Drinkware & Juice Dispensers",
        "category": "Kitchen & Dining",
        "pattern": r"\b(juice dispenser|drink dispenser|water dispenser|dispenser|kettle|blender|toaster|glasses|mugs|dinner set)\b"
    },

    # Books, Decor, Collectibles & Materials
    {
        "slug": "books-bibles",
        "name": "Books, Dictionaries & Bibles",
        "category": "Books & Media",
        "pattern": r"\b(book|books|dictionary|dictionaries|bible|bibles|encyclopedia|novel|novels|textbook|textbooks|magazines)\b"
    },
    {
        "slug": "posters-wall-art",
        "name": "Posters, Wall Art & Memorabilia",
        "category": "Home Decor & Art",
        "pattern": r"\b(poster|posters|wall art|framed print|canvas art|memorabilia|laminated pictures|art print)\b"
    },
    {
        "slug": "hair-beauty",
        "name": "Hair Extensions & Accessories",
        "category": "Beauty & Personal Care",
        "pattern": r"\b(braiding hair|hair extensions?|wig|wigs|hair piece|scrunchies?|hair clips?)\b"
    },
    {
        "slug": "bricks-building",
        "name": "Bricks, Pavers & Building Materials",
        "category": "Building & Hardware",
        "pattern": r"\b(brick|bricks|paver|pavers|tiles|timber|pallets|concrete|gravel|sand|plasterboard|scaffold)\b"
    },
    {
        "slug": "collectibles-cards",
        "name": "Trading Cards, Pokemon & Collectibles",
        "category": "Collectibles",
        "pattern": r"\b(pokemon|pokémon|trading cards|collector cards|collectible tins?|figurines?)\b"
    },
    {
        "slug": "craft-fabric-sewing",
        "name": "Fabric, Craft & Sewing Supplies",
        "category": "Crafts & Hobbies",
        "pattern": r"\b(fabric scraps?|fabric|yarn|wool|sewing|craft supplies|ribbon)\b"
    },
    {
        "slug": "party-supplies",
        "name": "Party Supplies & Invitations",
        "category": "Events & Parties",
        "pattern": r"\b(party|invites|invitations|balloons|party supplies|decorations|birthday party)\b"
    },
    {
        "slug": "air-fresheners",
        "name": "Air Fresheners & Household Cleaning",
        "category": "Household Supplies",
        "pattern": r"\b(airfreshener|airfresheners|air freshener|air fresheners|cleaning products|detergent|diffuser)\b"
    },
    {
        "slug": "health-supplements",
        "name": "Health Supplements & Wellness",
        "category": "Health & Wellness",
        "pattern": r"\b(qenda|supplements?|vitamins?|protein powder|fibre)\b"
    },
    {
        "slug": "garage-moving-sales",
        "name": "Garage & Moving Sales",
        "category": "Garage Sales",
        "pattern": r"\b(garage sale|moving sale|estate sale|yard sale)\b"
    },

    # Verge / Hard Rubbish
    {
        "slug": "hard-rubbish-verge",
        "name": "Verge / Hard Rubbish Collections",
        "category": "Street Finds",
        "pattern": r"\b(hard rubbish|nature strip|on verge|verge collection|kerbside|on the street)\b"
    }
]

DESCRIPTOR_ADJECTIVES = {
    "vintage", "retro", "antique", "modern", "wooden", "timber", "metal", "plastic",
    "silicone", "steel", "glass", "leather", "fabric", "ceramic", "cute", "small",
    "large", "big", "huge", "heavy", "mini", "assorted", "brand", "new", "used",
    "old", "rustic", "solid", "beautiful", "luxury", "designer", "heavy", "duty",
    "clean", "nice", "little", "white", "black", "red", "blue", "green", "grey", "gray",
    "free", "urgent", "pickup", "today", "moving", "must", "good", "condition", "richmond"
}

OFFER_PATTERNS = [
    r"\b(?:looking|taking|open|send|make|throw|give|want|wanting|accepting)\s+(?:for\s+|me\s+|us\s+|to\s+)?(?:all\s+)?(?:an?\s+)?offers?\b",
    r"\boffers?\s+(?:considered|welcome|wanted|invited|over|around|accepted|please)\b",
    r"\bbest\s+offers?\b",
    r"\bmake\s+(?:me\s+)?(?:an?\s+)?offers?\b",
    r"\bopen\s+to\s+(?:all\s+)?(?:prices?|offers?)\b",
    r"\bnot\s+(?:actually\s+)?free\b",
    r"\bisn'?t\s+(?:actually\s+)?free\b",
    r"\bnot\s+\$0\b",
    r"\b(?:pm|dm|inbox|msg|message)\s+(?:me\s+)?(?:for\s+)?prices?\b",
    r"\b(?:see\s+listing|read\s+desc(?:ription)?|check\s+desc(?:ription)?)\s+for\s+prices?\b",
    r"\bprice\s+is\s+not\s+free\b",
    r"\bprices?\s+in\s+desc(?:ription)?\b",
    r"\bprices?\s+listed\b",
    r"\bo\.?n\.?o\b",
    r"\bor\s+nearest\s+offer\b",
    r"\bswaps?\s+or\s+offers?\b",
    r"\btrade\s+or\s+offer\b"
]

def is_seeking_offers(title: str) -> bool:
    """Detects if a listing that claims to be free is actually asking for offers/prices."""
    if not title:
        return False
    t_lower = title.lower()
    return any(re.search(pat, t_lower, flags=re.IGNORECASE) for pat in OFFER_PATTERNS)

def is_priced_item(title: str = "", price: str = "", price_num: float = 0.0) -> bool:
    """
    Detects if an item that appeared in a free search actually has a price attached.
    Checks:
    - price_num > 0
    - price contains currency symbols or digits and isn't 'Free'
    - title contains currency symbols (e.g., 'AU$180', '$50', '25$')
    """
    if price_num and price_num > 0:
        return True

    if price:
        p_clean = price.strip().lower()
        if p_clean != "free" and (re.search(r"\$\s*\d+", price) or re.search(r"\bau\$\s*\d+", price, flags=re.I)):
            return True

    if title:
        # Detect currency amounts in title like 'AU$180', '$50', '$ 20'
        if re.search(r"(?:au)?\$\s*[\d,]+(?:\.\d+)?", title, flags=re.I):
            return True

    return False

def clean_title_noise(title: str) -> str:
    """Removes emojis, punctuation noise, prices, and common listing fillers."""
    t = re.sub(r"[\U00010000-\U0010ffff]", " ", title)  # remove high emojis
    t = re.sub(r"\b(?:AU)?\$\s*[\d,]+(?:\.\d+)?\b", " ", t, flags=re.I)  # remove prices like AU$1,500
    t = re.sub(r"\b\d+x\d+\s*(?:cm|mm|m|in)?\b", " ", t, flags=re.I)  # remove dimensions
    t = re.sub(r"\b\d+-seater\b", " ", t, flags=re.I)
    t = re.sub(r"[^\w\s-]", " ", t)  # remove punctuation
    # Remove filler words
    t = re.sub(r"\b(free|urgent|pickup|pick up|today|moving out|hard rubbish|on verge|verge|nature strip|must go|good condition|working|tested|australia|open to all prices|all prices|make an offer|ono)\b", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_core_product_phrase(title: str) -> str:
    """
    Intelligently extracts the head-noun product entity from a listing title
    instead of blindly taking the first word.
    """
    cleaned = clean_title_noise(title)
    if not cleaned:
        return "Miscellaneous Items"

    # Split on clause delimiters (hyphens, slashes)
    clauses = re.split(r"[-|/()]", cleaned)
    first_clause = clauses[0].strip() if clauses else cleaned

    # Split on prepositions ('for', 'with', 'in', 'at') to isolate core item
    prep_split = re.split(r"\b(?:for|with|in|at|from)\b", first_clause, flags=re.I)
    core = prep_split[0].strip() if prep_split else first_clause

    words = re.findall(r"[a-zA-Z]{3,}", core)
    filtered = [w for w in words if w.lower() not in DESCRIPTOR_ADJECTIVES]
    if not filtered:
        filtered = words

    if not filtered:
        return "Miscellaneous Items"

    # In English noun phrases, the head noun is at the end: take the last 2 nouns or 1 noun
    if len(filtered) >= 2:
        return f"{filtered[-2].capitalize()} {filtered[-1].capitalize()}"
    return filtered[-1].capitalize()

def classify_listing_title(title: str, price: str = "", price_num: float = 0.0) -> Dict[str, str]:
    """Matches a listing title against the taxonomy or generates a clean fallback product entity."""
    if is_priced_item(title=title, price=price, price_num=price_num) or is_seeking_offers(title):
        return {
            "slug": "not-free-priced",
            "name": "Priced / Offers Wanted (Not Free)",
            "category": "Offers & Wanted"
        }

    t_lower = f" {title.lower()} "

    for entry in PRODUCT_TAXONOMY:
        if re.search(entry["pattern"], t_lower):
            return {
                "slug": entry["slug"],
                "name": entry["name"],
                "category": entry["category"]
            }

    # Fallback to intelligent head-noun extraction
    head_name = extract_core_product_phrase(title)
    slug = re.sub(r"[^\w]+", "-", head_name.lower()).strip("-")
    if not slug:
        slug = "misc-free-items"
        head_name = "Miscellaneous Items"

    return {
        "slug": slug,
        "name": head_name,
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
        classification = classify_listing_title(title, price=item.get("price") or "", price_num=item.get("price_num") or 0.0)
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
            target_name = entry["name"]
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

def reconcile_all_excluded_interests() -> Dict[str, Any]:
    """
    Analyzes the products the user marked not interested in,
    intelligently maps them to canonical product categories,
    cleans up fragmented single-word excluded entries, and populates
    the clean merged Excluded profile.
    """
    USER_DISMISSED_TITLES = [
        "fish tank", "treadmill", "dog kennel", "piano", "display shelf",
        "casa domani juice dispenser", "pokemon tins", "dressing table",
        "toy kitchen", "rainbow unicorn braiding hair", "washing machine",
        "free gym equipment", "free shelf", "upright+piano+", "cot and mattress",
        "assorted puzzles", "dinosaurs invites", "box of kids toys", "free trampoline",
        "free fabric scraps", "assorted railway train memorabilia - laminated pictures",
        "stranger things 3 poster 60x90cm free", "free guava tree", "free working printers",
        "circulon skillets", "cabinets free", "clothing shelf", "kids free kitchen",
        "free books for kids", "free - king single bed",
        "silicone slow feeder for dogs for free", "free - dryer", "1999 savage lancer",
        "garage sale on today open", "free airfresheners", "free - qenda ultimate fibre",
        "free vintage desk", "free simpson sirocco 500 dryer", "free london piano",
        "agave", "free outside metal cat tower", "dolls house", "dictionary",
        "holy bible (nkjv)", "bedside tables", "free kids car", "pykler",
        "vintage fridge", "dishwasher", "free miele washing machine (pickup richmond)",
        "free bricks"
    ]

    excluded_slugs = set()
    excluded_names = {}
    for title in USER_DISMISSED_TITLES:
        classification = classify_listing_title(title)
        slug = classification["slug"]
        name = classification["name"]
        excluded_slugs.add(slug)
        excluded_names[slug] = name

    conn = get_connection()
    c = conn.cursor()

    # Clear old fragmented excluded items
    c.execute("DELETE FROM user_interests WHERE type = 'excluded'")

    # Insert clean canonical merged excluded products
    inserted_categories = []
    now = time.time()
    for slug, prod_name in sorted(excluded_names.items(), key=lambda x: x[1]):
        c.execute("""
        INSERT INTO user_interests (keyword, instant_alert, type, created_at)
        VALUES (?, 0, 'excluded', ?)
        """, (prod_name, now))
        inserted_categories.append(prod_name)

    # Re-evaluate all listings in database against the excluded and interested profiles
    c.execute("SELECT keyword, instant_alert, type FROM user_interests WHERE type = 'interested'")
    interested_items = [dict(r) for r in c.fetchall()]

    c.execute("SELECT listing_id, title, price, price_num FROM listings")
    all_listings = c.fetchall()
    affected_excluded = 0
    affected_interested = 0

    for l in all_listings:
        cls = classify_listing_title(l["title"] or "", price=l["price"] or "", price_num=l["price_num"] or 0.0)
        c_name = cls["name"]
        c_slug = cls["slug"]
        title_lower = (l["title"] or "").lower()

        is_ex = (c_slug in excluded_slugs or c_name in excluded_names.values() or c_slug == "not-free-priced")

        is_in = False
        is_star = False
        for ii in interested_items:
            ik = ii["keyword"].lower()
            if ik in title_lower or ik in c_name.lower() or ik == c_slug:
                is_in = True
                if ii.get("instant_alert"):
                    is_star = True
                break

        if is_ex:
            c.execute("""
            UPDATE listings
            SET interest_status = 'not_interested', is_favorite = 0, is_dismissed = 1, instant_match = 0
            WHERE listing_id = ?
            """, (l["listing_id"],))
            affected_excluded += 1
        elif is_in:
            c.execute("""
            UPDATE listings
            SET interest_status = 'interested', is_favorite = 1, is_dismissed = 0, instant_match = ?
            WHERE listing_id = ?
            """, (1 if is_star else 0, l["listing_id"]))
            affected_interested += 1
        else:
            c.execute("""
            UPDATE listings
            SET interest_status = 'none', is_dismissed = 0
            WHERE listing_id = ?
            """, (l["listing_id"],))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "total_source_listings": len(USER_DISMISSED_TITLES),
        "excluded_categories_count": len(inserted_categories),
        "excluded_categories": inserted_categories,
        "affected_listings": affected_excluded
    }

