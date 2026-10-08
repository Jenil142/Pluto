"""
Pluto Session Manager
Runs on the HOST machine to let you manually log into websites
and save the authenticated browser session for Pluto's Docker agent to reuse.

Usage:
    python -m pluto.tools.session_manager login <session_name>
    python -m pluto.tools.session_manager list
    python -m pluto.tools.session_manager delete <session_name>
"""

import asyncio
import os
import sys
import json

# Session storage path (shared with Docker via volume mount)
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "browser_sessions")


async def login_session(session_name: str):
    """Open a visible browser window for manual login, then save the session state."""
    from playwright.async_api import async_playwright
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    session_file = os.path.join(SESSIONS_DIR, f"{session_name}_state.json")
    
    print(f"[SessionManager] Opening browser for '{session_name}' session...")
    print(f"[SessionManager] Log in to your desired website(s), then close the browser window.")
    print(f"[SessionManager] Your session will be saved automatically.\n")
    
    async with async_playwright() as p:
        # Load existing session if available
        context_args = {"headless": False}
        if os.path.exists(session_file):
            print(f"[SessionManager] Loading existing session from: {session_file}")
            context_args["storage_state"] = session_file
        
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=session_file if os.path.exists(session_file) else None
        )
        
        page = await context.new_page()
        await page.goto("https://www.google.com")
        
        print("[SessionManager] Browser is open. Navigate to your target site and log in.")
        print("[SessionManager] When done, close the browser window to save the session.\n")
        
        # Wait for the browser to be closed by the user
        try:
            await page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        
        # If context is still alive, try to save state
        try:
            await context.storage_state(path=session_file)
            print(f"\n[SessionManager] Session '{session_name}' saved to: {session_file}")
        except Exception:
            # Browser was fully closed, try saving from any remaining pages
            print(f"\n[SessionManager] Browser closed. Attempting to save session...")
            try:
                await context.storage_state(path=session_file)
                print(f"[SessionManager] Session '{session_name}' saved successfully.")
            except Exception as e:
                print(f"[SessionManager] Could not save session: {e}")
        
        try:
            await browser.close()
        except Exception:
            pass


def list_sessions():
    """List all saved browser sessions."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sessions = [f.replace("_state.json", "") for f in os.listdir(SESSIONS_DIR) if f.endswith("_state.json")]
    
    if not sessions:
        print("[SessionManager] No saved sessions found.")
        return
    
    print("[SessionManager] Saved sessions:")
    for name in sorted(sessions):
        session_file = os.path.join(SESSIONS_DIR, f"{name}_state.json")
        size = os.path.getsize(session_file)
        print(f"  - {name} ({size} bytes)")


def delete_session(session_name: str):
    """Delete a saved browser session."""
    session_file = os.path.join(SESSIONS_DIR, f"{session_name}_state.json")
    if os.path.exists(session_file):
        os.remove(session_file)
        print(f"[SessionManager] Session '{session_name}' deleted.")
    else:
        print(f"[SessionManager] Session '{session_name}' not found.")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m pluto.tools.session_manager login <session_name>")
        print("  python -m pluto.tools.session_manager list")
        print("  python -m pluto.tools.session_manager delete <session_name>")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "login":
        if len(sys.argv) < 3:
            print("Error: Please provide a session name (e.g., 'github', 'whatsapp', 'gmail')")
            sys.exit(1)
        session_name = sys.argv[2]
        asyncio.run(login_session(session_name))
    
    elif action == "list":
        list_sessions()
    
    elif action == "delete":
        if len(sys.argv) < 3:
            print("Error: Please provide a session name to delete.")
            sys.exit(1)
        delete_session(sys.argv[2])
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
