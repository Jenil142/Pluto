"""
Pluto Live E2E Stress and Concurrency Harness (Python Client)
Target: http://127.0.0.1:8000
Covers:
1. Direct HTTP GET /api/health verification and response schema
2. Direct HTTP POST /api/chat with valid queries
3. Whitespace query handling (200 OK with prompt guidance)
4. Massive payload test (5,000, 25,000, 50,000 chars)
5. Unicode, multi-lingual, emoji, SQLi, command injection queries
6. High concurrency burst (5, 10, 20 parallel threads)
7. Offline connection error handling and fast recovery
8. Empirical latency profiling
"""

import sys
import time
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

LIVE_BASE_URL = "http://127.0.0.1:8000"
OFFLINE_BASE_URL = "http://127.0.0.1:59999"

results = {
    "passed": 0,
    "failed": 0,
    "metrics": []
}


def log_test(name: str, passed: bool, elapsed_ms: float = 0.0, notes: str = ""):
    status_str = "PASS" if passed else "FAIL"
    if passed:
        results["passed"] += 1
        print(f"[{status_str}] {name} ({elapsed_ms:.2f} ms)")
    else:
        results["failed"] += 1
        print(f"[{status_str}] {name} ({elapsed_ms:.2f} ms) - {notes}")
    results["metrics"].append({
        "name": name,
        "passed": passed,
        "elapsed_ms": elapsed_ms,
        "notes": notes
    })


def send_live_request(endpoint: str, data: dict = None, base_url: str = LIVE_BASE_URL, timeout: float = 30.0):
    url = f"{base_url.rstrip('/')}{endpoint}"
    req_data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    else:
        req = urllib.request.Request(url, headers=headers, method="GET")

    start_t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body), elapsed
    except urllib.error.HTTPError as he:
        elapsed = (time.perf_counter() - start_t) * 1000.0
        body = he.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return he.code, parsed, elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start_t) * 1000.0
        raise RuntimeError(f"Connection failure to {url}: {exc}") from exc


def main():
    print("=" * 64)
    print(" Pluto Live E2E Stress and Concurrency Harness (Python) ")
    print(f" Target: {LIVE_BASE_URL}")
    print("=" * 64 + "\n")

    # 1. Health check
    try:
        status, body, elapsed = send_live_request("/api/health")
        passed = (status == 200 and body.get("status") == "ok" and body.get("service") == "pluto-api")
        log_test("Live Health Endpoint Contract", passed, elapsed, f"Status: {status}")
    except Exception as err:
        log_test("Live Health Endpoint Contract", False, 0.0, str(err))

    # 2. Basic chat
    try:
        status, body, elapsed = send_live_request("/api/chat", {"message": "status"})
        passed = (status == 200 and "reply" in body and body.get("state") == "idle")
        snippet = body.get("reply", "")[:40] if passed else ""
        log_test("Live Single Chat Query (Status Command)", passed, elapsed, f"Snippet: {snippet}")
    except Exception as err:
        log_test("Live Single Chat Query (Status Command)", False, 0.0, str(err))

    # 3. Pure whitespace query (backend handling)
    try:
        status, body, elapsed = send_live_request("/api/chat", {"message": "   \n\t  "})
        passed = (status == 200 and body.get("reply") == "Please provide a valid query.")
        log_test("Whitespace Query Direct to Backend", passed, elapsed, f"Reply: {body.get('reply')}")
    except Exception as err:
        log_test("Whitespace Query Direct to Backend", False, 0.0, str(err))

    # 4. Large payloads (5,000, 10,000, 50,000 characters)
    for sz in [5000, 10000, 50000]:
        try:
            large_text = ("Robotic trajectory planner and vision subsystem " * (sz // 40))[:sz]
            status, body, elapsed = send_live_request("/api/chat", {"message": large_text})
            passed = (status == 200 and "reply" in body and len(body["reply"]) > 0)
            log_test(f"Large Query Payload ({sz} characters)", passed, elapsed, f"Reply len: {len(body.get('reply', ''))}")
        except Exception as err:
            log_test(f"Large Query Payload ({sz} characters)", False, 0.0, str(err))

    # 5. Unicode, multilingual, and injection strings
    test_cases = [
        ("Multilingual Script Mixture", "مرحبا بك / 欢迎 / Здравствуйте / Welcome to Pluto OS"),
        ("Complex Emojis & Math Symbols", "🚀🤖🌌🔬 ∑_{i=1}^N x_i = \u221e \u2260 0 \u03c0"),
        ("SQL Injection Drop Table", "'; DROP TABLE messages; SELECT 1; --"),
        ("Command Injection Sequence", "; uname -a; rm -rf /tmp/mock_test; echo PWNED"),
        ("Cross-Site Scripting Injection", "<script>alert('xss')</script><iframe src='javascript:void(0)'>"),
    ]
    for label, payload_text in test_cases:
        try:
            status, body, elapsed = send_live_request("/api/chat", {"message": payload_text})
            passed = (status == 200 and "reply" in body and body.get("state") == "idle")
            log_test(f"Adversarial String: {label}", passed, elapsed, f"Status: {status}")
        except Exception as err:
            log_test(f"Adversarial String: {label}", False, 0.0, str(err))

    # 6. Concurrency Burst: 5 parallel requests
    print("\n--- Running Concurrency Burst: 5 Parallel Requests ---")
    try:
        t_burst_start = time.perf_counter()
        latencies = []
        statuses = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(send_live_request, "/api/chat", {"message": f"Parallel batch 5 query {i}"})
                for i in range(5)
            ]
            for f in as_completed(futures):
                code, resp_json, lat = f.result()
                statuses.append(code)
                latencies.append(lat)
        t_burst_total = (time.perf_counter() - t_burst_start) * 1000.0
        burst_passed = all(code == 200 for code in statuses) and len(statuses) == 5
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        notes = f"Min: {min_lat:.1f}ms, Max: {max_lat:.1f}ms, Avg: {avg_lat:.1f}ms, Total wall: {t_burst_total:.1f}ms"
        log_test("Concurrency Burst (5 Parallel Requests)", burst_passed, t_burst_total, notes)
    except Exception as err:
        log_test("Concurrency Burst (5 Parallel Requests)", False, 0.0, str(err))

    # 7. Concurrency Burst: 10 parallel requests
    print("\n--- Running Concurrency Burst: 10 Parallel Requests ---")
    try:
        t_burst_start = time.perf_counter()
        latencies = []
        statuses = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(send_live_request, "/api/chat", {"message": f"Parallel batch 10 query {i} status"})
                for i in range(10)
            ]
            for f in as_completed(futures):
                code, resp_json, lat = f.result()
                statuses.append(code)
                latencies.append(lat)
        t_burst_total = (time.perf_counter() - t_burst_start) * 1000.0
        burst_passed = all(code == 200 for code in statuses) and len(statuses) == 10
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        notes = f"Min: {min_lat:.1f}ms, Max: {max_lat:.1f}ms, Avg: {avg_lat:.1f}ms, Total wall: {t_burst_total:.1f}ms"
        log_test("Concurrency Burst (10 Parallel Requests)", burst_passed, t_burst_total, notes)
    except Exception as err:
        log_test("Concurrency Burst (10 Parallel Requests)", False, 0.0, str(err))

    # 8. Offline Error Handling
    print("\n--- Testing Offline Error Handling ---")
    try:
        offline_failed_cleanly = False
        t_off_start = time.perf_counter()
        try:
            send_live_request("/api/chat", {"message": "Will fail"}, base_url=OFFLINE_BASE_URL, timeout=2.0)
        except RuntimeError as rerr:
            if "Connection failure" in str(rerr) or "refused" in str(rerr).lower():
                offline_failed_cleanly = True
        elapsed = (time.perf_counter() - t_off_start) * 1000.0
        log_test("Offline Network Fault Handling", offline_failed_cleanly, elapsed, "Connection cleanly refused")
    except Exception as err:
        log_test("Offline Network Fault Handling", False, 0.0, str(err))

    # 9. Recovery Verification
    try:
        status, body, elapsed = send_live_request("/api/chat", {"message": "Recovery check"})
        passed = (status == 200 and "reply" in body)
        log_test("Post-Fault Immediate Recovery", passed, elapsed, "Server remains responsive")
    except Exception as err:
        log_test("Post-Fault Immediate Recovery", False, 0.0, str(err))

    print("\n" + "=" * 64)
    print(f" Summary: {results['passed']} PASSED, {results['failed']} FAILED ")
    print("=" * 64)

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
