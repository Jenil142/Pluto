"""
Live Server Lifecycle and Verification Script for Pluto Backend API.
Path: /home/jenil/Pluto/tests/verify_api_live.py

Launches Uvicorn subprocess, executes live HTTP checks, validates CORS, and terminates cleanly.
"""

import sys
import time
import socket
import urllib.request
import urllib.error
import json
import subprocess
import os
import signal

PYTHON_BIN = sys.executable
BASE_URL = "http://127.0.0.1:8000"
SERVER_CMD = [PYTHON_BIN, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"]


def is_port_in_use(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{BASE_URL}/api/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def run_verification():
    print("[1/5] Checking if port 8000 is free...")
    if is_port_in_use(8000):
        print("ERROR: Port 8000 is already in use before starting server.")
        return False
    print("Port 8000 is free.")

    print("[2/5] Starting Uvicorn server on port 8000...")
    proc = subprocess.Popen(
        SERVER_CMD,
        cwd="/home/jenil/Pluto",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )

    try:
        ready = wait_for_server(timeout=10.0)
        if not ready:
            print("ERROR: Server failed to start and respond on port 8000 within 10 seconds.")
            if proc.poll() is not None:
                _, stderr = proc.communicate()
                print("Server process exited with stderr:")
                print(stderr.decode("utf-8", errors="replace"))
            return False
        print("Server is listening on port 8000.")

        # Test Health Endpoint
        print("[3/5] Testing GET /api/health...")
        req = urllib.request.Request(
            f"{BASE_URL}/api/health",
            headers={"Origin": "http://localhost:5173"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            status_code = resp.status
            body = json.loads(resp.read().decode("utf-8"))
            cors_header = resp.headers.get("Access-Control-Allow-Origin")

            assert status_code == 200, f"Expected status 200, got {status_code}"
            assert body.get("status") == "ok", f"Expected status 'ok', got {body.get('status')}"
            assert body.get("service") == "pluto-api", f"Expected service 'pluto-api', got {body.get('service')}"
            assert cors_header in ["http://localhost:5173", "*"], f"Invalid CORS header: {cors_header}"
            print(f"Health check PASSED: {body}")
            print(f"CORS header verified: Access-Control-Allow-Origin: {cors_header}")

        # Test Chat Endpoint
        print("[4/5] Testing POST /api/chat...")
        chat_payload = json.dumps({"message": "Hello Pluto, live verification check"}).encode("utf-8")
        req_chat = urllib.request.Request(
            f"{BASE_URL}/api/chat",
            data=chat_payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173"
            },
            method="POST"
        )
        with urllib.request.urlopen(req_chat, timeout=25.0) as resp:
            status_code = resp.status
            body = json.loads(resp.read().decode("utf-8"))
            assert status_code == 200, f"Expected status 200, got {status_code}"
            assert "reply" in body, f"Missing 'reply' key in {body}"
            assert isinstance(body["reply"], str) and len(body["reply"]) > 0, "Empty reply string"
            assert body.get("state") == "idle", f"Expected state 'idle', got {body.get('state')}"
            print(f"Chat check PASSED: reply='{body['reply']}', state='{body['state']}'")

        # Test CORS Preflight
        print("[4b/5] Testing CORS Preflight OPTIONS /api/chat...")
        req_opt = urllib.request.Request(
            f"{BASE_URL}/api/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            },
            method="OPTIONS"
        )
        with urllib.request.urlopen(req_opt, timeout=3.0) as resp:
            assert resp.status == 200, f"OPTIONS failed with status {resp.status}"
            allow_origin = resp.headers.get("Access-Control-Allow-Origin")
            assert allow_origin in ["http://localhost:5173", "*"], f"OPTIONS bad allow origin: {allow_origin}"
            allow_methods = resp.headers.get("Access-Control-Allow-Methods", "")
            assert "POST" in allow_methods, f"OPTIONS missing POST in allow methods: {allow_methods}"
            print("CORS preflight PASSED.")

        return True

    finally:
        print("[5/5] Testing process cleanup and port release...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3.0)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

        time.sleep(0.5)
        if is_port_in_use(8000):
            print("ERROR: Port 8000 was NOT released after process termination.")
            port_clean = False
        else:
            print("Port 8000 successfully released. Cleanup verified.")
            port_clean = True

    return port_clean


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
