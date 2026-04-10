"""
grader.py — Deterministic Episode Grader
=========================================
Standalone grader module for the CodeReview RL environment.

Each task grader produces a score in [0.0, 1.0]:
    score = correct_pr_outcomes / total_prs

A PR outcome is "correct" when:
    - Clean PR  (no ground-truth issues) → status == "approved"
    - Buggy PR  (has ground-truth issues) → status == "changes_requested"

Scores are always:
    float(min(1.0, max(0.0, raw_score)))   # strictly clamped
    reproducible for any given action sequence
    zero randomness, zero heuristics
"""

from __future__ import annotations
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Core grading function
# ---------------------------------------------------------------------------

def grade(
    pull_requests: List[Dict[str, Any]],
    ground_truth:  List[Dict[str, Any]],
) -> float:
    """
    Grade a completed episode deterministically.

    Parameters
    ----------
    pull_requests : list of PR dicts from env state
    ground_truth  : list of ground-truth dicts from the task scenario

    Returns
    -------
    float in [0.0, 1.0]
        1.0 = all PRs handled correctly
        0.0 = all PRs handled incorrectly
    """
    if not pull_requests:
        return 0.0

    truth_map: Dict[int, Dict[str, Any]] = {t["id"]: t for t in ground_truth}
    correct = 0
    total   = len(pull_requests)

    for pr in pull_requests:
        truth = truth_map.get(pr["id"])
        if truth is None:
            continue

        if truth.get("is_clean") and pr["status"] == "approved":
            correct += 1
        elif not truth.get("is_clean") and pr["status"] == "changes_requested":
            correct += 1

    raw = correct / total
    return float(min(1.0, max(0.0, raw)))


# ---------------------------------------------------------------------------
# Task-specific wrappers (used by app.py /grade endpoint)
# ---------------------------------------------------------------------------

def grade_easy(env_state: Dict[str, Any]) -> float:
    """Grade the easy task episode."""
    return _grade_from_state(env_state)


def grade_medium(env_state: Dict[str, Any]) -> float:
    """Grade the medium task episode."""
    return _grade_from_state(env_state)


def grade_hard(env_state: Dict[str, Any]) -> float:
    """Grade the hard task episode."""
    return _grade_from_state(env_state)


GRADERS = {
    "easy":   grade_easy,
    "medium": grade_medium,
    "hard":   grade_hard,
}


def grade_task(task: str, env_state: Dict[str, Any]) -> float:
    """
    Grade any task by name.

    Parameters
    ----------
    task      : "easy" | "medium" | "hard"
    env_state : dict returned by env.state_snapshot()

    Returns
    -------
    float in [0.0, 1.0]
    """
    grader = GRADERS.get(task)
    if grader is None:
        raise ValueError(f"Unknown task {task!r}. Valid tasks: {list(GRADERS)}")
    return grader(env_state)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _grade_from_state(env_state: Dict[str, Any]) -> float:
    """Extract PRs and ground truth from a state snapshot and grade."""
    prs    = env_state.get("pull_requests", [])
    truths = env_state.get("ground_truth",  [])
    return grade(prs, truths)
