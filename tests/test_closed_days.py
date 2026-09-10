import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import fetch_menu
from scripts.fetch_menu import is_closed_day, parse_cafeteria, CAFETERIAS


class ClosedDayTests(unittest.TestCase):
    def restaurant(self, restaurant_id="student", meals=None):
        return {"id": restaurant_id, "meals": meals or []}

    def test_weekend_and_weekday(self):
        for restaurant_id in ("student", "incubator", "faculty"):
            with self.subTest(restaurant=restaurant_id):
                self.assertTrue(is_closed_day("2026-09-05", self.restaurant(restaurant_id)))
                self.assertTrue(is_closed_day("2026-09-06", self.restaurant(restaurant_id)))
                self.assertFalse(is_closed_day("2026-09-07", self.restaurant(restaurant_id)))

    def test_public_lunar_and_substitute_holidays(self):
        for day in ("2026-05-05", "2026-02-17", "2026-09-25", "2026-03-02"):
            with self.subTest(date=day):
                self.assertTrue(is_closed_day(day, self.restaurant()))
        self.assertFalse(is_closed_day("2026-09-04", self.restaurant()))

    def test_separate_schedules_and_real_menus(self):
        for restaurant_id in ("dormitory", "food-court", "unknown"):
            self.assertFalse(is_closed_day("2026-09-05", self.restaurant(restaurant_id)))
        self.assertFalse(is_closed_day("2026-09-05", self.restaurant(meals=[{"type": "중식", "items": [{"menu": "특별 운영 메뉴"}]}])))

    def test_parser_uses_source_menu_date(self):
        source = '''<div class="hyu-pagination-inner"><h1>2026/09/05</h1></div>
        <div id="menu_dailyView"><h3 class="hyu-element">중식</h3></div>
        <div id="menu_weeklyView">'''
        day, restaurant = parse_cafeteria(source, CAFETERIAS[0])
        self.assertEqual(day, "2026-09-05")
        self.assertTrue(restaurant["closed"])

    def test_unknown_calendar_year_is_not_silently_a_weekday(self):
        with self.assertRaisesRegex(RuntimeError, "공휴일 자료"):
            is_closed_day("2036-09-01", self.restaurant())


class CurrentPortalParserTests(unittest.TestCase):
    source = '''
    <script>
      const dbMenus = [
        {"meal_type":"breakfast","name":"천원의 아침밥","description":"쌀밥\\r\\n깍두기", "price":1000,
         "image_url":"/uploads/breakfast.jpg","target_date":"2026-09-10","facility_name":"학생식당"},
        {"meal_type":"lunch","name":"제육덮밥","description":"배추김치", "price":4500,
         "image_url":null,"target_date":"2026-09-10","facility_name":"학생식당"},
        {"meal_type":"lunch","name":"교직원 메뉴","description":"", "price":7000,
         "image_url":null,"target_date":"2026-09-10","facility_name":"교직원식당"},
        {"meal_type":"lunch","name":"창업 메뉴","description":"", "price":6500,
         "image_url":null,"target_date":"2026-09-10","facility_name":"창업보육센터식당"},
        {"meal_type":"dinner","name":"기숙사 메뉴","description":"", "price":5000,
         "image_url":null,"target_date":"2026-09-10","facility_name":"창의인재원식당"}
      ];
      const dbFacilitiesList = [
        {"id":12,"name":"BLUEPOT","category":"카페/베이커리","location":"학생복지관 2F"},
        {"id":13,"name":"Pan&Wok","category":"일반음식점","location":"학생복지관 2층"},
        {"id":14,"name":"33떡볶이&꼬마김밥","category":"일반음식점","location":"학생복지관 2층"},
        {"id":15,"name":"FRESH BURRITOS","category":"일반음식점","location":"학생복지관 2층"},
        {"id":16,"name":"바비든든","category":"일반음식점","location":"학생복지관 2층"},
        {"id":17,"name":"산쪼메","category":"일반음식점","location":"학생복지관 2층"},
        {"id":18,"name":"NEW YORK BURGER","category":"일반음식점","location":"학생복지관 2층"}
      ];
    </script>
    '''

    def test_parses_embedded_json_date_and_only_selected_restaurant(self):
        day, restaurant = parse_cafeteria(self.source, CAFETERIAS[0])

        self.assertEqual(day, "2026-09-10")
        self.assertEqual([meal["type"] for meal in restaurant["meals"]], ["조식", "중식"])
        self.assertEqual(restaurant["meals"][0]["items"][0]["name"], "천원의 아침밥")
        self.assertEqual(restaurant["meals"][0]["items"][0]["description"], "쌀밥 깍두기")
        self.assertEqual(restaurant["meals"][0]["items"][0]["price"], "1,000원")
        self.assertEqual(
            restaurant["meals"][0]["items"][0]["image"],
            "https://life.hanyang.ac.kr/uploads/breakfast.jpg",
        )
        self.assertNotIn("교직원 메뉴", json.dumps(restaurant, ensure_ascii=False))

    def test_one_request_updates_good_restaurants_and_isolates_missing_one(self):
        source = self.source.replace('"facility_name":"학생식당"', '"facility_name":"미등록식당"')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "menu.json"
            with (
                patch.object(fetch_menu, "fetch", return_value=source) as mocked_fetch,
                patch.object(fetch_menu, "OUTPUT", output),
            ):
                fetch_menu.main()

            payload = json.loads(output.read_text())

        mocked_fetch.assert_called_once_with(fetch_menu.HY_SQUARE_URL)
        self.assertEqual(payload["date"], "2026-09-10")
        self.assertEqual(len(payload["restaurants"]), 4)
        self.assertTrue(payload["restaurants"][0]["unavailable"])
        self.assertEqual(payload["restaurants"][0]["meals"], [])
        self.assertTrue(payload["restaurants"][1]["meals"])
        self.assertEqual(len(payload["food_court"]["stores"]), 7)
        self.assertEqual(payload["food_court"]["stores"][1]["name"], "Pan&Wok")

    def test_total_failure_keeps_existing_output(self):
        broken_source = "<script>const dbMenus = [];</script>"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "menu.json"
            output.write_text("last good deployment", encoding="utf-8")
            with (
                patch.object(fetch_menu, "fetch", return_value=broken_source),
                patch.object(fetch_menu, "OUTPUT", output),
            ):
                with self.assertRaisesRegex(RuntimeError, "메뉴 날짜"):
                    fetch_menu.main()

            self.assertEqual(output.read_text(), "last good deployment")


if __name__ == "__main__":
    unittest.main()
