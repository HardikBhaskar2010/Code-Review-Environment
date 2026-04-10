"""
inference.py — CodeReview RL Environment Inference Script
==========================================================
MANDATORY environment variables:
    API_BASE_URL       The API endpoint for the LLM.
    MODEL_NAME         The model identifier to use for inference.
    HF_TOKEN           Your Hugging Face / API key.

STDOUT FORMAT (strictly enforced by validator):
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...,rn>
"""

import os
import json
import textwrap
from typing import List, Optional

# Auto-load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME   = os.getenv("MODEL_NAME")  or "Qwen/Qwen2.5-72B-Instruct"
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")

TASKS                   = ["easy", "medium", "hard"]
BENCHMARK               = "codereview_env"
MAX_STEPS               = 30   # outer safety cap — env terminates earlier via done
TEMPERATURE             = 0.2
MAX_TOKENS              = 256
SUCCESS_SCORE_THRESHOLD = 0.5

# Maximum possible cumulative reward per task (used for normalisation).
# easy:   analyze(0.05) + flag(0.40) + severity(0.15) + request_changes(0.20) = 0.80
# medium: 3 PRs × optimal path ≈ 2.05  (includes ordering bonus 0.15)
# hard:   5 PRs × optimal path ≈ 3.30  (includes ordering bonus 0.20)
MAX_REWARD = {
    "easy":   0.80,
    "medium": 2.05,
    "hard":   3.30,
}

# ---------------------------------------------------------------------------
# Structured stdout helpers
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val  = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )

# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert code reviewer with deep knowledge of software security, infrastructure, and best practices.

You will receive pull requests to review. Each step you must output ONE action as valid JSON — nothing else.

## Valid actions
- analyze_code      → start analyzing a PR's code (REQUIRED before any other action on that PR)
- flag_issue        → identify an issue: bug | security | style | performance
- set_severity      → set severity: critical | high | medium | low
- request_changes   → ask developer to fix issues (use after flagging + setting severity)
- approve_pr        → approve clean code (only if no issues found)
- verify_fix        → verify that requested changes were fixed (only after request_changes)

## Response format (STRICT — output ONLY this JSON, no markdown, no explanation)
{"action": "<action_name>", "pr_id": <int or null>, "value": "<string or null>"}

## Strategy
1. ALWAYS call analyze_code before any other action on a PR
2. PRIORITY ORDER: handle critical/security/infra PRs BEFORE medium/low/style PRs
3. Check PR dependencies — if a PR depends on another, resolve the blocker FIRST
4. Security and data-loss bugs are CRITICAL severity
5. Bugs causing crashes or service failures are HIGH severity
6. Performance issues without outage impact are MEDIUM severity
7. Style issues are LOW severity
8. Only approve PRs with ZERO issues
9. If a PR has dependencies listed, ensure all dependent PRs are resolved before approving

## Critical Rules
- NEVER approve code with bugs, security issues, or data-loss risk
- NEVER skip analyze_code — flagging without analyzing is rejected
- ALWAYS set severity explicitly before requesting changes
- ALWAYS resolve blocker PRs before dependent PRs
- Prioritize: critical → high → medium → low → clean approvals
""").strip()

# ---------------------------------------------------------------------------
# Environment client
# ---------------------------------------------------------------------------

def env_reset(task: str) -> dict:
    r = httpx.post(f"{ENV_BASE_URL}/reset", params={"task": task}, timeout=30)
    r.raise_for_status()
    return r.json()


def env_step(action: dict) -> dict:
    r = httpx.post(
        f"{ENV_BASE_URL}/step",
        json=action,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def env_close() -> None:
    """Signal environment cleanup. For HTTP envs this is a health-check no-op."""
    try:
        httpx.get(f"{ENV_BASE_URL}/health", timeout=5)
    except Exception:
        pass  # best-effort; never raise during cleanup

# ---------------------------------------------------------------------------
# Action parsing
# ---------------------------------------------------------------------------

def parse_action(text: str) -> Optional[dict]:
    """Extract JSON action from LLM response."""
    text = text.strip()
    # Strip markdown code fences
    if "```" in text:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                text = line
                break
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return {
            "action": str(parsed.get("action", "")),
            "pr_id":  parsed.get("pr_id"),
            "value":  parsed.get("value"),
        }
    except json.JSONDecodeError:
        return None


def action_to_str(action: dict) -> str:
    """Compact representation for [STEP] log."""
    pr_id = action.get("pr_id")
    val = action.get("value")
    parts = [action.get("action", "unknown")]
    if pr_id is not None:
        parts.append(str(pr_id))
    if val is not None:
        parts.append(f'"{val}"')
    return f"{parts[0]}({','.join(parts[1:])})"

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def get_model_action(prompt: str, history: List[str]) -> str:
    history_block = "\n".join(history[-6:]) if history else "None"
    user_prompt = (
        f"Recent steps:\n{history_block}\n\n"
        f"Current state:\n{prompt}\n\n"
        "Output your next action as JSON."
    )
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return ""

# ---------------------------------------------------------------------------
# Single episode runner
# ---------------------------------------------------------------------------

def run_episode(task: str) -> None:
    # Scores must survive score:.2f formatting and still be strictly in (0, 1).
    # 0.002 rounds to '0.00' → parsed as 0.0 → REJECTED by validator.
    # 0.998 rounds to '1.00' → parsed as 1.0 → REJECTED by validator.
    # 0.01  rounds to '0.01' → parsed as 0.01 → ACCEPTED. ✓
    # 0.99  rounds to '0.99' → parsed as 0.99 → ACCEPTED. ✓
    MIN_VALID_SCORE = 0.01
    MAX_VALID_SCORE = 0.99
    
    rewards:      List[float] = []
    steps_taken:  int         = 0
    success:      bool        = False
    score:        float       = MIN_VALID_SCORE
    history:      List[str]   = []

    log_start(task=task, env=BENCHMARK, model=MODEL_NAME)

    try:
        result      = env_reset(task)
        done        = result.get("done", False)

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            obs    = result.get("observation", {})
            prompt = obs.get("prompt", "")

            # Build context from message history
            messages = obs.get("messages", [])
            if messages:
                msg_block = "\n".join(
                    f"[{m.get('category','MSG')}] {m.get('content','')}"
                    for m in messages[-4:]
                )
                prompt = f"{msg_block}\n\n{prompt}"

            raw_text = get_model_action(prompt, history)
            action   = parse_action(raw_text)
            error    = None

            if action is None:
                error  = f"parse_error: {raw_text[:60]!r}"
                action = {"action": "analyze_code", "pr_id": 1, "value": None}

            try:
                result      = env_step(action)
                reward      = float(result.get("reward", 0.0))
                done        = result.get("done", False)
                step_error  = result.get("info", {}).get("error")
                if step_error:
                    error = step_error
            except httpx.HTTPStatusError as e:
                reward = 0.0
                error  = str(e)
                done   = False

            rewards.append(reward)
            steps_taken  = step
            action_str   = action_to_str(action)

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            history.append(
                f"Step {step}: {action_str} -> reward {reward:+.2f}"
                + (f" [ERROR: {error}]" if error else "")
            )

            if done:
                break

        # Normalise score: cumulative reward / theoretical max → [0, 1]
        max_r   = MAX_REWARD.get(task, 1.0)
        total   = sum(rewards)
        score   = float(min(max(total / max_r, MIN_VALID_SCORE), MAX_VALID_SCORE))
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error: {exc}", flush=True)
        score = MIN_VALID_SCORE

    finally:
        env_close()   # mirrors sample's env.close() — always runs
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60, flush=True)
    print(f"CodeReview RL Inference Runner", flush=True)
    print(f"Model:   {MODEL_NAME}", flush=True)
    print(f"API:     {API_BASE_URL}", flush=True)
    print(f"Env:     {ENV_BASE_URL}", flush=True)
    print("=" * 60, flush=True)

    for task in TASKS:
        run_episode(task)
        print(flush=True)


if __name__ == "__main__":
    main()
