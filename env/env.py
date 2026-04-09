"""
env/env.py — CodeReview RL Environment Core
============================================
Simulates a code review system where an AI agent must:
  - Analyze pull requests for bugs, security issues, style violations
  - Flag issues with correct severity
  - Request changes or approve PRs
  - Verify fixes
  - Manage review queues under time constraints

State machine:
  submitted → analyzing → issues_found → changes_requested → re_review → approved
  submitted → analyzing → clean → approved
"""

from __future__ import annotations
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Models (OpenEnv spec compliance)
# ---------------------------------------------------------------------------

class Action(BaseModel):
    """Agent action — what the reviewer does next."""
    action: str = Field(
        ...,
        description="Action type: analyze_code, flag_issue, set_severity, request_changes, approve_pr, verify_fix"
    )
    pr_id: Optional[int] = Field(None, description="Pull request ID to act on")
    value: Optional[str] = Field(None, description="Additional parameter (issue_type, severity, etc.)")


class Observation(BaseModel):
    """Environment observation returned after each step."""
    pull_requests: List[Dict[str, Any]] = Field(default_factory=list)
    step: int = 0
    pending_reviews: int = 0
    review_pressure: float = 0.0
    code_standards: List[str] = Field(default_factory=list)


class Reward(BaseModel):
    """Reward signal with episode termination flag."""
    reward: float = 0.0
    done: bool = False
    info: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Environment
# ---------------------------------------------------------------------------

class CodeReviewEnv:
    """
    CodeReview RL Environment
    
    Manages pull request review workflow with deterministic rewards.
    """

    def __init__(self):
        self.prs: List[Dict[str, Any]] = []
        self.step_count: int = 0
        self.max_steps: int = 20
        self.review_deadline: Optional[int] = None
        self.code_standards: List[str] = []
        self.reward_config: Dict[str, float] = {}
        self.ground_truth: List[Dict[str, Any]] = []
        self.cumulative_reward: float = 0.0

    def reset(self, scenario: Dict[str, Any]) -> Observation:
        """Reset environment with a task scenario."""
        self.prs = [pr.copy() for pr in scenario["pull_requests"]]
        self.step_count = 0
        self.max_steps = scenario["max_steps"]
        self.review_deadline = scenario.get("review_deadline")
        self.code_standards = scenario.get("code_standards", [])
        self.reward_config = scenario["reward_config"]
        self.ground_truth = scenario["ground_truth"]
        self.cumulative_reward = 0.0

        return self._build_observation()

    def step(self, action: Action) -> tuple[Observation, Reward]:
        """Execute one action and return (observation, reward)."""
        self.step_count += 1

        reward_val = 0.0
        done = False
        info: Dict[str, Any] = {}

        # Validate PR exists
        pr = self._get_pr(action.pr_id)
        if pr is None and action.action not in ["analyze_code"]:
            reward_val = self.reward_config.get("invalid_action_penalty", -0.10)
            info["error"] = f"PR {action.pr_id} not found"
            self.cumulative_reward += reward_val
            return self._build_observation(), Reward(reward=reward_val, done=False, info=info)

        # Process action
        if action.action == "analyze_code":
            reward_val, info = self._handle_analyze(action, pr)
        elif action.action == "flag_issue":
            reward_val, info = self._handle_flag_issue(action, pr)
        elif action.action == "set_severity":
            reward_val, info = self._handle_set_severity(action, pr)
        elif action.action == "request_changes":
            reward_val, info = self._handle_request_changes(action, pr)
        elif action.action == "approve_pr":
            reward_val, info = self._handle_approve(action, pr)
        elif action.action == "verify_fix":
            reward_val, info = self._handle_verify_fix(action, pr)
        else:
            reward_val = self.reward_config.get("invalid_action_penalty", -0.10)
            info["error"] = f"Unknown action: {action.action}"

        self.cumulative_reward += reward_val

        # Check termination conditions
        done = self._check_done()

        # Deadline breach penalty
        if self.review_deadline and self.step_count >= self.review_deadline and not done:
            deadline_penalty = self.reward_config.get("deadline_breach_penalty", -0.50)
            reward_val += deadline_penalty
            self.cumulative_reward += deadline_penalty
            info["deadline_breach"] = True
            done = True

        return self._build_observation(), Reward(reward=reward_val, done=done, info=info)

    def state_snapshot(self) -> Dict[str, Any]:
        """Return full environment state for debugging."""
        return {
            "pull_requests": self.prs,
            "step": self.step_count,
            "max_steps": self.max_steps,
            "pending_reviews": sum(1 for pr in self.prs if pr["status"] not in ["approved", "rejected"]),
            "cumulative_reward": self.cumulative_reward,
            "done": self._check_done(),
        }

    # -----------------------------------------------------------------------
    # Action Handlers
    # -----------------------------------------------------------------------

    def _handle_analyze(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Analyze code in a PR."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        if pr["status"] != "submitted":
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "PR already analyzed"}

        pr["status"] = "analyzing"
        pr["analyzed"] = True
        
        # Small reward for starting analysis
        reward = self.reward_config.get("analyze_reward", 0.05)
        return reward, {"message": f"Analyzing PR #{pr['id']}"}

    def _handle_flag_issue(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Flag an issue in the PR."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        if not pr.get("analyzed"):
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "Must analyze before flagging"}

        issue_type = action.value  # e.g., "bug", "security", "style"
        
        # Get ground truth for this PR
        truth = self._get_ground_truth(pr["id"])
        if truth is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No ground truth"}

        # Check if issue type is correct
        if issue_type in truth.get("issues", []):
            reward = self.reward_config.get("correct_bug_detection", 0.40)
            pr["status"] = "issues_found"
            pr.setdefault("flagged_issues", []).append(issue_type)
            return reward, {"message": f"Correctly identified {issue_type}"}
        else:
            # False positive
            reward = self.reward_config.get("false_positive_penalty", -0.20)
            pr.setdefault("flagged_issues", []).append(issue_type)
            return reward, {"error": f"False positive: {issue_type}"}

    def _handle_set_severity(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Set severity for flagged issues."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        if pr["status"] not in ["issues_found", "analyzing"]:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No issues to set severity"}

        severity = action.value  # e.g., "critical", "high", "medium", "low"
        truth = self._get_ground_truth(pr["id"])
        
        if truth and severity == truth.get("severity"):
            reward = self.reward_config.get("correct_severity", 0.15)
            pr["severity"] = severity
            return reward, {"message": f"Correct severity: {severity}"}
        else:
            reward = self.reward_config.get("wrong_severity_penalty", -0.15)
            pr["severity"] = severity
            return reward, {"error": f"Wrong severity: {severity}"}

    def _handle_request_changes(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Request changes on a PR."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        if pr["status"] not in ["issues_found", "analyzing"]:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "Invalid state for requesting changes"}

        truth = self._get_ground_truth(pr["id"])
        
        # Should request changes if there are real issues
        if truth and len(truth.get("issues", [])) > 0:
            reward = self.reward_config.get("actionable_feedback", 0.20)
            pr["status"] = "changes_requested"
            return reward, {"message": "Changes requested"}
        else:
            # Requesting changes on clean code
            reward = self.reward_config.get("false_positive_penalty", -0.20)
            pr["status"] = "changes_requested"
            return reward, {"error": "Requested changes on clean code"}

    def _handle_approve(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Approve a PR."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        truth = self._get_ground_truth(pr["id"])
        
        # Check if PR is clean (no issues)
        if truth and len(truth.get("issues", [])) == 0:
            reward = self.reward_config.get("approve_clean_code", 0.25)
            pr["status"] = "approved"
            return reward, {"message": "Correctly approved clean PR"}
        else:
            # Approving buggy code - critical error
            reward = self.reward_config.get("approve_buggy_code_penalty", -0.80)
            pr["status"] = "approved"
            return reward, {"error": "Approved PR with bugs!"}

    def _handle_verify_fix(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        """Verify that requested changes were fixed."""
        if pr is None:
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No PR specified"}

        if pr["status"] != "changes_requested":
            return self.reward_config.get("invalid_action_penalty", -0.10), {"error": "No changes to verify"}

        # Simulate fix verification (in real scenario, would check updated code)
        pr["status"] = "re_review"
        reward = self.reward_config.get("verify_fix_reward", 0.10)
        return reward, {"message": "Fix verified, ready for re-review"}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _get_pr(self, pr_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Get PR by ID."""
        if pr_id is None:
            return None
        for pr in self.prs:
            if pr["id"] == pr_id:
                return pr
        return None

    def _get_ground_truth(self, pr_id: int) -> Optional[Dict[str, Any]]:
        """Get ground truth for a PR."""
        for truth in self.ground_truth:
            if truth["id"] == pr_id:
                return truth
        return None

    def _build_observation(self) -> Observation:
        """Build observation from current state."""
        pending = sum(1 for pr in self.prs if pr["status"] not in ["approved", "rejected"])
        
        # Calculate review pressure (increases as deadline approaches)
        pressure = 0.0
        if self.review_deadline:
            pressure = min(self.step_count / self.review_deadline, 1.0)

        return Observation(
            pull_requests=self.prs,
            step=self.step_count,
            pending_reviews=pending,
            review_pressure=pressure,
            code_standards=self.code_standards,
        )

    def _check_done(self) -> bool:
        """Check if episode is complete."""
        # Done if all PRs are approved or rejected
        all_reviewed = all(pr["status"] in ["approved", "rejected"] for pr in self.prs)
        
        # Or if max steps reached
        max_steps_reached = self.step_count >= self.max_steps
        
        return all_reviewed or max_steps_reached
