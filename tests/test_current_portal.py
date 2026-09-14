from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import fetch_menu as m, refresh_menu

NOW = datetime(2026, 9, 14, 12, tzinfo=m.KST)
FIXTURE = (Path(__file__).parent / 'fixtures/hy_square_2026-09-14.html').read_text()


def source(menus=None, facilities=None):
    if menus is None:
        menus = m.extract_json_array(FIXTURE, 'dbMenus')
    if facilities is None:
        facilities = m.extract_json_array(FIXTURE, 'dbFacilitiesList')
    return f'const dbMenus = {json.dumps(menus)}; const dbFacilitiesList = {json.dumps(facilities)};'


class CurrentSourceTests(unittest.TestCase):
    def test_actual_september14_fixture(self):
        data = m.build_payload(FIXTURE, NOW)
        self.assertEqual([sum(len(meal['items']) for meal in r['meals']) for r in data['restaurants']], [3, 4, 2, 2])
        self.assertEqual(len(data['food_court']['stores']), 7)
        self.assertIn('꼬치어묵탕', data['restaurants'][0]['meals'][0]['items'][0]['menu'])
        self.assertEqual(data['restaurants'][0]['meals'][0]['items'][0]['price'], '1,000원')
        self.assertTrue(data['restaurants'][0]['meals'][0]['items'][0]['image'].startswith('https://life.hanyang.ac.kr/uploads/'))

    def test_login_block_and_missing_array(self):
        for page in ['<html>Login</html>', '<h1>Access Denied</h1>', 'const dbFacilitiesList = [];']:
            with self.subTest(page=page), self.assertRaises(m.SourceSchemaError):
                m.build_payload(page, NOW)

    def test_one_bad_restaurant_isolated(self):
        menus = m.extract_json_array(FIXTURE, 'dbMenus')
        for item in menus:
            if item['facility_id'] == 1:
                item.pop('target_date')
        data = m.build_payload(source(menus), NOW)
        self.assertEqual(data['restaurants'][0]['status'], 'source_error')
        self.assertTrue(all(r['meals'] for r in data['restaurants'][1:]))

    def test_missing_one_registered_facility_means_not_registered(self):
        menus = [i for i in m.extract_json_array(FIXTURE, 'dbMenus') if i['facility_id'] != 1]
        data = m.build_payload(source(menus), NOW)
        self.assertEqual(data['restaurants'][0]['status'], 'not_registered')

    def test_all_empty_missing_dates_and_old_date_are_not_publishable(self):
        for page in [source([]), FIXTURE.replace('2026-09-14', '2026-09-13'), FIXTURE.replace('target_date', 'missing_date')]:
            with self.subTest(page=page[:40]), self.assertRaises(m.SourceUnavailable):
                m.build_payload(page, NOW)

    def test_multiple_dates_select_only_today(self):
        menus = m.extract_json_array(FIXTURE, 'dbMenus')
        menus.append({**menus[0], 'target_date': '2026-09-13', 'name': 'YESTERDAY'})
        data = m.build_payload(source(menus), NOW)
        self.assertNotIn('YESTERDAY', json.dumps(data))

    def test_food_court_drift_is_isolated(self):
        facilities = [f for f in m.extract_json_array(FIXTURE, 'dbFacilitiesList') if f['id'] != 12]
        data = m.build_payload(source(facilities=facilities), NOW)
        self.assertTrue(data['food_court']['unavailable'])
        self.assertTrue(all(r['meals'] for r in data['restaurants']))

    def test_optional_null_fields(self):
        menus = m.extract_json_array(FIXTURE, 'dbMenus')
        menus[0].update(price=None, image_url=None, description=None)
        item = m.build_payload(source(menus), NOW)['restaurants'][0]['meals'][0]['items'][0]
        self.assertEqual(item['price'], '')
        self.assertEqual(item['description'], '')
        self.assertNotIn('image', item)

    def test_kst_boundary(self):
        utc = datetime.fromisoformat('2026-09-13T15:00:00+00:00')
        self.assertEqual(m.build_payload(FIXTURE, utc)['date'], '2026-09-14')

    def test_original_checked_at_not_replaced_by_cache_read_time(self):
        data = m.build_payload(FIXTURE + '\nconst sourceCheckedAt = "2026-09-14T00:00:00Z";', NOW)
        self.assertEqual(data['generated_at'], '2026-09-14T00:00:00Z')

    def test_output_unchanged_on_source_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'menu.json'
            output.write_text('LAST GOOD')
            with patch.object(m, 'OUTPUT', output), patch.object(m, 'fetch', side_effect=m.FetchError('403')):
                with self.assertRaises(m.SourceUnavailable):
                    m.main()
            self.assertEqual(output.read_text(), 'LAST GOOD')

    def test_scheduler_only_swallows_expected_source_errors(self):
        with patch.object(refresh_menu, 'main', side_effect=m.FetchError('503')):
            self.assertFalse(refresh_menu.run())
        with patch.object(refresh_menu, 'main', side_effect=TypeError('code defect')):
            with self.assertRaises(TypeError):
                refresh_menu.run()

    def test_ui_stale_and_different_empty_states(self):
        page = (Path(__file__).parents[1] / 'dist/index.html').read_text()
        for text in ['마지막 확인된 메뉴', '지난 메뉴', '마지막 정상 갱신', '오늘 메뉴 미등록', '원본 조회 일시 실패', 'Asia/Seoul']:
            self.assertIn(text, page)


if __name__ == '__main__':
    unittest.main()
