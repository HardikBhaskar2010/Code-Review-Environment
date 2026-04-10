"""
env/env.py — CodeReview RL Environment Core
============================================
Simulates a code review system where an AI agent must:
  - Analyze pull requests for bugs, security issues, style violations
  - Flag issues with correct severity
  - Request changes or approve PRs
  - Verify fixes and manage review queues under time constraints
  - Handle PR dependencies (blocked / unblock chains)

State machine per PR:
  submitted → analyzing → issues_found → changes_requested → re_review → approved
  submitted → analyzing → approved  (clean code)

Episode terminates when:
  - All PRs reach terminal state (approved / changes_requested)
  - Step budget exhausted (step_count >= max_steps)
  - SLA hard deadline breached (step_count > review_deadline)
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
        description=(
            "Action type: analyze_code | flag_issue | set_severity | "
            "request_changes | approve_pr | verify_fix"
        )
    )
    pr_id: Optional[int] = Field(None, description="Pull request ID to act on")
    value: Optional[str]  = Field(None, description="Additional parameter (issue_type, severity, etc.)")


class Observation(BaseModel):
    """Environment observation returned after each step."""
    pull_requests:    List[Dict[str, Any]] = Field(default_factory=list)
    step:             int   = 0
    steps_remaining:  int   = 0          # explicit budget signal
    pending_reviews:  int   = 0
    review_pressure:  float = 0.0
    code_standards:   List[str] = Field(default_factory=list)
    cumulative_reward: float = 0.0


class Reward(BaseModel):
    """Reward signal with episode termination flag."""
    reward: float = 0.0
    done:   bool  = False
    info:   Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Environment
# ---------------------------------------------------------------------------

VALID_ACTIONS = {
    "analyze_code", "flag_issue", "set_severity",
    "request_changes", "approve_pr", "verify_fix",
}

TERMINAL_STATES = {"approved", "changes_requested", "rejected"}


class CodeReviewEnv:
    """
    CodeReview RL Environment

    Deterministic, reproducible rewards. Given the same initial state and
    action sequence, always produces identical transitions and scores.
    """

    def __init__(self) -> None:
        self.prs:              List[Dict[str, Any]] = []
        self.step_count:       int   = 0
        self.max_steps:        int   = 20
        self.review_deadline:  Optional[int] = None
        self.code_standards:   List[str] = []
        self.reward_config:    Dict[str, float] = {}
        self.ground_truth:     List[Dict[str, Any]] = []
        self.cumulative_reward: float = 0.0
        self._ordering_bonus_paid: bool = False   # one-time bonus tracker
        self._sla_penalty_paid:    bool = False   # avoid double-penalising

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def reset(self, scenario: Dict[str, Any]) -> Observation:
        """Reset environment with a task scenario."""
        self.prs               = [pr.copy() for pr in scenario["pull_requests"]]
        self.step_count        = 0
        self.max_steps         = scenario["max_steps"]
        self.review_deadline   = scenario.get("review_deadline")
        self.code_standards    = scenario.get("code_standards", [])
        self.reward_config     = scenario["reward_config"]
        self.ground_truth      = scenario["ground_truth"]
        self.cumulative_reward = 0.0
        self._ordering_bonus_paid = False
        self._sla_penalty_paid    = False
        return self._build_observation()

    def step(self, action: Action) -> tuple[Observation, Reward]:
        """Execute one action and return (observation, reward)."""
        self.step_count += 1

        reward_val = 0.0
        done       = False
        info: Dict[str, Any] = {}

        # ── Unknown action ──────────────────────────────────────────────────
        if action.action not in VALID_ACTIONS:
            reward_val = self._penalty("invalid_action_penalty")
            info["error"] = f"Unknown action: {action.action!r}"
            self._accumulate(reward_val)
            return self._build_observation(), Reward(reward=reward_val, done=False, info=info)

        # ── Validate PR exists ──────────────────────────────────────────────
        pr = self._get_pr(action.pr_id)
        if pr is None and action.action != "analyze_code":
            reward_val = self._penalty("invalid_action_penalty")
            info["error"] = f"PR {action.pr_id} not found"
            self._accumulate(reward_val)
            return self._build_observation(), Reward(reward=reward_val, done=False, info=info)

        # ── Dispatch ────────────────────────────────────────────────────────
        if   action.action == "analyze_code":      reward_val, info = self._handle_analyze(action, pr)
        elif action.action == "flag_issue":         reward_val, info = self._handle_flag_issue(action, pr)
        elif action.action == "set_severity":       reward_val, info = self._handle_set_severity(action, pr)
        elif action.action == "request_changes":    reward_val, info = self._handle_request_changes(action, pr)
        elif action.action == "approve_pr":         reward_val, info = self._handle_approve(action, pr)
        elif action.action == "verify_fix":         reward_val, info = self._handle_verify_fix(action, pr)

        # ── Ordering bonus (trajectory-level, awarded once) ─────────────────
        ordering_bonus = self._check_ordering_bonus()
        if ordering_bonus != 0.0:
            reward_val += ordering_bonus
            info["ordering_bonus"] = ordering_bonus

        self._accumulate(reward_val)

        # ── SLA soft-deadline penalty (per-step, after soft threshold) ───────
        sla_penalty = self._maybe_sla_penalty()
        if sla_penalty != 0.0:
            self._accumulate(sla_penalty)
            info["sla_delay_penalty"] = sla_penalty

        # ── Termination check ────────────────────────────────────────────────
        done = self._check_done()

        # ── Hard deadline breach adds one-time penalty and forces done ───────
        if (
            self.review_deadline
            and self.step_count > self.review_deadline
            and not self._sla_penalty_paid
        ):
            breach = self._penalty("deadline_breach_penalty")
            self._accumulate(breach)
            reward_val += breach
            info["deadline_breach"] = True
            self._sla_penalty_paid = True
            done = True

        info["cumulative_reward"] = round(self.cumulative_reward, 4)
        return self._build_observation(), Reward(reward=_clamp(reward_val), done=done, info=info)

    def grade_episode(self) -> float:
        """
        Deterministic grade for the completed episode.

        score = PRs_handled_correctly / total_PRs
        Returns strictly open interval (0.001, 0.999) — validator requires
        scores strictly between 0 and 1, never exactly 0.0 or 1.0.
        """
        total   = len(self.prs)
        correct = 0
        for pr in self.prs:
            truth = self._get_ground_truth(pr["id"])
            if truth is None:
                continue
            if truth.get("is_clean") and pr["status"] == "approved":
                correct += 1
            elif not truth.get("is_clean") and pr["status"] == "changes_requested":
                correct += 1
        raw = correct / total if total > 0 else 0.0
        return float(min(0.99, max(0.01, raw)))



    def state_snapshot(self) -> Dict[str, Any]:
        """Return full environment state for debugging / /state endpoint."""
        return {
            "pull_requests":     self.prs,
            "step":              self.step_count,
            "max_steps":         self.max_steps,
            "steps_remaining":   max(0, self.max_steps - self.step_count),
            "pending_reviews":   sum(1 for pr in self.prs if pr["status"] not in TERMINAL_STATES),
            "cumulative_reward": self.cumulative_reward,
            "episode_grade":     self.grade_episode(),
            "done":              self._check_done(),
        }

    # -----------------------------------------------------------------------
    # Action Handlers
    # -----------------------------------------------------------------------

    def _handle_analyze(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified for analyze_code"}

        if pr["status"] != "submitted":
            return self._penalty("invalid_action_penalty"), {
                "error": f"PR #{pr['id']} already in state '{pr['status']}' — cannot re-analyze"
            }

        pr["status"]   = "analyzing"
        pr["analyzed"] = True
        reward = self.reward_config.get("analyze_reward", 0.05)
        return _clamp(reward), {"message": f"Analyzing PR #{pr['id']}"}

    def _handle_flag_issue(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified"}

        # State validation: must analyze first
        if not pr.get("analyzed"):
            return self._penalty("invalid_action_penalty"), {
                "error": f"PR #{pr['id']} not analyzed yet — call analyze_code first"
            }

        issue_type = action.value
        truth      = self._get_ground_truth(pr["id"])
        if truth is None:
            return self._penalty("invalid_action_penalty"), {"error": "No ground truth for PR"}

        if issue_type in truth.get("issues", []):
            pr["status"] = "issues_found"
            pr.setdefault("flagged_issues", []).append(issue_type)
            reward = self.reward_config.get("correct_bug_detection", 0.40)
            return _clamp(reward), {"message": f"Correctly identified '{issue_type}' in PR #{pr['id']}"}
        else:
            # False positive
            pr.setdefault("flagged_issues", []).append(issue_type)
            reward = self.reward_config.get("false_positive_penalty", -0.20)
            return _clamp(reward), {"error": f"False positive: '{issue_type}' is not an issue in PR #{pr['id']}"}

    def _handle_set_severity(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified"}

        # State validation
        if pr["status"] not in {"issues_found", "analyzing"}:
            return self._penalty("invalid_action_penalty"), {
                "error": f"PR #{pr['id']} has no flagged issues to set severity on (state={pr['status']!r})"
            }

        severity = action.value
        truth    = self._get_ground_truth(pr["id"])
        if truth and severity == truth.get("severity"):
            pr["severity"] = severity
            reward = self.reward_config.get("correct_severity", 0.15)
            return _clamp(reward), {"message": f"Correct severity '{severity}' for PR #{pr['id']}"}
        else:
            pr["severity"] = severity
            reward = self.reward_config.get("wrong_severity_penalty", -0.15)
            expected = truth.get("severity") if truth else "unknown"
            return _clamp(reward), {
                "error": f"Wrong severity '{severity}' for PR #{pr['id']} (expected '{expected}')"
            }

    def _handle_request_changes(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified"}

        if pr["status"] not in {"issues_found", "analyzing"}:
            return self._penalty("invalid_action_penalty"), {
                "error": f"Invalid state '{pr['status']}' for request_changes on PR #{pr['id']}"
            }

        truth = self._get_ground_truth(pr["id"])
        if truth and len(truth.get("issues", [])) > 0:
            pr["status"] = "changes_requested"
            reward = self.reward_config.get("actionable_feedback", 0.20)
            return _clamp(reward), {"message": f"Changes requested on PR #{pr['id']}"}
        else:
            # Requesting changes on clean code — penalise
            pr["status"] = "changes_requested"
            reward = self.reward_config.get("false_positive_penalty", -0.20)
            return _clamp(reward), {"error": f"PR #{pr['id']} is clean — requesting changes is a false positive"}

    def _handle_approve(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified"}

        # Must have analyzed
        if not pr.get("analyzed"):
            return self._penalty("invalid_action_penalty"), {
                "error": f"PR #{pr['id']} not analyzed — cannot approve without analysis"
            }

        # Check dependency: if this PR depends on something not yet resolved, penalise
        for dep_id in pr.get("dependencies", []):
            dep_pr = self._get_pr(dep_id)
            if dep_pr and dep_pr["status"] not in TERMINAL_STATES:
                reward = self._penalty("invalid_action_penalty")
                return reward, {
                    "error": (
                        f"PR #{pr['id']} depends on PR #{dep_id} which is not yet resolved "
                        f"(state={dep_pr['status']!r}) — resolve dependencies first"
                    )
                }

        truth = self._get_ground_truth(pr["id"])
        if truth and len(truth.get("issues", [])) == 0:
            pr["status"] = "approved"
            reward = self.reward_config.get("approve_clean_code", 0.25)
            return _clamp(reward), {"message": f"Correctly approved clean PR #{pr['id']}"}
        else:
            # Approving buggy code — critical penalty
            pr["status"] = "approved"
            reward = self.reward_config.get("approve_buggy_code_penalty", -0.80)
            return _clamp(reward), {"error": f"Approved PR #{pr['id']} which has bugs/security issues!"}

    def _handle_verify_fix(self, action: Action, pr: Optional[Dict]) -> tuple[float, Dict]:
        if pr is None:
            return self._penalty("invalid_action_penalty"), {"error": "No PR specified"}

        if pr["status"] != "changes_requested":
            return self._penalty("invalid_action_penalty"), {
                "error": f"PR #{pr['id']} is in state '{pr['status']}' — nothing to verify"
            }

        pr["status"] = "re_review"
        reward = self.reward_config.get("verify_fix_reward", 0.10)
        return _clamp(reward), {"message": f"Fix verified for PR #{pr['id']}, ready for re-review"}

    # -----------------------------------------------------------------------
    # Ordering Bonus / SLA Penalty (trajectory-level signals)
    # -----------------------------------------------------------------------

    def _check_ordering_bonus(self) -> float:
        """
        Award one-time ordering bonus when security PRs are resolved before
        low-severity PRs. Penalise reverse ordering.
        Returned reward added to the current step's reward.
        """
        if self._ordering_bonus_paid:
            return 0.0

        bonus_cfg   = self.reward_config.get("optimal_ordering_bonus", 0.0)
        penalty_cfg = self.reward_config.get("wrong_ordering_penalty", 0.0)
        if bonus_cfg == 0.0 and penalty_cfg == 0.0:
            return 0.0

        # Gather security and style/clean ground-truth IDs
        security_ids = {
            t["id"] for t in self.ground_truth
            if "security" in t.get("issues", []) or t.get("severity") == "critical"
        }
        style_ids = {
            t["id"] for t in self.ground_truth
            if t.get("is_clean") or t.get("severity") in {None, "low", "style"}
        }

        # Check if any security PR reached terminal state first
        sec_done   = [pr for pr in self.prs if pr["id"] in security_ids  and pr["status"] in TERMINAL_STATES]
        style_done = [pr for pr in self.prs if pr["id"] in style_ids     and pr["status"] in TERMINAL_STATES]

        if sec_done and not style_done:
            # Security PR(s) resolved while style PRs are still open → optimal!
            self._ordering_bonus_paid = True
            return _clamp(bonus_cfg)

        if style_done and not sec_done and security_ids:
            # Style PRs done first while security still open → penalty
            self._ordering_bonus_paid = True
            return _clamp(penalty_cfg)   # penalty_cfg should be negative

        return 0.0

    def _maybe_sla_penalty(self) -> float:
        """
        Apply a one-time SLA delay penalty after the soft deadline
        (80 % of review_deadline) passes and there are still open PRs.
        """
        if self._sla_penalty_paid or not self.review_deadline:
            return 0.0
        soft_deadline = int(self.review_deadline * 0.80)
        if self.step_count < soft_deadline:
            return 0.0
        open_prs = [pr for pr in self.prs if pr["status"] not in TERMINAL_STATES]
        if not open_prs:
            return 0.0
        self._sla_penalty_paid = True
        return _clamp(self.reward_config.get("sla_delay_penalty", -0.20))

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _penalty(self, key: str) -> float:
        return _clamp(self.reward_config.get(key, -0.10))

    def _accumulate(self, val: float) -> None:
        self.cumulative_reward += val

    def _get_pr(self, pr_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if pr_id is None:
            return None
        for pr in self.prs:
            if pr["id"] == pr_id:
                return pr
        return None

    def _get_ground_truth(self, pr_id: int) -> Optional[Dict[str, Any]]:
        for truth in self.ground_truth:
            if truth["id"] == pr_id:
                return truth
        return None

    def _build_observation(self) -> Observation:
        pending = sum(1 for pr in self.prs if pr["status"] not in TERMINAL_STATES)
        pressure = 0.0
        if self.review_deadline:
            pressure = min(self.step_count / self.review_deadline, 1.0)
        return Observation(
            pull_requests=self.prs,
            step=self.step_count,
            steps_remaining=max(0, self.max_steps - self.step_count),
            pending_reviews=pending,
            review_pressure=pressure,
            code_standards=self.code_standards,
            cumulative_reward=round(self.cumulative_reward, 4),
        )

    def _check_done(self) -> bool:
        """
        Episode terminates when ANY of these hold:
          1. All PRs in terminal state
          2. Step budget reached
          3. Hard SLA deadline breached
        """
        all_closed       = all(pr["status"] in TERMINAL_STATES for pr in self.prs)
        budget_exhausted = self.step_count >= self.max_steps
        sla_breached     = bool(self.review_deadline and self.step_count > self.review_deadline)
        return all_closed or budget_exhausted or sla_breached


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _clamp(val: float) -> float:
    """Strictly enforce reward range [-1.0, 1.0] and return float."""
    return float(max(-1.0, min(1.0, val)))
