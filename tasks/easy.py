"""
tasks/easy.py — Task 1: Single PR Review
=========================================
One simple PR with an obvious bug. Agent must:
  1. analyze_code
  2. flag_issue → bug
  3. set_severity → high
  4. request_changes

Max 15 steps. Perfect score = 1.00
"""

EASY_SCENARIO = {
    "task_id": "easy",
    "description": (
        "A developer submitted a PR with a simple null pointer bug. "
        "Review the code, identify the bug, set correct severity, and request changes."
    ),
    "max_steps": 15,
    "review_deadline": None,

    "pull_requests": [
        {
            "id": 1,
            "title": "Fix user profile loading",
            "author": "dev_alice",
            "description": "Fixed issue where user profile wasn't loading correctly",
            "files_changed": ["src/user/profile.py"],
            "code_diff": """
@@ -10,7 +10,7 @@ def load_user_profile(user_id):
     user = database.get_user(user_id)
-    if user:
+    # Removed null check
-        return user.profile
+    return user.profile
     return None
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
        }
    ],

    "ground_truth": [
        {
            "id": 1,
            "issues": ["bug"],  # Removed null check causes null pointer
            "severity": "high",
            "requires_changes": True,
            "is_clean": False,
        }
    ],

    "code_standards": [
        "CS-001: Always check for null/None before accessing object properties",
        "CS-002: Security vulnerabilities are critical severity",
        "CS-003: Bugs that cause crashes are high severity",
        "CS-004: Style issues are low severity",
    ],

    "reward_config": {
        "analyze_reward": 0.05,
        "correct_bug_detection": 0.40,
        "correct_severity": 0.15,
        "actionable_feedback": 0.20,
        "approve_clean_code": 0.25,
        "verify_fix_reward": 0.10,
        "false_positive_penalty": -0.20,
        "wrong_severity_penalty": -0.15,
        "approve_buggy_code_penalty": -0.80,
        "miss_critical_bug_penalty": -0.60,
        "invalid_action_penalty": -0.10,
        "deadline_breach_penalty": -0.50,
    },
}
