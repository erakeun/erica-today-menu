import copy
import unittest
from datetime import datetime, timezone
from scripts.artifact import validate


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "schema_version": 1, "campus": "ERICA",
            "date": "2026-09-10", "generated_at": "2026-09-10T12:09:35+09:00",
            "restaurants": [
                {"id": rid, "meals": [{"type": "중식", "items": [{"menu": "시험 메뉴", "price": ""}]}]}
                for rid in ("student", "dormitory", "incubator", "faculty")
            ],
            "food_court": {"stores": [{"name": "시험 매장"}]}
        }
        self.now = datetime(2026, 9, 14, tzinfo=timezone.utc)

    def test_preserve_old_last_good(self):
        self.assertEqual(validate(self.payload, now=self.now), self.payload)

    def test_fresh_deployment_rejects_stale(self):
        with self.assertRaises(ValueError):
            validate(self.payload, now=self.now, require_today=True)

    def test_rejects_empty_and_duplicate_ids(self):
        for kind in ("empty", "duplicate"):
            p = copy.deepcopy(self.payload)
            if kind == "empty":
                for r in p["restaurants"]:
                    r.update(meals=[], unavailable=True)
            else:
                p["restaurants"][0]["id"] = "faculty"
            with self.assertRaises(ValueError):
                validate(p, now=self.now)

    def test_bad_item_and_image(self):
        for item in ({"menu": ""}, {"menu": "밥", "image": "javascript:alert(1)"}):
            p = copy.deepcopy(self.payload)
            p["restaurants"][0]["meals"][0]["items"] = [item]
            with self.assertRaises(ValueError):
                validate(p, now=self.now)

    def test_kst_date_boundary(self):
        p = self.payload
        p["date"] = "2026-09-15"
        p["generated_at"] = "2026-09-15T00:00:00+09:00"
        validate(p, now=datetime(2026, 9, 14, 15, tzinfo=timezone.utc), require_today=True)
        with self.assertRaises(ValueError):
            validate(p, now=datetime(2026, 9, 14, 14, 59, tzinfo=timezone.utc), require_today=True)

