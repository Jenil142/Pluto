"""
Pluto Browser Automation Tool
Dispatches web automation tasks to the Dockerized browser agent service.
"""

import os
import json
import urllib.request
import urllib.error
from google.genai import types


BROWSER_SERVICE_URL = os.getenv("BROWSER_SERVICE_URL", "http://localhost:9090")


def execute_browser_task(task: str, session_name: str = "default", **kwargs) -> dict:
    """
    Execute a web browser automation task via the Dockerized browser agent.
    
    Args:
        task: Natural language description of the browser task to perform.
        session_name: Name of the saved authentication session to use (e.g., 'github', 'gmail').
    
    Returns:
        dict with 'success', 'result' or 'error' keys.
    """
    
    if not task.strip():
        return {
            "success": False,
            "error": "No task description provided.",
        }
    
    endpoint = f"{BROWSER_SERVICE_URL}/execute"
    payload = json.dumps({
        "task": task.strip(),
        "session_name": session_name,
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        # Long timeout: browser tasks can take minutes
        with urllib.request.urlopen(req, timeout=None) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
            
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Cannot reach browser agent at {BROWSER_SERVICE_URL}. Is the Docker container running? ({e})",
            "hint": "Run: docker compose up -d pluto-browser",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Browser task dispatch failed: {e}",
        }


def list_browser_sessions(**kwargs) -> dict:
    """List all available authenticated browser sessions."""
    
    endpoint = f"{BROWSER_SERVICE_URL}/health"
    
    try:
        req = urllib.request.Request(endpoint, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sessions = data.get("available_sessions", [])
            if sessions:
                return {
                    "sessions": sessions,
                    "count": len(sessions),
                    "hint": "Use session_name parameter to specify which authenticated session to use.",
                }
            else:
                return {
                    "sessions": [],
                    "count": 0,
                    "hint": "No sessions found. Run: python -m pluto.tools.session_manager login <name>",
                }
    except Exception as e:
        return {
            "error": f"Cannot reach browser agent: {e}",
            "hint": "Run: docker compose up -d pluto-browser",
        }


# --- Gemini Tool Declarations ---

browser_task_declaration = types.FunctionDeclaration(
    name="execute_browser_task",
    description=(
        "Execute a web browser automation task. Pluto will control a real Chromium browser "
        "to navigate websites, click buttons, fill forms, extract data, and perform complex "
        "web interactions. Use saved authentication sessions to access logged-in accounts. "
        "Use this tool when the user asks you to do something on a website, automate a web task, "
        "check a web dashboard, or interact with any web application."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "task": types.Schema(
                type="STRING",
                description=(
                    "A clear, natural language description of the browser task to perform. "
                    "Be specific about the target website, what actions to take, and what data to extract. "
                    "Example: 'Go to github.com/browser-use/browser-use and star the repository'"
                ),
            ),
            "session_name": types.Schema(
                type="STRING",
                description=(
                    "The name of the saved authentication session to use for this task. "
                    "Use 'default' for unauthenticated browsing, or a specific name like "
                    "'github', 'gmail', 'whatsapp' for pre-authenticated sessions."
                ),
            ),
        },
        required=["task"],
    ),
)

list_sessions_declaration = types.FunctionDeclaration(
    name="list_browser_sessions",
    description=(
        "List all available authenticated browser sessions. Use this to check which "
        "website logins are available before executing a browser task."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)
