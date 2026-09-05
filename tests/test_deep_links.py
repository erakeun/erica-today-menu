from pathlib import Path
import unittest


class DeepLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).parents[1] / "dist" / "index.html").read_text()

    def test_supported_restaurant_ids_have_buttons(self):
        for restaurant_id in ("student", "dormitory", "incubator", "faculty", "food-court"):
            with self.subTest(restaurant=restaurant_id):
                self.assertIn(f'data-restaurant="{restaurant_id}"', self.html)

    def test_query_is_validated_and_url_is_kept_shareable(self):
        self.assertIn("RESTAURANT_FILTERS.includes(requestedRestaurant)", self.html)
        self.assertIn("next.set('restaurant', state.restaurant)", self.html)
        self.assertIn("history.replaceState", self.html)


if __name__ == "__main__":
    unittest.main()
