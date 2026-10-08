"""
Adversarial Boundary, CORS Security, and Failure Mode Test Suite for Pluto Backend API.
Path: /home/jenil/Pluto/tests/test_adversarial_boundary.py

Empirically tests:
1. Malformed payloads, schema violations, type mismatches, and massive payloads.
2. SQL injection strings, command injection syntax, and database table integrity.
3. Multibyte unicode, emojis, RTL scripts, CJK scripts, and zalgo text.
4. Empty strings, pure whitespace, and null bytes (escaped and raw).
5. Unsupported HTTP methods (PUT, DELETE, PATCH, GET) on /api/chat and /api/health.
6. CORS origin filtering: allowed origins vs disallowed/spoofed origins and preflight.
7. Consistent JSON error bodies (no unhandled HTML tracebacks or crashes).
8. Internal failure modes: core timeouts, core exceptions, and database write errors.
9. Live server lifecycle verification on port 8000 with complete process cleanup.
"""

import os
import sys
import json
import time
import socket
import signal
import sqlite3
import unittest
import subprocess
import urllib.request
import urllib.error
from unittest.mock import patch, AsyncMock
from datetime import datetime

from fastapi.testclient import TestClient

# Ensure root Pluto directory is in Python path
sys.path.insert(0, "/home/jenil/Pluto")

from api import app
from pluto.memory.chat_history import DATABASE_PATH


class TestAdversarialBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _assert_json_error(self, response, expected_status=None):
        """Helper to verify response is valid JSON and not an HTML traceback."""
        if expected_status:
            self.assertEqual(
                response.status_code,
                expected_status,
                f"Expected status {expected_status}, got {response.status_code}. Body: {response.text}"
            )
        content_type = response.headers.get("content-type", "")
        self.assertTrue(
            content_type.startswith("application/json"),
            f"Expected application/json content-type, got '{content_type}'. Body: {response.text}"
        )
        try:
            data = response.json()
            self.assertIsInstance(data, (dict, list))
            if isinstance(data, dict):
                self.assertTrue("detail" in data or "reply" in data or "status" in data)
            return data
        except Exception as exc:
            self.fail(f"Response body is not valid JSON: {response.text}. Error: {exc}")

    # =========================================================================
    # 1. Boundary & Malformed Inputs
    # =========================================================================

    def test_01_malformed_json_unclosed_bracket(self):
        """Verify unclosed JSON returns HTTP 400 or 422 with structured JSON error."""
        response = self.client.post(
            "/api/chat",
            content=b'{"message": "unclosed string',
            headers={"Content-Type": "application/json"}
        )
        self.assertIn(response.status_code, [400, 422])
        self._assert_json_error(response)

    def test_02_malformed_json_raw_garbage(self):
        """Verify arbitrary binary garbage returns HTTP 400 or 422 with JSON error."""
        response = self.client.post(
            "/api/chat",
            content=b"\xff\xfe\x00\x01\x02\x03\x04",
            headers={"Content-Type": "application/json"}
        )
        self.assertIn(response.status_code, [400, 422])
        self._assert_json_error(response)

    def test_03_malformed_json_empty_body(self):
        """Verify empty body with application/json header returns HTTP 400 or 422."""
        response = self.client.post(
            "/api/chat",
            content=b"",
            headers={"Content-Type": "application/json"}
        )
        self.assertIn(response.status_code, [400, 422])
        self._assert_json_error(response)

    def test_04_invalid_types_boolean(self):
        """Verify boolean value for string field returns HTTP 422."""
        response = self.client.post("/api/chat", json={"message": True})
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_05_invalid_types_null(self):
        """Verify null/None value for string field returns HTTP 422."""
        response = self.client.post("/api/chat", json={"message": None})
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_06_invalid_types_array(self):
        """Verify array value for string field returns HTTP 422."""
        response = self.client.post("/api/chat", json={"message": ["malicious", "payload"]})
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_07_invalid_types_object(self):
        """Verify dictionary object for string field returns HTTP 422."""
        response = self.client.post("/api/chat", json={"message": {"nested": "dict"}})
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_08_root_type_array(self):
        """Verify JSON array at root level returns HTTP 422."""
        response = self.client.post("/api/chat", json=[{"message": "test"}])
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_09_extra_unexpected_fields(self):
        """Verify extra unexpected fields are tolerated and return HTTP 200."""
        payload = {
            "message": "Status check with extra parameters",
            "admin": True,
            "role": "superuser",
            "__proto__": {"injected": True}
        }
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Extra parameters handled safely."
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertEqual(data.get("reply"), "Extra parameters handled safely.")
            self.assertEqual(data.get("state"), "idle")

    def test_10_large_payload_stress(self):
        """Verify large string payload (100KB) does not crash or exhaust server."""
        large_text = "Pluto system check " * 5000  # ~95 KB
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Large payload processed cleanly."
            response = self.client.post("/api/chat", json={"message": large_text})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertEqual(data.get("reply"), "Large payload processed cleanly.")
            self.assertEqual(data.get("state"), "idle")

    # =========================================================================
    # 2. SQL Injection and Code Injection Defense
    # =========================================================================

    def test_11_sqli_drop_table_attempt(self):
        """Verify SQL injection attempting to drop table does not corrupt database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        self.assertIsNotNone(cur.fetchone(), "messages table must exist initially")
        conn.close()

        sqli_payload = "'; DROP TABLE messages; SELECT * FROM messages WHERE '1'='1"
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "SQL injection payload handled as text."
            response = self.client.post("/api/chat", json={"message": sqli_payload})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)

        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        table_exists = cur.fetchone()
        self.assertIsNotNone(table_exists, "messages table must NOT be dropped by SQL injection payload")
        conn.close()

    def test_12_sqli_tautology_and_union(self):
        """Verify SQL tautology and union strings execute cleanly without SQL errors."""
        payloads = [
            "' OR '1'='1' --",
            "\" OR \"1\"=\"1\" --",
            "' UNION SELECT 1, 'injected', datetime('now') --",
            "admin'--",
            "1; EXEC xp_cmdshell('dir');"
        ]
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "SQL string treated as plain text query."
            for payload in payloads:
                response = self.client.post("/api/chat", json={"message": payload})
                self.assertEqual(response.status_code, 200)
                data = self._assert_json_error(response)
                self.assertIn("reply", data)
                self.assertEqual(data.get("state"), "idle")

    def test_13_command_and_template_injection(self):
        """Verify shell and template syntax is treated safely as inert text."""
        payload = "; cat /etc/passwd; $(whoami); `id`; {{ 7 * 7 }} ${7*7} <% 7*7 %>"
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Command injection syntax treated safely as text."
            response = self.client.post("/api/chat", json={"message": payload})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)

    # =========================================================================
    # 3. Unicode and Character Encodings
    # =========================================================================

    def test_14_unicode_emojis_and_symbols(self):
        """Verify multibyte emojis and mathematical symbols pass safely."""
        emoji_query = "Pluto mission 🤖🚀🪐✨🔥 π ≈ 3.14159 ∞ ≠ 0"
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Emoji and symbol query processed cleanly: 🤖🪐"
            response = self.client.post("/api/chat", json={"message": emoji_query})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)
            self.assertIn("🤖", data["reply"])

    def test_15_unicode_multilingual_scripts(self):
        """Verify Arabic, Hebrew, CJK, Cyrillic, and Greek scripts pass safely."""
        multilingual = (
            "العربية: مرحبا بكم في بلوتو | "
            "עברית: שלום פلوטו | "
            "中文: 欢迎使用冥王星系统 | "
            "日本語: プルートAIへようこそ | "
            "한국어: 명왕성 시스템에 오신 것을 환영합니다 | "
            "Русский: Привет от Плутона | "
            "Ελληνικά: Γειά σου Πλούτωνα"
        )
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Multilingual query processed successfully."
            response = self.client.post("/api/chat", json={"message": multilingual})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)

    def test_16_unicode_zalgo_and_zero_width(self):
        """Verify combining diacritics (zalgo) and zero-width characters."""
        zalgo_text = "H̷e̸l̴l̵o̸\u200b\u200c\u200d ̷P̷l̷u̸t̵o̸"
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Zalgo query processed safely."
            response = self.client.post("/api/chat", json={"message": zalgo_text})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)

    # =========================================================================
    # 4. Empty Strings, Pure Whitespace, and Null Bytes
    # =========================================================================

    def test_17_empty_string_rejected_by_schema(self):
        """Verify empty string returns HTTP 422 because min_length=1."""
        response = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(response.status_code, 422)
        data = self._assert_json_error(response)
        self.assertIn("detail", data)

    def test_18_whitespace_handled_gracefully(self):
        """Verify whitespace-only string returns fallback guidance without crashing."""
        for ws in ["   ", "\t\t\t", "\n\n\r\n", "  \t \n  "]:
            response = self.client.post("/api/chat", json={"message": ws})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertEqual(data.get("reply"), "Please provide a valid query.")
            self.assertEqual(data.get("state"), "idle")

    def test_19_escaped_null_byte_in_json(self):
        """Verify escaped null byte \\u0000 in JSON payload does not crash server."""
        payload = {"message": "prefix\\u0000injected_null\\u0000suffix"}
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Null byte query handled."
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)

    def test_20_raw_null_byte_in_stream(self):
        """Verify raw unescaped null byte in JSON stream returns 400 or 422 JSON error."""
        raw_payload = b'{"message": "raw\x00byte"}'
        response = self.client.post(
            "/api/chat",
            content=raw_payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertIn(response.status_code, [400, 422])
        self._assert_json_error(response)

    # =========================================================================
    # 5. Unsupported HTTP Methods
    # =========================================================================

    def test_21_unsupported_methods_chat(self):
        """Verify PUT, DELETE, PATCH, GET on /api/chat return HTTP 405 with JSON error."""
        methods = ["put", "delete", "patch", "get"]
        for method in methods:
            func = getattr(self.client, method)
            response = func("/api/chat")
            self.assertEqual(
                response.status_code,
                405,
                f"Method {method.upper()} on /api/chat should return 405, got {response.status_code}"
            )
            data = self._assert_json_error(response)
            self.assertIn("detail", data)
            self.assertEqual(data["detail"], "Method Not Allowed")

    def test_22_unsupported_methods_health(self):
        """Verify POST, PUT, DELETE, PATCH on /api/health return HTTP 405 with JSON error."""
        methods = ["post", "put", "delete", "patch"]
        for method in methods:
            func = getattr(self.client, method)
            response = func("/api/health")
            self.assertEqual(
                response.status_code,
                405,
                f"Method {method.upper()} on /api/health should return 405, got {response.status_code}"
            )
            data = self._assert_json_error(response)
            self.assertIn("detail", data)
            self.assertEqual(data["detail"], "Method Not Allowed")

    # =========================================================================
    # 6. CORS Origin Security Verification
    # =========================================================================

    def test_23_cors_allowed_origins(self):
        """Verify allowed origins receive Access-Control-Allow-Origin header."""
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:9000",
        ]
        for origin in allowed_origins:
            response = self.client.get("/api/health", headers={"Origin": origin})
            self.assertEqual(response.status_code, 200)
            allow_origin = response.headers.get("access-control-allow-origin")
            self.assertEqual(
                allow_origin,
                origin,
                f"Expected Access-Control-Allow-Origin: {origin}, got: {allow_origin}"
            )

    def test_24_cors_disallowed_origins(self):
        """Verify disallowed and spoofed origins do NOT receive Access-Control-Allow-Origin."""
        disallowed_origins = [
            "http://evil.com",
            "https://malicious.org",
            "http://localhost.evil.com",
            "http://127.0.0.1.attacker.com",
            "null",
            "http://fake-localhost:5173",
        ]
        for origin in disallowed_origins:
            response = self.client.get("/api/health", headers={"Origin": origin})
            self.assertEqual(response.status_code, 200)
            allow_origin = response.headers.get("access-control-allow-origin")
            self.assertNotEqual(
                allow_origin,
                origin,
                f"Disallowed origin {origin} was improperly granted CORS access!"
            )
            self.assertIsNone(
                allow_origin,
                f"Disallowed origin {origin} should receive no allow-origin header, got: {allow_origin}"
            )

    def test_25_cors_preflight_allowed_vs_disallowed(self):
        """Verify CORS preflight OPTIONS behavior for allowed vs disallowed origins."""
        # Allowed origin preflight
        preflight_headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        res_allowed = self.client.options("/api/chat", headers=preflight_headers)
        self.assertEqual(res_allowed.status_code, 200)
        self.assertEqual(
            res_allowed.headers.get("access-control-allow-origin"),
            "http://localhost:5173"
        )
        self.assertIn("POST", res_allowed.headers.get("access-control-allow-methods", ""))

        # Disallowed origin preflight
        disallowed_preflight = {
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        res_disallowed = self.client.options("/api/chat", headers=disallowed_preflight)
        allow_origin = res_disallowed.headers.get("access-control-allow-origin")
        self.assertIsNone(
            allow_origin,
            f"Preflight from evil.com should not return allow-origin header, got: {allow_origin}"
        )

    # =========================================================================
    # 7. Error Consistency (JSON Error Bodies on 404)
    # =========================================================================

    def test_26_not_found_endpoints_return_json(self):
        """Verify 404 responses return application/json with detail error object."""
        endpoints = [
            ("GET", "/api/nonexistent"),
            ("POST", "/api/unknown_route"),
            ("DELETE", "/does_not_exist")
        ]
        for method, path in endpoints:
            func = getattr(self.client, method.lower())
            response = func(path)
            self.assertEqual(response.status_code, 404)
            data = self._assert_json_error(response, expected_status=404)
            self.assertIn("detail", data)
            self.assertEqual(data["detail"], "Not Found")

    # =========================================================================
    # 8. Internal Failure Modes (Timeouts, Exceptions, DB Faults)
    # =========================================================================

    def test_27_core_timeout_returns_fallback_json(self):
        """Verify 15-second core timeout triggers graceful local fallback with HTTP 200."""
        import asyncio
        with patch("api._process_core_query", side_effect=asyncio.TimeoutError):
            response = self.client.post("/api/chat", json={"message": "Query that hangs"})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)
            self.assertIn("fallback mode", data["reply"].lower())
            self.assertEqual(data.get("state"), "idle")

    def test_28_core_exception_returns_fallback_json(self):
        """Verify unhandled core exception returns fallback response rather than 500 HTML."""
        with patch("api._process_core_query", side_effect=RuntimeError("Google Gemini connection reset")):
            response = self.client.post("/api/chat", json={"message": "Query that crashes"})
            self.assertEqual(response.status_code, 200)
            data = self._assert_json_error(response)
            self.assertIn("reply", data)
            self.assertIn("fallback mode", data["reply"].lower())
            self.assertEqual(data.get("state"), "idle")

    def test_29_db_persistence_failure_tolerated(self):
        """Verify failure in SQLite history persistence does not crash chat endpoint."""
        with patch("api._process_core_query", new_callable=AsyncMock) as mock_core:
            mock_core.return_value = "Normal reply with corrupted DB"
            with patch("api.save_messages", side_effect=sqlite3.OperationalError("database is locked")):
                response = self.client.post("/api/chat", json={"message": "Query with DB error"})
                self.assertEqual(response.status_code, 200)
                data = self._assert_json_error(response)
                self.assertEqual(data.get("reply"), "Normal reply with corrupted DB")
                self.assertEqual(data.get("state"), "idle")


# =========================================================================
# 9. Live Server Lifecycle & Port Release Harness
# =========================================================================

def is_port_in_use(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_live_server_adversarial_test():
    """Starts Uvicorn subprocess, executes live boundary checks over HTTP, cleanly terminates."""
    print("\n--- Live Server Adversarial Lifecycle Test ---")
    if is_port_in_use(8000):
        print("FAIL: Port 8000 already in use before test.")
        return False

    server_cmd = [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"]
    proc = subprocess.Popen(
        server_cmd,
        cwd="/home/jenil/Pluto",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

    clean = False
    try:
        # Wait for server ready
        ready = False
        start = time.time()
        while time.time() - start < 10.0:
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/api/health")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.2)

        if not ready:
            print("FAIL: Live server failed to respond within 10 seconds.")
            return False
        print("Live server started successfully on port 8000.")

        # Test live CORS allowed origin
        req_allowed = urllib.request.Request(
            "http://127.0.0.1:8000/api/health",
            headers={"Origin": "http://localhost:5173"}
        )
        with urllib.request.urlopen(req_allowed, timeout=3.0) as resp:
            cors_hdr = resp.headers.get("Access-Control-Allow-Origin")
            assert cors_hdr == "http://localhost:5173", f"Expected http://localhost:5173, got {cors_hdr}"
            print("Live CORS allowed origin check: PASSED.")

        # Test live CORS disallowed origin
        req_disallowed = urllib.request.Request(
            "http://127.0.0.1:8000/api/health",
            headers={"Origin": "http://malicious.org"}
        )
        with urllib.request.urlopen(req_disallowed, timeout=3.0) as resp:
            cors_hdr = resp.headers.get("Access-Control-Allow-Origin")
            assert cors_hdr is None, f"Disallowed origin received CORS header: {cors_hdr}"
            print("Live CORS disallowed origin check: PASSED (No allow-origin header).")

        # Test live malformed JSON (raw bytes)
        req_malformed = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=b'{"bad json',
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req_malformed, timeout=3.0)
            print("FAIL: Malformed JSON did not raise HTTP error.")
            return False
        except urllib.error.HTTPError as err:
            assert err.code in [400, 422], f"Expected 400 or 422, got {err.code}"
            err_body = err.read().decode("utf-8")
            parsed_err = json.loads(err_body)
            assert "detail" in parsed_err, f"Missing detail in error response: {parsed_err}"
            print(f"Live malformed JSON check: PASSED (HTTP {err.code}, valid JSON error).")

        # Test live unsupported method
        req_unsupported = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        try:
            urllib.request.urlopen(req_unsupported, timeout=3.0)
            print("FAIL: Unsupported method PUT did not raise HTTP error.")
            return False
        except urllib.error.HTTPError as err:
            assert err.code == 405, f"Expected 405, got {err.code}"
            err_body = err.read().decode("utf-8")
            parsed_err = json.loads(err_body)
            assert parsed_err.get("detail") == "Method Not Allowed"
            print("Live unsupported method check: PASSED (HTTP 405, Method Not Allowed).")

        # Test live whitespace query (handled by local logic without triggering Gemini)
        ws_data = json.dumps({"message": "     \n\t  "}).encode("utf-8")
        req_ws = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=ws_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_ws, timeout=5.0) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            ws_body = json.loads(resp.read().decode("utf-8"))
            assert ws_body.get("reply") == "Please provide a valid query."
            print("Live whitespace boundary check: PASSED (HTTP 200, prompt guidance).")

        # Test live 404 Not Found JSON error
        req_404 = urllib.request.Request("http://127.0.0.1:8000/api/unknown_endpoint")
        try:
            urllib.request.urlopen(req_404, timeout=3.0)
            print("FAIL: Nonexistent route did not raise HTTP error.")
            return False
        except urllib.error.HTTPError as err:
            assert err.code == 404, f"Expected 404, got {err.code}"
            err_body = err.read().decode("utf-8")
            parsed_err = json.loads(err_body)
            assert parsed_err.get("detail") == "Not Found"
            print("Live 404 Not Found check: PASSED (HTTP 404, structured JSON error).")

        # Test live SQL injection string on live server
        sqli_data = json.dumps({"message": "'; DROP TABLE messages; --"}).encode("utf-8")
        req_sqli = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=sqli_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_sqli, timeout=20.0) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            sqli_body = json.loads(resp.read().decode("utf-8"))
            assert "reply" in sqli_body
            assert sqli_body.get("state") == "idle"
            print("Live SQL injection boundary check: PASSED (HTTP 200, handled safely).")

        # Confirm SQLite table still exists after live injection
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        assert cur.fetchone() is not None, "messages table was dropped by live SQL injection!"
        conn.close()
        print("Live database integrity check: PASSED (table preserved).")

        return True

    finally:
        print("Cleaning up live server process group...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3.0)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

        time.sleep(0.5)
        clean = not is_port_in_use(8000)
        if clean:
            print("Port 8000 released successfully. Live lifecycle verified.")
        else:
            print("FAIL: Port 8000 was not released after process termination.")

    return clean


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAdversarialBoundary)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    live_ok = run_live_server_adversarial_test()

    all_passed = result.wasSuccessful() and live_ok
    print(f"\nFinal Adversarial Boundary Suite Result: {'PASS' if all_passed else 'FAIL'}")
    sys.exit(0 if all_passed else 1)
