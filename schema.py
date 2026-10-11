import time
from typing import Optional, Dict, Any, List

class SearchFilter:
    def __init__(
        self,
        id: Optional[int] = None,
        name: str = "Free Items 3011",
        query: str = "",
        postcode: str = "3011",
        radius_km: int = 50,
        min_price: Optional[int] = None,
        max_price: Optional[int] = 0, # 0 means free items
        category: str = "",
        enabled: bool = True,
        notify_email: bool = True,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None
    ):
        self.id = id
        self.name = name
        self.query = query.strip()
        self.postcode = postcode.strip()
        self.radius_km = radius_km
        self.min_price = min_price
        self.max_price = max_price
        self.category = category.strip()
        self.enabled = enabled
        self.notify_email = notify_email
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "query": self.query,
            "postcode": self.postcode,
            "radius_km": self.radius_km,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "category": self.category,
            "enabled": bool(self.enabled),
            "notify_email": bool(self.notify_email),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchFilter":
        return cls(
            id=data.get("id"),
            name=data.get("name", "Search Filter"),
            query=data.get("query", ""),
            postcode=data.get("postcode", "3011"),
            radius_km=int(data.get("radius_km", 50)),
            min_price=int(data["min_price"]) if data.get("min_price") is not None and str(data["min_price"]).isdigit() else None,
            max_price=int(data["max_price"]) if data.get("max_price") is not None and str(data["max_price"]).isdigit() else 0,
            category=data.get("category", ""),
            enabled=bool(data.get("enabled", True)),
            notify_email=bool(data.get("notify_email", True)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

class ListingItem:
    def __init__(
        self,
        listing_id: str,
        title: str,
        price: str,
        price_num: Optional[float] = 0.0,
        location: str = "",
        url: str = "",
        image_url: str = "",
        search_filter_id: Optional[int] = None,
        first_seen: Optional[float] = None,
        is_favorite: bool = False,
        is_dismissed: bool = False,
        is_notified: bool = False,
        interest_status: str = "none",
        instant_match: bool = False
    ):
        self.listing_id = str(listing_id)
        self.title = title
        self.price = price
        self.price_num = price_num
        self.location = location
        self.url = url
        self.image_url = image_url
        self.search_filter_id = search_filter_id
        self.first_seen = first_seen or time.time()
        self.is_favorite = is_favorite
        self.is_dismissed = is_dismissed
        self.is_notified = is_notified
        self.interest_status = interest_status
        self.instant_match = instant_match

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "title": self.title,
            "price": self.price,
            "price_num": self.price_num,
            "location": self.location,
            "url": self.url,
            "image_url": self.image_url,
            "search_filter_id": self.search_filter_id,
            "first_seen": self.first_seen,
            "is_favorite": bool(self.is_favorite),
            "is_dismissed": bool(self.is_dismissed),
            "is_notified": bool(self.is_notified),
            "interest_status": self.interest_status,
            "instant_match": bool(self.instant_match)
        }
