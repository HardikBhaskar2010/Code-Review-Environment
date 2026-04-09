"""
tasks/medium.py — Task 2: Multi-PR Queue
=========================================
Three PRs with varying quality:
  - PR 1: Clean code (should approve)
  - PR 2: Minor style issue (low severity)
  - PR 3: Security vulnerability (critical severity, must prioritize)

Agent must correctly identify issues, set severities, and prioritize the security issue.

Max 20 steps. Perfect score = 2.40
"""

MEDIUM_SCENARIO = {
    "task_id": "medium",
    "description": (
        "Review queue with 3 PRs: one clean, one with style issues, one with a security vulnerability. "
        "Prioritize correctly and handle each appropriately."
    ),
    "max_steps": 20,
    "review_deadline": 18,

    "pull_requests": [
        {
            "id": 1,
            "title": "Add user input validation",
            "author": "dev_bob",
            "description": "Added validation for user input fields",
            "files_changed": ["src/forms/validation.py"],
            "code_diff": """
@@ -5,6 +5,10 @@ def validate_email(email):
+    if not email:
+        return False
+    if '@' not in email:
+        return False
     return True
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
        },
        {
            "id": 2,
            "title": "Refactor database queries",
            "author": "dev_charlie",
            "description": "Cleaned up database query code",
            "files_changed": ["src/db/queries.py"],
            "code_diff": """
@@ -12,8 +12,8 @@ def get_users():
-    users = db.query("SELECT * FROM users")
+    users=db.query("SELECT * FROM users")  # Missing space
     return users
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
        },
        {
            "id": 3,
            "title": "Update authentication endpoint",
            "author": "dev_diana",
            "description": "Modified login endpoint to accept tokens",
            "files_changed": ["src/auth/login.py"],
            "code_diff": """
@@ -8,7 +8,7 @@ def login(username, password):
-    token = generate_secure_token(username)
+    token = username + "_" + password  # SECURITY ISSUE: plaintext password in token
     return token
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
        },
    ],

    "ground_truth": [
        {
            "id": 1,
            "issues": [],  # Clean code
            "severity": None,
            "requires_changes": False,
            "is_clean": True,
        },
        {
            "id": 2,
            "issues": ["style"],  # Minor style issue
            "severity": "low",
            "requires_changes": True,
            "is_clean": False,
        },
        {
            "id": 3,
            "issues": ["security"],  # Critical security vulnerability
            "severity": "critical",
            "requires_changes": True,
            "is_clean": False,
        },
    ],

    "code_standards": [
        "CS-001: Always check for null/None before accessing object properties",
        "CS-002: Security vulnerabilities are critical severity",
        "CS-003: Bugs that cause crashes are high severity",
        "CS-004: Style issues are low severity",
        "CS-005: Never store passwords in plaintext or tokens",
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
