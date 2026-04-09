"""
tasks/hard.py — Task 3: Dependency Chain with Security Issue
=============================================================
Four PRs with dependencies:
  - PR 1: Base library update (has security vulnerability)
  - PR 2: Feature using PR 1 (depends on PR 1)
  - PR 3: Another feature using PR 1 (depends on PR 1)
  - PR 4: Clean refactoring (independent)

Agent must:
  1. Identify security vulnerability in PR 1
  2. Block/request changes on PR 1
  3. Recognize that PR 2 and PR 3 depend on PR 1 and should wait
  4. Approve PR 4 (independent and clean)
  5. Handle under time pressure (review deadline)

Max 25 steps. Perfect score = 3.50
"""

HARD_SCENARIO = {
    "task_id": "hard",
    "description": (
        "Complex review scenario: 4 PRs with dependencies. "
        "PR 1 has a security vulnerability that blocks dependent PRs 2 and 3. "
        "PR 4 is independent and clean. Must prioritize security issue and manage dependencies."
    ),
    "max_steps": 25,
    "review_deadline": 22,

    "pull_requests": [
        {
            "id": 1,
            "title": "Update crypto library to v2.0",
            "author": "dev_eve",
            "description": "Updated encryption library to latest version",
            "files_changed": ["src/lib/crypto.py"],
            "code_diff": """
@@ -3,7 +3,7 @@ import hashlib
 def encrypt_data(data, key):
-    return hashlib.sha256(data + key).hexdigest()
+    return hashlib.md5(data + key).hexdigest()  # SECURITY: MD5 is broken
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
            "dependencies": [],
        },
        {
            "id": 2,
            "title": "Add encrypted user data storage",
            "author": "dev_frank",
            "description": "Store user data with encryption using updated crypto lib",
            "files_changed": ["src/storage/user_data.py"],
            "code_diff": """
@@ -1,5 +1,6 @@
+from lib.crypto import encrypt_data  # Depends on PR 1
 def store_user_data(user_id, data):
+    encrypted = encrypt_data(data, user_id)
     database.save(user_id, encrypted)
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
            "dependencies": [1],  # Depends on PR 1
        },
        {
            "id": 3,
            "title": "Encrypt API tokens",
            "author": "dev_grace",
            "description": "Use new crypto lib to encrypt API tokens",
            "files_changed": ["src/auth/tokens.py"],
            "code_diff": """
@@ -1,5 +1,6 @@
+from lib.crypto import encrypt_data  # Depends on PR 1
 def generate_token(user_id):
+    token = encrypt_data(user_id, SECRET_KEY)
     return token
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
            "dependencies": [1],  # Depends on PR 1
        },
        {
            "id": 4,
            "title": "Refactor logging module",
            "author": "dev_henry",
            "description": "Cleaned up logging code for better readability",
            "files_changed": ["src/utils/logger.py"],
            "code_diff": """
@@ -10,10 +10,8 @@ def log_message(level, message):
-    if level == "ERROR":
-        print(f"ERROR: {message}")
-    elif level == "INFO":
-        print(f"INFO: {message}")
+    # Cleaner implementation
+    print(f"{level}: {message}")
""",
            "status": "submitted",
            "analyzed": False,
            "flagged_issues": [],
            "severity": None,
            "dependencies": [],  # Independent
        },
    ],

    "ground_truth": [
        {
            "id": 1,
            "issues": ["security"],  # MD5 is cryptographically broken
            "severity": "critical",
            "requires_changes": True,
            "is_clean": False,
            "blocks": [2, 3],  # Blocks dependent PRs
        },
        {
            "id": 2,
            "issues": [],  # Code is fine, but blocked by PR 1
            "severity": None,
            "requires_changes": False,
            "is_clean": True,
            "blocked_by": [1],
        },
        {
            "id": 3,
            "issues": [],  # Code is fine, but blocked by PR 1
            "severity": None,
            "requires_changes": False,
            "is_clean": True,
            "blocked_by": [1],
        },
        {
            "id": 4,
            "issues": [],  # Clean refactoring
            "severity": None,
            "requires_changes": False,
            "is_clean": True,
        },
    ],

    "code_standards": [
        "CS-001: Always check for null/None before accessing object properties",
        "CS-002: Security vulnerabilities are critical severity",
        "CS-003: Bugs that cause crashes are high severity",
        "CS-004: Style issues are low severity",
        "CS-005: Never store passwords in plaintext or tokens",
        "CS-006: MD5 and SHA1 are deprecated for cryptographic use",
        "CS-007: Block dependent PRs if base PR has critical issues",
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
