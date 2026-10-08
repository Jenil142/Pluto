"""
Unit and Contract Verification Suite for Pluto Backend API.
Uses unittest and FastAPI TestClient.
"""

import unittest
from fastapi.testclient import TestClient

from api import app, generate_local_fallback


class TestPlutoApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_health_endpoint(self):
        """Verify GET /api/health returns 200 and contract payload."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers.get("content-type", "").startswith("application/json")
        )
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "pluto-api")

    def test_02_health_alias(self):
        """Verify GET /health and GET / fallback aliases return 200."""
        for path in ["/health", "/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("service"), "pluto-api")

    def test_03_chat_endpoint_valid_message(self):
        """Verify POST /api/chat accepts query and returns structured response."""
        payload = {"message": "Hello Pluto, status check"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers.get("content-type", "").startswith("application/json")
        )
        data = response.json()
        self.assertIn("reply", data)
        self.assertIsInstance(data["reply"], str)
        self.assertGreater(len(data["reply"]), 0)
        self.assertIn("state", data)
        self.assertEqual(data["state"], "idle")

    def test_04_chat_endpoint_missing_message(self):
        """Verify POST /api/chat with missing body returns 422 validation error."""
        # Empty body
        response_empty_body = self.client.post("/api/chat", json={})
        self.assertEqual(response_empty_body.status_code, 422)

        # Empty string
        response_empty_str = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(response_empty_str.status_code, 422)

    def test_05_cors_headers_on_get(self):
        """Verify CORS headers when Origin header is provided."""
        headers = {"Origin": "http://localhost:5173"}
        response = self.client.get("/api/health", headers=headers)
        self.assertEqual(response.status_code, 200)
        allow_origin = response.headers.get("access-control-allow-origin")
        self.assertIn(allow_origin, ["http://localhost:5173", "*"])

    def test_06_cors_preflight_options(self):
        """Verify CORS preflight OPTIONS request for /api/chat."""
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = self.client.options("/api/chat", headers=headers)
        self.assertEqual(response.status_code, 200)
        allow_origin = response.headers.get("access-control-allow-origin")
        self.assertIn(allow_origin, ["http://localhost:5173", "*"])
        allow_methods = response.headers.get("access-control-allow-methods", "")
        self.assertIn("POST", allow_methods)

    def test_07_local_fallback_functionality(self):
        """Verify local fallback logic produces helpful offline responses."""
        time_reply = generate_local_fallback("What time is it?")
        self.assertIn("currently", time_reply.lower())

        date_reply = generate_local_fallback("What is today's date?")
        self.assertIn("today is", date_reply.lower())

        status_reply = generate_local_fallback("System status")
        self.assertIn("pluto local backend is active", status_reply.lower())

        unknown_reply = generate_local_fallback("Tell me a story", reason="Testing offline mode")
        self.assertIn("fallback mode", unknown_reply.lower())


if __name__ == "__main__":
    unittest.main()
