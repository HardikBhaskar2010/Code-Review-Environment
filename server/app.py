"""
server/app.py — CodeReview RL Environment FastAPI Server
=========================================================
HTTP API wrapper around CodeReviewEnv.
Conforms to OpenEnv spec for compatibility with evaluation tools.

Endpoints:
  POST /reset?task=easy|medium|hard   → ResetResult  (200)
  POST /step                          → StepResult   (200)
  GET  /state                         → EnvSnapshot  (200)
  GET  /health                        → Health check
  GET  /metadata                      → Environment info
  GET  /schema                        → Action/Observation schemas
  POST /mcp                           → MCP/JSON-RPC endpoint

Runs on:  uvicorn server.app:app --host 0.0.0.0 --port 7860
"""

from __future__ import annotations

import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from env.env import CodeReviewEnv, Action, Observation, Reward
from tasks.easy import EASY_SCENARIO
from tasks.medium import MEDIUM_SCENARIO
from tasks.hard import HARD_SCENARIO

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CodeReview RL Environment",
    description=(
        "Multi-step Reinforcement Learning environment simulating code review "
        "and pull request management. Conforms to the OpenEnv spec."
    ),
    version="1.0.0",
)

# Shared environment instance
env = CodeReviewEnv()

TASK_MAP = {
    "easy": EASY_SCENARIO,
    "medium": MEDIUM_SCENARIO,
    "hard": HARD_SCENARIO,
}

# ---------------------------------------------------------------------------
# OpenEnv-compatible response models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """Single message in observation history."""
    category: str
    content: str


class OpenEnvObservation(BaseModel):
    """Observation with prompt, messages, and state."""
    prompt: str
    messages: list[Message]
    state: dict


class ResetResult(BaseModel):
    observation: OpenEnvObservation
    done: bool
    task: str
    max_steps: int


class StepResult(BaseModel):
    observation: OpenEnvObservation
    reward: float
    done: bool
    info: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_prompt(obs_raw: dict) -> str:
    """Render observation into human-readable prompt."""
    lines: list[str] = ["# CodeReview Dashboard\n"]

    prs = obs_raw.get("pull_requests", [])
    lines.append(f"**Pending reviews:** {obs_raw.get('pending_reviews', 0)}/{len(prs)}")
    lines.append(f"**Step:** {obs_raw.get('step', 0)}  |  **Review pressure:** {obs_raw.get('review_pressure', 0.0):.0%}\n")

    for pr in prs:
        status_tag = f"[{pr['status'].upper()}]"
        lines.append(
            f"---\n"
            f"**PR #{pr['id']}** {status_tag}  \n"
            f"Title: {pr['title']}  \n"
            f"Author: {pr['author']}  \n"
            f"Description: {pr['description']}  \n"
            f"Files: {', '.join(pr['files_changed'])}"
        )
        
        if pr.get("code_diff"):
            lines.append(f"\nCode diff:\n```diff\n{pr['code_diff']}\n```")
        
        if pr.get("flagged_issues"):
            lines.append(f"Flagged issues: {', '.join(pr['flagged_issues'])}")
        
        if pr.get("severity"):
            lines.append(f"Severity: {pr['severity']}")
        
        if pr.get("dependencies"):
            lines.append(f"Depends on: PR {', '.join(map(str, pr['dependencies']))}")

    if obs_raw.get("code_standards"):
        lines.append("\n## Code Standards")
        for std in obs_raw["code_standards"]:
            lines.append(f"- {std}")

    lines.append(
        "\n## Your Action\n"
        "Respond with a JSON object specifying your next action:\n"
        "```json\n"
        '{"action": "<action_name>", "pr_id": <int|null>, "value": "<str|null>"}\n'
        "```\n"
        "Valid actions: analyze_code, flag_issue, set_severity, request_changes, approve_pr, verify_fix"
    )

    return "\n".join(lines)


def _build_openenv_obs(raw_obs: dict, messages: list[Message]) -> OpenEnvObservation:
    return OpenEnvObservation(
        prompt=_render_prompt(raw_obs),
        messages=messages,
        state=raw_obs,
    )


_message_history: list[Message] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "CodeReview RL Environment",
        "version": "1.0.0",
        "spec": "OpenEnv v1.0",
        "endpoints": ["/reset", "/step", "/state", "/health", "/metadata", "/schema"],
        "tasks": list(TASK_MAP.keys()),
    }


@app.post("/reset", response_model=ResetResult, summary="Reset the environment")
async def reset(
    task: str = Query(default="easy", enum=["easy", "medium", "hard"])
) -> ResetResult:
    """Reset environment and load task scenario."""
    global _message_history

    if task not in TASK_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task '{task}'. Choose from {list(TASK_MAP)}",
        )

    scenario = TASK_MAP[task]
    raw_obs = env.reset(scenario)
    raw_dict = raw_obs.model_dump()

    _message_history = [
        Message(
            category="SYSTEM",
            content=(
                f"CodeReview RL Environment — Task: {task.upper()}\n"
                f"{scenario['description']}"
            ),
        )
    ]

    openenv_obs = _build_openenv_obs(raw_dict, list(_message_history))

    return ResetResult(
        observation=openenv_obs,
        done=False,
        task=task,
        max_steps=scenario["max_steps"],
    )


@app.post("/step", response_model=StepResult, summary="Take one action")
async def step(action: Action) -> StepResult:
    """Execute agent action and advance environment."""
    global _message_history

    try:
        raw_obs, reward = env.step(action)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw_dict = raw_obs.model_dump()

    # Build feedback message
    feedback_lines = [
        f"Action: {action.action} | pr_id={action.pr_id} | value={action.value}",
        f"Reward: {reward.reward:+.4f} | Done: {reward.done}",
    ]
    if reward.info:
        feedback_lines.append(f"Info: {json.dumps(reward.info)}")

    _message_history.append(
        Message(category="FEEDBACK", content="\n".join(feedback_lines))
    )

    openenv_obs = _build_openenv_obs(raw_dict, list(_message_history))

    return StepResult(
        observation=openenv_obs,
        reward=reward.reward,
        done=reward.done,
        info=reward.info,
    )


@app.get("/state", summary="Get current environment state")
async def state() -> JSONResponse:
    """Full environment state snapshot."""
    return JSONResponse(content=env.state_snapshot())


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "healthy"}


@app.get("/metadata", summary="Environment metadata")
async def metadata():
    """Return environment metadata for OpenEnv validator."""
    return {
        "name": "codereview_env",
        "description": (
            "Multi-step Reinforcement Learning environment simulating code review "
            "and pull request management. Agent analyzes code, identifies bugs, "
            "sets severity, and approves or requests changes across three difficulty levels."
        ),
        "version": "1.0.0",
        "tasks": list(TASK_MAP.keys()),
        "reward_range": [-1.0, 1.0],
        "author": "hackathon-team",
    }


@app.get("/schema", summary="Action/Observation schemas")
async def schema():
    """Return schemas for OpenEnv validator."""
    return {
        "action": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "analyze_code",
                        "flag_issue",
                        "set_severity",
                        "request_changes",
                        "approve_pr",
                        "verify_fix",
                    ],
                },
                "pr_id": {"type": ["integer", "null"]},
                "value": {"type": ["string", "null"]},
            },
            "required": ["action"],
        },
        "observation": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "messages": {"type": "array"},
                "state": {"type": "object"},
            },
        },
        "state": {
            "type": "object",
            "properties": {
                "pull_requests": {"type": "array"},
                "step": {"type": "integer"},
                "pending_reviews": {"type": "integer"},
                "review_pressure": {"type": "number"},
                "done": {"type": "boolean"},
            },
        },
    }


@app.post("/mcp", summary="MCP/JSON-RPC 2.0 endpoint")
async def mcp(request: dict) -> JSONResponse:
    """Minimal JSON-RPC 2.0 endpoint for OpenEnv validator."""
    method = request.get("method", "")
    req_id = request.get("id", 1)

    def ok(result):
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})

    def err(code, msg):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}
        )

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "codereview_env", "version": "1.0.0"},
        })

    if method == "tools/list":
        return ok({"tools": [
            {"name": "reset", "description": "Reset the environment",
             "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}}},
            {"name": "step", "description": "Take one action",
             "inputSchema": {"type": "object", "properties": {
                 "action": {"type": "string"},
                 "pr_id": {"type": ["integer", "null"]},
                 "value": {"type": ["string", "null"]},
             }}},
            {"name": "state", "description": "Get current state",
             "inputSchema": {"type": "object"}},
        ]})

    if method == "tools/call":
        params = request.get("params", {})
        tool = params.get("name", "")
        args = params.get("arguments", {})

        if tool == "reset":
            task = args.get("task", "easy")
            scenario = TASK_MAP.get(task)
            if not scenario:
                return err(-32602, f"Unknown task '{task}'")
            raw_obs = env.reset(scenario)
            return ok({"content": [{"type": "text", "text": str(raw_obs.model_dump())}]})

        if tool == "step":
            action = Action(**args)
            try:
                raw_obs, reward = env.step(action)
                return ok({"content": [{"type": "text", "text": str({
                    "reward": reward.reward, "done": reward.done,
                })}]})
            except RuntimeError as e:
                return err(-32603, str(e))

        if tool == "state":
            return ok({"content": [{"type": "text", "text": str(env.state_snapshot())}]})

        return err(-32601, f"Unknown tool '{tool}'")

    return err(-32601, f"Method not found: '{method}'")


def main():
    """Main entry point."""
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
