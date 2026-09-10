#!/usr/bin/env python3
"""Fetch ERICA cafeteria data and write one static JSON file.

Holiday classification runs at build time; visitors only read the static JSON.
"""

from __future__ import annotations

import html as html_lib
import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "menu.json"
KST = timezone(timedelta(hours=9))
HOLIDAY_CALENDAR = json.loads(
    (ROOT / "scripts" / "kr_public_holidays.json").read_text(encoding="utf-8")
)

CAFETERIAS = (
    {
        "id": "student",
        "name": "학생식당",
        "location": "복지관 2층",
        "hours": "조식 08:30–09:40 · 중식 11:30–13:30",
        "url": "https://life.hanyang.ac.kr/theme/pages/home.php",
    },
    {
        "id": "dormitory",
        "name": "창의인재원식당",
        "location": "창의관 1층",
        "hours": "조식 07:40–09:00 · 중식 11:30–13:20 · 석식 17:10–18:40",
        "url": "https://life.hanyang.ac.kr/theme/pages/home.php",
    },
    {
        "id": "incubator",
        "name": "창업보육센터",
        "location": "창업보육센터 지하 1층",
        "hours": "중식 11:30–13:30 · 석식 17:00–18:30",
        "url": "https://life.hanyang.ac.kr/theme/pages/home.php",
    },
    {
        "id": "faculty",
        "name": "교직원식당",
        "location": "복지관 3층",
        "hours": "중식 11:30–13:30",
        "url": "https://life.hanyang.ac.kr/theme/pages/home.php",
    },
)

HY_SQUARE_URL = "https://life.hanyang.ac.kr/theme/pages/home.php"
FOOD_COURT_URL = HY_SQUARE_URL
FOOD_COURT_IDS = {12, 13, 14, 15, 16, 17, 18}
SOURCE_NAMES = {
    "student": "학생식당",
    "dormitory": "창의인재원식당",
    "incubator": "창업보육센터식당",
    "faculty": "교직원식당",
}
MEAL_TYPES = {"breakfast": "조식", "lunch": "중식", "dinner": "석식"}
# Campus operating policy: the dormitory and food court have separate schedules.
WEEKDAY_ONLY_RESTAURANTS = {"student", "incubator", "faculty"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)
OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(CookieJar())
)


def fetch(url: str, attempts: int = 3) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with OPENER.open(request, timeout=20) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read()
                print(
                    "HTTP 응답: "
                    f"attempt={attempt + 1}/{attempts} "
                    f"status={response.status} "
                    f"final_url={response.geturl()} "
                    f"bytes={len(body)} charset={charset}"
                )
                return body.decode(charset, errors="replace")
        except Exception as exc:  # urllib raises several transport error types.
            last_error = exc
            print(
                "HTTP 실패: "
                f"attempt={attempt + 1}/{attempts} url={url} "
                f"status={getattr(exc, 'code', 'n/a')} "
                f"final_url={getattr(exc, 'url', url)} "
                f"exception={type(exc).__name__}: {exc}"
            )
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f"HY-SQUARE 페이지를 {attempts}회 시도했지만 불러오지 못했습니다: {url}"
    ) from last_error


def clean_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html_lib.unescape(fragment)
    return re.sub(r"\s+", " ", fragment).strip()


def is_closed_day(menu_date: str, restaurant: dict) -> bool:
    """Never replace an actual menu or infer closure from a meal filter."""
    if restaurant["id"] not in WEEKDAY_ONLY_RESTAURANTS or restaurant["meals"]:
        return False
    day = date.fromisoformat(menu_date)
    if day.year not in HOLIDAY_CALENDAR["years"]:
        raise RuntimeError(f"{day.year}년 대한민국 공휴일 자료를 갱신해야 합니다.")
    return day.weekday() >= 5 or menu_date in HOLIDAY_CALENDAR["dates"]


def restaurant_record(config: dict[str, str], meals: list[dict]) -> dict:
    return {
        "id": config["id"],
        "name": config["name"],
        "location": config["location"],
        "hours": config["hours"],
        "source": config["url"],
        "meals": meals,
    }


def extract_json_array(source: str, variable: str) -> list[dict]:
    match = re.search(
        rf"\bconst\s+{re.escape(variable)}\s*=\s*(\[.*?\])\s*;",
        source,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"HY-SQUARE 페이지에서 {variable} 데이터를 찾지 못했습니다.")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"HY-SQUARE의 {variable} 데이터가 올바르지 않습니다.") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError(f"HY-SQUARE의 {variable} 데이터 형식이 올바르지 않습니다.")
    return value


def parse_embedded_menus(source: str, config: dict[str, str]) -> tuple[str, dict] | None:
    """Parse the consolidated menu JSON used by the current welfare portal."""
    if not re.search(r"\bconst\s+dbMenus\s*=", source):
        return None
    all_items = extract_json_array(source, "dbMenus")

    dates = {
        item.get("target_date")
        for item in all_items
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("target_date", "")))
    }
    if len(dates) != 1:
        raise RuntimeError(
            f"{config['name']} 페이지의 메뉴 날짜를 확정하지 못했습니다: {sorted(dates)}"
        )
    menu_date = dates.pop()

    grouped: dict[str, list[dict]] = {}
    source_name = SOURCE_NAMES[config["id"]]
    for raw_item in all_items:
        if raw_item.get("facility_name") != source_name:
            continue
        meal_type = MEAL_TYPES.get(raw_item.get("meal_type"))
        menu_name = clean_text(str(raw_item.get("name") or ""))
        if not meal_type or not menu_name:
            continue

        description = clean_text(str(raw_item.get("description") or ""))
        menu = f"{menu_name} · {description}" if description else menu_name
        raw_price = raw_item.get("price")
        if isinstance(raw_price, (int, float)):
            price = f"{raw_price:,.0f}원"
        else:
            price = clean_text(str(raw_price or ""))
        item = {
            "name": menu_name,
            "description": description,
            "menu": menu,
            "price": price,
        }

        raw_image = str(raw_item.get("image_url") or "").strip()
        if raw_image:
            image_url = urljoin(config["url"], raw_image)
            if image_url.startswith(("https://", "http://")):
                item["image"] = image_url
        grouped.setdefault(meal_type, []).append(item)

    meals = [
        {"type": meal_type, "items": grouped[meal_type]}
        for meal_type in MEAL_TYPES.values()
        if meal_type in grouped
    ]
    restaurant = restaurant_record(config, meals)
    restaurant["closed"] = is_closed_day(menu_date, restaurant)
    if not meals and not restaurant["closed"]:
        restaurant["unavailable"] = True
    return menu_date, restaurant


def parse_cafeteria(source: str, config: dict[str, str]) -> tuple[str, dict]:
    embedded = parse_embedded_menus(source, config)
    if embedded is not None:
        return embedded

    date_match = re.search(
        r'class="hyu-pagination-inner"[^>]*>.*?<h1>\s*(\d{4}/\d{2}/\d{2})\s*</h1>',
        source,
        flags=re.DOTALL,
    )
    if not date_match:
        raise RuntimeError(f"{config['name']} 페이지에서 메뉴 날짜를 찾지 못했습니다.")

    daily_match = re.search(
        r'<div id="[^"]*_dailyView"[^>]*>(.*?)'
        r'<div id="[^"]*_weeklyView"',
        source,
        flags=re.DOTALL,
    )
    if not daily_match:
        raise RuntimeError(f"{config['name']} 페이지의 오늘 메뉴 영역이 변경되었습니다.")

    chunks = re.split(
        r'<h3\b[^>]*class="[^"]*\bhyu-element\b[^"]*"[^>]*>(.*?)</h3>',
        daily_match.group(1),
        flags=re.DOTALL | re.IGNORECASE,
    )
    meals: list[dict] = []
    item_pattern = re.compile(
        r'<div class="menu-img"[^>]*style="[^"]*?url\([\'\"]?([^\'\")]+)'
        r'[\'\"]?\)[^"]*"[^>]*>.*?</div>\s*'
        r'<div class="menu-detail">\s*<p[^>]*>(.*?)</p>\s*</div>\s*'
        r'<div class="menu-price">\s*<h3[^>]*>(.*?)</h3>',
        flags=re.DOTALL | re.IGNORECASE,
    )

    for index in range(1, len(chunks), 2):
        meal_type = clean_text(chunks[index])
        section = chunks[index + 1]
        items = []
        for raw_image, raw_menu, raw_price in item_pattern.findall(section):
            menu = clean_text(raw_menu)
            if not menu:
                continue

            item = {"menu": menu, "price": clean_text(raw_price)}
            image_url = urljoin(config["url"], html_lib.unescape(raw_image).strip())
            image_key = image_url.lower()
            is_placeholder = any(
                marker in image_key for marker in ("no-img", "no_image", "noimage")
            )
            if image_url.startswith(("https://", "http://")) and not is_placeholder:
                item["image"] = image_url
            items.append(item)
        if items:
            meals.append({"type": meal_type, "items": items})

    restaurant = restaurant_record(config, meals)
    menu_date = date_match.group(1).replace("/", "-")
    restaurant["closed"] = is_closed_day(menu_date, restaurant)
    return menu_date, restaurant


def parse_food_court(source: str) -> list[dict]:
    """Read the student-welfare food-court tenants from dbFacilitiesList."""
    facilities = extract_json_array(source, "dbFacilitiesList")
    stores = []
    for facility in facilities:
        if facility.get("id") not in FOOD_COURT_IDS:
            continue
        name = clean_text(str(facility.get("name") or ""))
        location = clean_text(str(facility.get("location") or ""))
        category = clean_text(str(facility.get("category") or ""))
        if name:
            stores.append({"name": name, "location": location, "category": category})

    if {store["name"] for store in stores} and len(stores) == len(FOOD_COURT_IDS):
        return stores
    raise RuntimeError(
        f"푸드코트 매장 {len(FOOD_COURT_IDS)}곳 중 {len(stores)}곳만 찾았습니다."
    )


def unavailable_restaurant(config: dict[str, str]) -> dict:
    restaurant = restaurant_record(config, [])
    restaurant["closed"] = False
    restaurant["unavailable"] = True
    return restaurant


def main() -> None:
    now = datetime.now(KST)
    # The new portal embeds every cafeteria and food-court tenant in one response.
    # A total request/parsing failure must happen before OUTPUT is touched so Pages
    # keeps serving the last successful artifact.
    source = fetch(HY_SQUARE_URL)
    all_menus = extract_json_array(source, "dbMenus")
    print(f"파싱 시작: dbMenus={len(all_menus)}개")

    dates = {
        item.get("target_date")
        for item in all_menus
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("target_date", "")))
    }
    if len(dates) != 1:
        raise RuntimeError(f"메뉴 날짜를 하나로 확정하지 못했습니다: {sorted(dates)}")
    menu_date = dates.pop()
    if menu_date != now.date().isoformat():
        raise RuntimeError(
            f"HY-SQUARE 메뉴가 오늘 날짜가 아닙니다: source={menu_date}, today={now.date()}"
        )

    restaurants = []
    for config in CAFETERIAS:
        try:
            parsed_date, restaurant = parse_cafeteria(source, config)
            if parsed_date != menu_date:
                raise RuntimeError(f"날짜 불일치: {parsed_date} != {menu_date}")
        except Exception as exc:
            print(f"식당 파싱 실패: id={config['id']} exception={type(exc).__name__}: {exc}")
            restaurant = unavailable_restaurant(config)
        restaurants.append(restaurant)
        item_count = sum(len(meal["items"]) for meal in restaurant["meals"])
        print(
            f"식당 파싱 결과: id={config['id']} meals={len(restaurant['meals'])} "
            f"items={item_count} unavailable={restaurant.get('unavailable', False)}"
        )

    available_restaurants = [restaurant for restaurant in restaurants if restaurant["meals"]]
    if not available_restaurants:
        raise RuntimeError("네 식당 메뉴를 하나도 수집하지 못해 기존 배포본을 유지합니다.")

    try:
        food_court_stores = parse_food_court(source)
        food_court_unavailable = False
    except Exception as exc:
        print(f"푸드코트 파싱 실패: exception={type(exc).__name__}: {exc}")
        food_court_stores = []
        food_court_unavailable = True
    print(
        f"푸드코트 파싱 결과: stores={len(food_court_stores)} "
        f"unavailable={food_court_unavailable}"
    )

    payload = {
        "schema_version": 1,
        "campus": "ERICA",
        "date": menu_date,
        "generated_at": now.isoformat(timespec="seconds"),
        "restaurants": restaurants,
        "food_court": {
            "name": "푸드코트",
            "note": "학생복지관 2층 입점 매장",
            "source": FOOD_COURT_URL,
            "stores": food_court_stores,
            "unavailable": food_court_unavailable,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"{payload['date']} 메뉴: 식당 {len(restaurants)}곳, "
        f"푸드코트 {len(payload['food_court']['stores'])}곳"
    )


if __name__ == "__main__":
    main()
