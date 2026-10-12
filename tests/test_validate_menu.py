import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import validate_menu
from scripts.artifact import KST


class ValidateMenuFileTests(unittest.TestCase):
    def test_validates_utf8_menu_with_korean_text(self):
        now = datetime.now(KST)
        payload = {
            "schema_version": 1, "campus": "ERICA",
            "date": now.date().isoformat(), "generated_at": now.isoformat(),
            "restaurants": [
                {"id": rid, "meals": [{"type": "중식", "items": [{"menu": "한글 검증 메뉴"}]}]}
                for rid in ("student", "dormitory", "incubator", "faculty")
            ],
            "food_court": {"stores": [{"name": "가상 매장"}]},
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "dist").mkdir()
            artifact = root / "dist/menu.json"
            original = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            artifact.write_bytes(original)
            output = io.StringIO()
            with patch.object(validate_menu, "__file__", str(root / "scripts/validate_menu.py")), patch("sys.stdout", output):
                validate_menu.main()
            self.assertIn("restaurants=4", output.getvalue())
            self.assertEqual(artifact.read_bytes(), original)
