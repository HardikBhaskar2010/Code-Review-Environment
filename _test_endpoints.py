"""Test endpoints via real HTTP requests against running server."""
import httpx
import sys
import time

BASE = "http://localhost:7860"
failures = []

def check(label, cond, detail=""):
    if cond:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} {detail}")
        failures.append(label)

# Wait for server
for _ in range(10):
    try:
        httpx.get(f"{BASE}/health", timeout=2)
        break
    except Exception:
        time.sleep(0.5)

# 1. POST /reset - empty body, no query (what the validator does)
r = httpx.post(f"{BASE}/reset", json={}, timeout=10)
check("POST /reset (empty body, no params) → 200", r.status_code == 200, f"got {r.status_code}")
if r.status_code == 200:
    d = r.json()
    check("  has 'observation'", "observation" in d)
    check("  has 'done'", "done" in d)
    check("  task defaults to 'easy'", d.get("task") == "easy", str(d.get("task")))

# 2. POST /reset?task=hard
r2 = httpx.post(f"{BASE}/reset?task=hard", json={}, timeout=10)
check("POST /reset?task=hard → 200", r2.status_code == 200)
if r2.status_code == 200:
    d2 = r2.json()
    n_prs = len(d2["observation"]["state"]["pull_requests"])
    check(f"  hard task: 5 PRs (got {n_prs})", n_prs == 5)
    check(f"  max_steps=15 (got {d2.get('max_steps')})", d2.get("max_steps") == 15)

# 3. POST /step
httpx.post(f"{BASE}/reset?task=easy", timeout=10)
r3 = httpx.post(f"{BASE}/step", json={"action": "analyze_code", "pr_id": 1, "value": None}, timeout=10)
check("POST /step (analyze_code) → 200", r3.status_code == 200)
if r3.status_code == 200:
    d3 = r3.json()
    check("  reward in [-1,1]", -1.0 <= d3["reward"] <= 1.0, str(d3.get("reward")))
    check("  has 'done'", "done" in d3)

# 4. GET /state (must include ground_truth for grader)
r4 = httpx.get(f"{BASE}/state", timeout=10)
check("GET /state → 200", r4.status_code == 200)
if r4.status_code == 200:
    d4 = r4.json()
    check("  state has 'ground_truth'", "ground_truth" in d4)

# 5. GET /health
r5 = httpx.get(f"{BASE}/health", timeout=10)
check("GET /health → 200", r5.status_code == 200)

# 6. GET /grade
r6 = httpx.get(f"{BASE}/grade?task=easy", timeout=10)
check("GET /grade?task=easy → 200", r6.status_code == 200)
if r6.status_code == 200:
    d6 = r6.json()
    check(f"  score in [0,1] (got {d6.get('score')})", 0.0 <= d6["score"] <= 1.0)

# 7. GET /metadata
r7 = httpx.get(f"{BASE}/metadata", timeout=10)
check("GET /metadata → 200", r7.status_code == 200)

# 8. GET /schema
r8 = httpx.get(f"{BASE}/schema", timeout=10)
check("GET /schema → 200", r8.status_code == 200)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
else:
    print("RESULT: ALL ENDPOINT TESTS PASSED - READY FOR VALIDATOR")
