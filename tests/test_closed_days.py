import unittest

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


if __name__ == "__main__":
    unittest.main()
