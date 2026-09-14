"""Validation shared by fresh menu and UI-only deployments."""
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
IDS = {"student", "dormitory", "incubator", "faculty"}


def validate(payload, *, require_today=False, now=None):
    now = now or datetime.now(KST)
    if payload.get("schema_version") != 1 or payload.get("campus") != "ERICA":
        raise ValueError("Unsupported menu schema/campus")
    day = date.fromisoformat(payload["date"])
    updated = datetime.fromisoformat(payload["generated_at"])
    if updated.tzinfo is None or updated > now + timedelta(minutes=5):
        raise ValueError("Invalid generation time")
    if day > now.astimezone(KST).date():
        raise ValueError("Future menu date")
    if require_today and day != now.astimezone(KST).date():
        raise ValueError("Menu is not for today in KST")
    restaurants = payload["restaurants"]
    if len(restaurants) != 4 or {r["id"] for r in restaurants} != IDS:
        raise ValueError("Missing or duplicate restaurant IDs")
    total = 0
    for r in restaurants:
        if not isinstance(r["meals"], list):
            raise ValueError("Invalid meals")
        types = []
        for meal in r["meals"]:
            types.append(meal["type"])
            if meal["type"] not in {"조식", "중식", "석식"} or not meal["items"]:
                raise ValueError("Invalid meal type/items")
            for item in meal["items"]:
                if not isinstance(item.get("menu"), str) or not item["menu"].strip():
                    raise ValueError("Empty menu item")
                for key in ("price", "description", "name"):
                    if key in item and not isinstance(item[key], str):
                        raise ValueError("Invalid optional text field")
                if "image" in item and not item["image"].startswith(("https://", "http://")):
                    raise ValueError("Invalid image URL")
                total += 1
        if len(set(types)) != len(types):
            raise ValueError("Duplicate meal type")
        if not r["meals"] and not (r.get("unavailable") or r.get("closed")):
            raise ValueError("Empty restaurant without explicit state")
    if not total:
        raise ValueError("Refusing to deploy an empty menu")
    court = payload["food_court"]
    stores = court["stores"]
    if not isinstance(stores, list) or (not stores and not court.get("unavailable")):
        raise ValueError("Invalid food court")
    if any(not isinstance(s.get("name"), str) or not s["name"].strip() for s in stores):
        raise ValueError("Invalid food court store")
    if len({s["name"] for s in stores}) != len(stores):
        raise ValueError("Duplicate food court stores")
    return payload

