#!/usr/bin/env python3
"""Fetch ERICA cafeteria data and write one static JSON file.

Holiday classification runs at build time; visitors only read the static JSON.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urljoin

try:
    from .artifact import validate
except ImportError:
    from artifact import validate


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


class SourceUnavailable(RuntimeError):
    """Expected upstream failure: preserve the last successful artifact."""


class SourceSchemaError(SourceUnavailable):
    """The upstream response is not safe to publish."""


class FetchError(SourceUnavailable):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def fetch_url(url: str, path: str, attempts: int = 2) -> str:
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
                    f"path={path} "
                    f"attempt={attempt + 1}/{attempts} "
                    f"status={response.status} "
                    f"final_url={response.geturl()} "
                    f"bytes={len(body)} charset={charset} "
                    f"content_type={response.headers.get('Content-Type', '')} initial_url={url}"
                )
                return body.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            error_body = exc.read()
            print(
                "HTTP 실패: "
                f"path={path} "
                f"attempt={attempt + 1}/{attempts} url={url} "
                f"status={exc.code} final_url={exc.geturl()} "
                f"bytes={len(error_body)} content_type={exc.headers.get('Content-Type', '')} "
                f"exception=HTTPError: {exc}"
            )
            if path == "fixed-proxy" and exc.code in (400, 401, 403, 404, 500):
                raise RuntimeError(f"중계 설정/내부 오류: HTTP {exc.code}") from exc
            if exc.code in (400, 401, 403, 404):
                break
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            print(
                "HTTP 실패: "
                f"path={path} "
                f"attempt={attempt + 1}/{attempts} url={url} "
                f"status={getattr(exc, 'code', 'n/a')} "
                f"final_url={getattr(exc, 'url', url)} "
                f"exception={type(exc).__name__}: {exc}"
            )
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise FetchError(
        f"{path} 경로를 {attempts}회 시도했지만 불러오지 못했습니다: {url}",
        getattr(last_error, "code", None),
    ) from last_error


def fetch(url: str) -> str:
    """Configured relay is the only scheduled source; direct is diagnostic/local."""
    proxy_url = os.environ.get("MENU_PROXY_URL", "").strip()
    if not proxy_url:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise ValueError("Actions requires a verified MENU_PROXY_URL")
        return fetch_url(url, "direct", attempts=1)
    if not proxy_url.startswith("https://"):
        raise ValueError("MENU_PROXY_URL must use HTTPS")
    proxy_body = fetch_url(proxy_url, "fixed-proxy", attempts=2)
    try:
        payload = json.loads(proxy_body)
        if not payload.get("ok") or payload.get("source_url") != HY_SQUARE_URL:
            raise SourceUnavailable("중계기가 원본 조회 실패를 보고했습니다.")
        menus = payload["menus"]
        facilities = payload["facilities"]
        if not isinstance(menus, list) or not isinstance(facilities, list):
            raise TypeError("menus/facilities must be arrays")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SourceSchemaError("고정 중계 응답의 메뉴 JSON 형식이 올바르지 않습니다.") from exc
    print(
        f"중계 JSON 검증: menus={len(menus)} facilities={len(facilities)} "
        f"source_url={payload.get('source_url', 'n/a')}"
    )
    print(f"원본 HTTP 진단: {json.dumps(payload.get('diagnostics'), ensure_ascii=False)}")
    return (
        f"const dbMenus = {json.dumps(menus, ensure_ascii=False)};\n"
        f"const dbFacilitiesList = {json.dumps(facilities, ensure_ascii=False)};\n"
        f"const sourceCheckedAt = {json.dumps(payload.get('checked_at'))};"
    )


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
        raise SourceSchemaError(f"HY-SQUARE 페이지에서 {variable} 데이터를 찾지 못했습니다.")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SourceSchemaError(f"HY-SQUARE의 {variable} 데이터가 올바르지 않습니다.") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SourceSchemaError(f"HY-SQUARE의 {variable} 데이터 형식이 올바르지 않습니다.")
    return value


FACILITY_ID = {"student": 1, "faculty": 2, "incubator": 3, "dormitory": 4}


def parse_items(all_items: list[dict], config: dict, menu_date: str) -> dict:
    grouped = {}
    for raw in all_items:
        selected = (raw.get("facility_id") == FACILITY_ID[config["id"]]
                    if "facility_id" in raw else raw.get("facility_name") == SOURCE_NAMES[config["id"]])
        if not selected:
            continue
        raw_date = raw.get("target_date")
        try:
            date.fromisoformat(raw_date)
        except (ValueError, TypeError):
            raise SourceSchemaError(f"{config['id']}: 메뉴 날짜 누락/형식 오류")
        if raw_date != menu_date:
            continue
        meal_type = MEAL_TYPES.get(raw.get("meal_type"))
        name = raw.get("name")
        if not meal_type or not isinstance(name, str) or not clean_text(name):
            raise SourceSchemaError(f"{config['id']}: 메뉴 이름/끼니 형식 오류")
        description = raw.get("description") or ""
        price = raw.get("price")
        image = raw.get("image_url") or ""
        if not isinstance(description, str) or not isinstance(image, str):
            raise SourceSchemaError(f"{config['id']}: 설명/사진 형식 오류")
        if price is not None and (isinstance(price, bool) or not isinstance(price, (int, float, str))):
            raise SourceSchemaError(f"{config['id']}: 가격 형식 오류")
        name, description = clean_text(name), clean_text(description)
        item = {"name": name, "description": description,
                "menu": f"{name} · {description}" if description else name,
                "price": f"{price:,.0f}원" if isinstance(price, (int, float)) else clean_text(str(price or ""))}
        if image.strip():
            image_url = urljoin(HY_SQUARE_URL, image.strip())
            if image_url.startswith(("https://", "http://")):
                item["image"] = image_url
        grouped.setdefault(meal_type, []).append(item)
    meals = [{"type": kind, "items": grouped[kind]} for kind in MEAL_TYPES.values() if kind in grouped]
    restaurant = restaurant_record(config, meals)
    restaurant["closed"] = is_closed_day(menu_date, restaurant)
    restaurant["status"] = "available" if meals else ("closed" if restaurant["closed"] else "not_registered")
    restaurant["unavailable"] = not meals and not restaurant["closed"]
    return restaurant


def parse_embedded_menus(source: str, config: dict[str, str]) -> tuple[str, dict] | None:
    """Compatibility entry point; the live collector decodes each array only once."""
    if not re.search(r"\bconst\s+dbMenus\s*=", source):
        return None
    all_items = extract_json_array(source, "dbMenus")
    dates = {item.get("target_date") for item in all_items}
    if len(dates) != 1 or None in dates:
        raise SourceSchemaError("메뉴 날짜를 확정하지 못했습니다.")
    menu_date = dates.pop()
    return menu_date, parse_items(all_items, config, menu_date)


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
    return parse_food_court_items(facilities)


def parse_food_court_items(facilities: list[dict]) -> list[dict]:
    stores = []
    seen = set()
    for facility in facilities:
        if facility.get("id") not in FOOD_COURT_IDS:
            continue
        if facility["id"] in seen:
            raise SourceSchemaError("푸드코트 매장 ID 중복")
        seen.add(facility["id"])
        name = clean_text(str(facility.get("name") or ""))
        location = clean_text(str(facility.get("location") or ""))
        category = clean_text(str(facility.get("category") or ""))
        if name:
            stores.append({"name": name, "location": location, "category": category})

    if {store["name"] for store in stores} and len(stores) == len(FOOD_COURT_IDS):
        return stores
    raise SourceSchemaError(
        f"푸드코트 매장 {len(FOOD_COURT_IDS)}곳 중 {len(stores)}곳만 찾았습니다."
    )


def unavailable_restaurant(config: dict[str, str]) -> dict:
    restaurant = restaurant_record(config, [])
    restaurant["closed"] = False
    restaurant["unavailable"] = True
    return restaurant


def build_payload(source: str, now: datetime) -> dict:
    now = now.astimezone(KST)
    menu_date = now.date().isoformat()
    all_menus = extract_json_array(source, "dbMenus")
    print(f"파싱 시작: dbMenus={len(all_menus)}개 today={menu_date}")
    if not all_menus:
        raise SourceUnavailable("메뉴 날짜/메뉴 미등록: 새 배포 없이 마지막 정상본을 유지합니다.")
    dates = {item.get("target_date") for item in all_menus}
    if menu_date not in dates:
        raise SourceSchemaError(f"오늘 메뉴 날짜가 없습니다: source={dates}, today={menu_date}")
    try:
        facilities = extract_json_array(source, "dbFacilitiesList")
    except SourceSchemaError as exc:
        print(f"시설 목록 파싱 실패: {exc}")
        facilities = []
    checked_match = re.search(r'const sourceCheckedAt = (.*?);', source)
    checked_at = json.loads(checked_match.group(1)) if checked_match else None

    restaurants = []
    for config in CAFETERIAS:
        try:
            restaurant = parse_items(all_menus, config, menu_date)
            if not restaurant["meals"] and not any(f.get("id") == FACILITY_ID[config["id"]] for f in facilities):
                restaurant = unavailable_restaurant(config)
                restaurant["status"] = "source_error"
        except SourceSchemaError as exc:
            print(f"식당 파싱 실패: id={config['id']} exception={type(exc).__name__}: {exc}")
            restaurant = unavailable_restaurant(config)
            restaurant["status"] = "source_error"
        restaurants.append(restaurant)
        count = sum(len(meal["items"]) for meal in restaurant["meals"])
        print(f"식당 파싱 결과: id={config['id']} items={count} status={restaurant['status']}")

    if not any(r["meals"] for r in restaurants):
        raise SourceUnavailable("네 식당 메뉴를 하나도 수집하지 못해 기존 배포본을 유지합니다.")
    try:
        stores = parse_food_court_items(facilities)
        court_error = False
    except SourceSchemaError as exc:
        print(f"푸드코트 파싱 실패: exception={type(exc).__name__}: {exc}")
        stores, court_error = [], True
    print(f"푸드코트 파싱 결과: stores={len(stores)} unavailable={court_error}")
    payload = {
        "schema_version": 1, "campus": "ERICA", "date": menu_date,
        "generated_at": checked_at or now.isoformat(timespec="seconds"),
        "restaurants": restaurants,
        "food_court": {"name": "푸드코트", "note": "학생복지관 2층 입점 매장",
                       "source": FOOD_COURT_URL, "stores": stores, "unavailable": court_error},
    }
    # A programming/output-schema defect is deliberately NOT SourceUnavailable.
    validate(payload, require_today=True, now=now)
    return payload


def main() -> None:
    payload = build_payload(fetch(HY_SQUARE_URL), datetime.now(KST))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pending = OUTPUT.with_suffix(".json.pending")
    pending.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(OUTPUT)
    print(f"{payload['date']} 메뉴: 식당 4곳, 푸드코트 {len(payload['food_court']['stores'])}곳")


if __name__ == "__main__":
    main()
