import io
import json
import os
from email.message import Message
import unittest
import urllib.error
from unittest.mock import MagicMock, patch
from scripts import fetch_menu as m


def response(body="ok", url=m.HY_SQUARE_URL):
    value = MagicMock()
    value.__enter__.return_value = value
    value.status = 200
    value.headers = Message()
    value.headers["Content-Type"] = "text/html; charset=UTF-8"
    value.read.return_value = body.encode()
    value.geturl.return_value = url
    return value


class FetchPathTests(unittest.TestCase):
    def test_configured_relay_never_requests_direct_source(self):
        body = json.dumps({"ok": True, "source_url": m.HY_SQUARE_URL, "menus": [], "facilities": []})
        with patch.dict(os.environ, {"MENU_PROXY_URL": "https://relay.example/"}, clear=True), patch.object(m, "fetch_url", return_value=body) as request:
            m.fetch(m.HY_SQUARE_URL)
            request.assert_called_once_with("https://relay.example/", "fixed-proxy", attempts=2)

    def test_local_direct_mode(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(m, "fetch_url", return_value="HTML") as request:
            self.assertEqual(m.fetch(m.HY_SQUARE_URL), "HTML")
            request.assert_called_once_with(m.HY_SQUARE_URL, "direct", attempts=1)

    def test_actions_missing_config_is_code_configuration_failure(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with self.assertRaises(ValueError):
                m.fetch(m.HY_SQUARE_URL)

    def test_403_single_attempt_and_diagnostics(self):
        headers = Message()
        headers["Content-Type"] = "text/html"
        error = urllib.error.HTTPError(m.HY_SQUARE_URL, 403, "Forbidden", headers, io.BytesIO(b"denied"))
        with patch.object(m.OPENER, "open", side_effect=error) as request, patch.object(m.time, "sleep") as sleep:
            with self.assertRaises(m.FetchError) as caught:
                m.fetch_url(m.HY_SQUARE_URL, "direct", attempts=3)
            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(request.call_count, 1)
            sleep.assert_not_called()

    def test_timeout_retries_bounded(self):
        with patch.object(m.OPENER, "open", side_effect=TimeoutError("timed out")) as request, patch.object(m.time, "sleep"):
            with self.assertRaises(m.FetchError):
                m.fetch_url(m.HY_SQUARE_URL, "direct")
            self.assertEqual(request.call_count, 2)

    def test_final_redirect_url_is_logged(self):
        with patch.object(m.OPENER, "open", return_value=response(url="https://school.example/new")), patch("builtins.print") as log:
            self.assertEqual(m.fetch_url("https://school.example/old", "diagnostic"), "ok")
            self.assertIn("final_url=https://school.example/new", log.call_args.args[0])
            self.assertIn("bytes=2", log.call_args.args[0])
            self.assertIn("content_type=text/html", log.call_args.args[0])

    def test_block_html_is_not_proxy_json(self):
        with patch.dict(os.environ, {"MENU_PROXY_URL": "https://relay.example/"}), patch.object(m, "fetch_url", return_value="<html>Login</html>"):
            with self.assertRaises(m.SourceSchemaError):
                m.fetch(m.HY_SQUARE_URL)

    def test_relay_internal_error_is_not_suppressed(self):
        error = urllib.error.HTTPError("https://relay.example/", 500, "error", Message(), io.BytesIO(b"error"))
        with patch.object(m.OPENER, "open", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                m.fetch_url("https://relay.example/", "fixed-proxy")
            self.assertNotIsInstance(caught.exception, m.SourceUnavailable)
