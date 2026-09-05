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
        "url": "https://www.hanyang.ac.kr/re12",
    },
    {
        "id": "dormitory",
        "name": "창의인재원식당",
        "location": "창의관 1층",
        "hours": "조식 07:40–09:00 · 중식 11:30–13:20 · 석식 17:10–18:40",
        "url": "https://www.hanyang.ac.kr/re13",
    },
    {
        "id": "incubator",
        "name": "창업보육센터",
        "location": "창업보육센터 지하 1층",
        "hours": "중식 11:30–13:30 · 석식 17:00–18:30",
        "url": "https://www.hanyang.ac.kr/re15",
    },
    {
        "id": "faculty",
        "name": "교직원식당",
        "location": "복지관 3층",
        "hours": "중식 11:30–13:30",
        "url": "https://www.hanyang.ac.kr/re11",
    },
)

FOOD_COURT_URL = "https://www.hanyang.ac.kr/re14"
# Campus operating policy: the dormitory and food court have separate schedules.
WEEKDAY_ONLY_RESTAURANTS = {"student", "incubator", "faculty"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)
REQUEST_DELAY_SECONDS = 3
OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(CookieJar())
)


def fetch(url: str, attempts: int = 5) -> str:
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
                return response.read().decode(charset, errors="replace")
        except Exception as exc:  # urllib raises several transport error types.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"공식 페이지를 불러오지 못했습니다: {url}") from last_error


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


def parse_cafeteria(source: str, config: dict[str, str]) -> tuple[str, dict]:
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

    restaurant = {
        "id": config["id"],
        "name": config["name"],
        "location": config["location"],
        "hours": config["hours"],
        "source": config["url"],
        "meals": meals,
    }
    menu_date = date_match.group(1).replace("/", "-")
    restaurant["closed"] = is_closed_day(menu_date, restaurant)
    return menu_date, restaurant


def parse_food_court(source: str) -> list[dict]:
    table_match = re.search(
        r'<th[^>]*>.*?상호명.*?</th>.*?<tbody>(.*?)</tbody>',
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        raise RuntimeError("푸드코트 페이지의 매장 표가 변경되었습니다.")

    stores: list[dict] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        values = [clean_text(cell) for cell in cells]
        if len(values) >= 3:
            stores.append(
                {
                    "name": values[0],
                    "hours": values[1],
                    "menu": values[2],
                }
            )
        elif len(values) == 1 and stores:
            stores[-1]["menu"] = f"{stores[-1]['menu']}, {values[0]}"

    if not stores:
        raise RuntimeError("푸드코트 매장 정보를 찾지 못했습니다.")
    return stores


def main() -> None:
    dates: set[str] = set()
    restaurants: list[dict] = []

    for config in CAFETERIAS:
        menu_date, restaurant = parse_cafeteria(fetch(config["url"]), config)
        dates.add(menu_date)
        restaurants.append(restaurant)
        # Avoid a burst of requests against the university's public site.
        time.sleep(REQUEST_DELAY_SECONDS)

    if len(dates) != 1:
        raise RuntimeError(f"식당별 메뉴 날짜가 일치하지 않습니다: {sorted(dates)}")

    now = datetime.now(KST)
    payload = {
        "schema_version": 1,
        "campus": "ERICA",
        "date": dates.pop(),
        "generated_at": now.isoformat(timespec="seconds"),
        "restaurants": restaurants,
        "food_court": {
            "name": "푸드코트",
            "note": "고정 운영 매장과 대표 메뉴",
            "source": FOOD_COURT_URL,
            "stores": parse_food_court(fetch(FOOD_COURT_URL)),
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
