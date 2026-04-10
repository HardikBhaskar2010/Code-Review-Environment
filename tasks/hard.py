"""
tasks/hard.py — Task 3: Production Incident Cluster
=====================================================
Five PRs submitted during a live production outage.
They share a common root cause (disk-full on the database node)
and form a cascade of dependent failures.

The agent must:
  1. Detect the shared root cause in PR #1 (infra fix)
  2. Prioritize PR #1 BEFORE touching PR #3 or PR #4
  3. Correctly diagnose PR #2 (performance, not critical)
  4. Resolve PR #3 (application crash) AFTER PR #1 is handled
  5. Resolve PR #4 (billing delay) AFTER PR #3 is handled
  6. Approve PR #5 (clean monitoring tweak) — independent

Optimal ordering (highest reward):
  analyze #1 → flag security/bug → request_changes #1
  → analyze #3 → flag bug → request_changes #3
  → analyze #4 → flag bug → request_changes #4
  → analyze #2 → flag bug (performance) → set_severity medium → request_changes #2
  → analyze #5 → approve #5

Wrong ordering (e.g. touching PR #5 or PR #2 before PR #1):
  → ordering penalty applied

MAX_STEPS = 15  (tight — forces real planning, prevents brute-force)
REVIEW_DEADLINE = 12  (SLA: must clear critical PRs within 12 steps)

Perfect score (cumulative reward, normalised to ~1.0):
  analyze×5 × 0.05   = 0.25
  correct_detections  = 0.40 × 3 = 1.20   (PRs 1,3,4 have bugs)
  correct_severities  = 0.15 × 4 = 0.60
  request_changes×4   = 0.20 × 4 = 0.80
  approve_clean×1     = 0.25
  ordering_bonus      = 0.20
  ----------------------------------
  Total ≈ 3.30  →  normalised to 1.0

Baseline (GPT-4 greedy, wrong ordering): ~0.30–0.40
"""

HARD_SCENARIO = {
    "task_id": "hard",
    "description": (
        "PRODUCTION OUTAGE in progress. Five PRs landed simultaneously during "
        "a disk-full incident on the database node. "
        "PR #1 is the root-cause fix (delete orphaned temp files); "
        "PR #2 causes slow dashboard queries (performance, root: disk I/O); "
        "PR #3 makes the login service throw 500s (bug, blocked by PR #1 fix); "
        "PR #4 delays billing notifications (bug, cascades from PR #3); "
        "PR #5 is an unrelated monitoring config tweak (clean). "
        "You must identify the root cause, prioritize infra first, and resolve "
        "the cascade in correct dependency order under SLA pressure."
    ),
    "max_steps": 15,
    "review_deadline": 12,   # SLA hard deadline — breach = -0.50

    "pull_requests": [
        {
            "id": 1,
            "title": "[INFRA] Remove orphaned temp files clogging /var/db",
            "author":      "ops_alice",
            "description": (
                "Emergency patch: disk usage at 98%. Script purges /var/db/tmp "
                "but also deletes active WAL (write-ahead-log) files — "
                "data loss risk."
            ),
            "files_changed": ["ops/cleanup.sh"],
            "code_diff": """\
@@ -12,6 +12,10 @@ purge_temp() {
-    find /var/db/tmp -mtime +7 -delete
+    find /var/db/ -name "*.tmp" -delete   # BUG: also matches active WAL *.tmp files
+    echo "Disk freed: $(df -h /var/db | tail -1)"
 }
""",
            "status":         "submitted",
            "analyzed":       False,
            "flagged_issues": [],
            "severity":       None,
            "dependencies":   [],
        },
        {
            "id": 2,
            "title": "Optimise dashboard aggregate query",
            "author":      "dev_bob",
            "description": (
                "Dashboard P99 latency spiked to 8 s. Added index hint and "
                "reduced result window — performance improvement."
            ),
            "files_changed": ["api/dashboard.py"],
            "code_diff": """\
@@ -34,7 +34,7 @@ def get_dashboard_stats(org_id):
-    rows = db.execute("SELECT * FROM events WHERE org_id=?", [org_id])
+    rows = db.execute(
+        "SELECT /*+ INDEX(events idx_org_ts) */ * FROM events "
+        "WHERE org_id=? ORDER BY ts DESC LIMIT 500",   # perf issue: missing pagination
+        [org_id])
     return aggregate(rows)
""",
            "status":         "submitted",
            "analyzed":       False,
            "flagged_issues": [],
            "severity":       None,
            "dependencies":   [],   # independent — but medium-priority perf issue
        },
        {
            "id": 3,
            "title": "Fix login service 500 errors",
            "author":      "dev_carol",
            "description": (
                "Login service throwing HTTP 500 when reading user session tokens. "
                "Root cause: session store path on the full disk is unwritable — "
                "must wait for disk fix (PR #1) before this can ship safely."
            ),
            "files_changed": ["auth/session.py"],
            "code_diff": """\
@@ -8,7 +8,7 @@ def create_session(user_id):
-    path = SESSION_DIR + user_id + ".tok"
+    path = "/tmp/" + user_id + ".tok"   # BUG: /tmp also on same disk; race condition
     with open(path, "w") as f:
         f.write(generate_token(user_id))
""",
            "status":         "submitted",
            "analyzed":       False,
            "flagged_issues": [],
            "severity":       None,
            "dependencies":   [1],  # depends on PR #1 (disk fix)
        },
        {
            "id": 4,
            "title": "Retry billing notification on transient failures",
            "author":      "dev_dan",
            "description": (
                "Billing notifications silently dropping when session lookup fails. "
                "Added naive retry — but swallows exception on third failure."
            ),
            "files_changed": ["billing/notify.py"],
            "code_diff": """\
@@ -15,6 +15,12 @@ def send_billing_notice(user_id, amount):
+    for attempt in range(3):
+        try:
+            session = get_session(user_id)   # calls PR #3 code
+            dispatch(session, amount)
+            return
+        except Exception:
+            pass   # BUG: silently swallows all errors on final attempt
+    # No fallback — billing notification lost
""",
            "status":         "submitted",
            "analyzed":       False,
            "flagged_issues": [],
            "severity":       None,
            "dependencies":   [3],  # depends on PR #3 (session fix)
        },
        {
            "id": 5,
            "title": "Tune disk-full alert threshold from 90% → 85%",
            "author":      "ops_eve",
            "description": (
                "Monitoring: lower disk alert trigger to 85 % so ops gets "
                "earlier warning. Clean config change."
            ),
            "files_changed": ["monitoring/alerts.yaml"],
            "code_diff": """\
@@ -3,3 +3,3 @@ disk_alert:
-  threshold_pct: 90
+  threshold_pct: 85
   channel: "#ops-alerts"
""",
            "status":         "submitted",
            "analyzed":       False,
            "flagged_issues": [],
            "severity":       None,
            "dependencies":   [],   # independent, clean
        },
    ],

    "ground_truth": [
        {
            "id": 1,
            "issues":           ["bug"],        # deletes active WAL files → data loss
            "severity":         "critical",
            "requires_changes": True,
            "is_clean":         False,
            "priority":         1,              # must be handled FIRST
            "blocks":           [3],
        },
        {
            "id": 2,
            "issues":           ["bug"],        # missing pagination → memory OOM
            "severity":         "medium",
            "requires_changes": True,
            "is_clean":         False,
            "priority":         3,              # handle after infra
        },
        {
            "id": 3,
            "issues":           ["bug"],        # race condition on /tmp
            "severity":         "high",
            "requires_changes": True,
            "is_clean":         False,
            "priority":         2,              # after PR #1
            "blocked_by":       [1],
            "blocks":           [4],
        },
        {
            "id": 4,
            "issues":           ["bug"],        # silent exception swallow
            "severity":         "high",
            "requires_changes": True,
            "is_clean":         False,
            "priority":         2,              # after PR #3
            "blocked_by":       [3],
        },
        {
            "id": 5,
            "issues":           [],             # clean
            "severity":         None,
            "requires_changes": False,
            "is_clean":         True,
            "priority":         4,              # handle last
        },
    ],

    "code_standards": [
        "CS-001: Never delete files with overly broad glob patterns (data loss risk)",
        "CS-002: Critical severity = data loss, security breach, or service outage",
        "CS-003: High severity = significant functionality broken",
        "CS-004: Medium severity = performance degradation or partial breakage",
        "CS-005: Low / style severity = readability or minor inefficiency",
        "CS-006: Always resolve blocking infra PRs before dependent app PRs",
        "CS-007: Never silently swallow exceptions without fallback or alert",
        "CS-008: DB queries touching large tables must have LIMIT / pagination",
        "CS-009: Resolve PRs in dependency order: blocker → blocked",
        "CS-010: Prioritize by severity: critical → high → medium → low",
    ],

    "reward_config": {
        # Per-action rewards
        "analyze_reward":           0.05,
        "correct_bug_detection":    0.40,
        "correct_severity":         0.15,
        "actionable_feedback":      0.20,
        "approve_clean_code":       0.25,
        "verify_fix_reward":        0.10,
        # Penalties
        "false_positive_penalty":  -0.20,
        "wrong_severity_penalty":  -0.15,
        "approve_buggy_code_penalty": -0.80,
        "miss_critical_bug_penalty":  -0.60,
        "invalid_action_penalty":     -0.10,
        "deadline_breach_penalty":    -0.50,
        "sla_delay_penalty":          -0.20,
        # Trajectory bonuses (awarded once per episode)
        "optimal_ordering_bonus":   0.20,
        "wrong_ordering_penalty":  -0.25,
    },
}
