"""
Pluto Browser Automation Service
Runs inside Docker container. Exposes a lightweight HTTP API
that the Pluto backend calls to execute browser automation tasks.

Uses browser-use library with native Gemini support (ChatGoogle).
"""

import asyncio
import json
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

from browser_use import Agent, Browser, ChatGoogle


# Configuration from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
BROWSER_MODEL = os.getenv("BROWSER_MODEL", "gemini-3.5-flash")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./data/browser_sessions")
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "./data/downloads")
PORT = int(os.getenv("BROWSER_SERVICE_PORT", "9090"))
MAX_STEPS = int(os.getenv("BROWSER_MAX_STEPS", "25"))

# Set the API key for browser-use's ChatGoogle
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


async def run_browser_task(task: str, session_name: str = "default") -> dict:
    """Execute a browser automation task using browser-use with optional persistent session."""

    session_file = os.path.join(SESSIONS_DIR, f"{session_name}_state.json")
    has_session = os.path.exists(session_file)

    headless_env = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    browser = Browser(
        headless=headless_env,
        disable_security=True,
        enable_default_extensions=False,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
        minimum_wait_page_load_time=0.5,
        wait_for_network_idle_page_load_time=1.0,
        wait_between_actions=0.0,
        storage_state=session_file if has_session else None,
    )

    # Configure LLM
    llm = ChatGoogle(model=BROWSER_MODEL)

    try:
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            max_actions_per_step=10,
            use_vision=False,
        )

        history = await agent.run(max_steps=MAX_STEPS)

        # Save updated session state after task completion
        try:
            await browser.export_storage_state(session_file)
        except Exception:
            pass  # Non-critical if export fails

        return {
            "success": history.is_successful(),
            "result": history.final_result() or "",
            "urls_visited": history.urls(),
            "extracted_content": history.extracted_content(),
            "duration_seconds": round(history.total_duration_seconds(), 2),
            "session_saved": True,
            "session_name": session_name,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        try:
            await browser.close()
        except Exception:
            pass


class BrowserServiceHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the browser automation service."""

    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
                task = data.get("task", "")
                session_name = data.get("session_name", "default")

                if not task:
                    self._respond(400, {"error": "No task provided"})
                    return

                # Run the async browser task
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(run_browser_task(task, session_name))
                finally:
                    loop.close()

                self._respond(200, result)

            except json.JSONDecodeError:
                self._respond(400, {"error": "Invalid JSON"})
            except Exception as e:
                self._respond(500, {"error": str(e), "traceback": traceback.format_exc()})
        else:
            self._respond(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/health":
            sessions = []
            if os.path.exists(SESSIONS_DIR):
                sessions = [
                    f.replace("_state.json", "")
                    for f in os.listdir(SESSIONS_DIR)
                    if f.endswith("_state.json")
                ]
            self._respond(200, {
                "status": "ok",
                "service": "pluto-browser-agent",
                "model": BROWSER_MODEL,
                "max_steps": MAX_STEPS,
                "available_sessions": sessions,
            })
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[BrowserService] {args[0]}")


def main():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    server = HTTPServer(("0.0.0.0", PORT), BrowserServiceHandler)
    print(f"[BrowserService] Pluto Browser Automation Service running on port {PORT}")
    print(f"[BrowserService] Model: {BROWSER_MODEL} | Max steps: {MAX_STEPS}")
    print(f"[BrowserService] Sessions directory: {SESSIONS_DIR}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[BrowserService] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
