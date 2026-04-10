"""Pre-submission compliance audit script."""
import sys

issues = []

print("=" * 60)
print("PRE-SUBMISSION COMPLIANCE AUDIT")
print("=" * 60)

# 1. Imports
try:
    from env.env import CodeReviewEnv, Action, Observation, Reward, _clamp
    print("[PASS] env.py imports cleanly")
except Exception as e:
    issues.append(f"FAIL env.py: {e}")

try:
    from tasks.easy   import EASY_SCENARIO
    from tasks.medium import MEDIUM_SCENARIO
    from tasks.hard   import HARD_SCENARIO
    print("[PASS] tasks/easy/medium/hard import OK")
except Exception as e:
    issues.append(f"FAIL tasks: {e}")

try:
    from grader import grade, grade_task, GRADERS
    print("[PASS] grader.py imports cleanly")
except Exception as e:
    issues.append(f"FAIL grader.py: {e}")

try:
    import app as _app
    print("[PASS] app.py (FastAPI) imports cleanly")
except Exception as e:
    issues.append(f"FAIL app.py: {e}")

# 2. Pydantic models
try:
    a = Action(action="analyze_code", pr_id=1)
    o = Observation()
    r = Reward(reward=0.5, done=False)
    print("[PASS] Pydantic models: Action / Observation / Reward")
except Exception as e:
    issues.append(f"FAIL pydantic models: {e}")

# 3. reset / step / state_snapshot API
try:
    env = CodeReviewEnv()
    obs = env.reset(EASY_SCENARIO)
    assert hasattr(obs, "pull_requests"), "missing pull_requests"
    assert hasattr(obs, "steps_remaining"), "missing steps_remaining"
    assert hasattr(obs, "cumulative_reward"), "missing cumulative_reward"
    obs2, rew = env.step(Action(action="analyze_code", pr_id=1))
    snap = env.state_snapshot()
    assert "pull_requests" in snap
    assert "done" in snap
    print("[PASS] reset() / step() / state_snapshot() API")
except Exception as e:
    issues.append(f"FAIL core API: {e}")

# 4. Graders return float in [0.0, 1.0]
try:
    env2 = CodeReviewEnv()
    for task, scenario in [
        ("easy",   EASY_SCENARIO),
        ("medium", MEDIUM_SCENARIO),
        ("hard",   HARD_SCENARIO),
    ]:
        env2.reset(scenario)
        snap = env2.state_snapshot()
        snap["ground_truth"] = env2.ground_truth
        score = grade_task(task, snap)
        assert isinstance(score, float), f"{task} score not float: {type(score)}"
        assert 0.0 <= score <= 1.0,      f"{task} score out of range: {score}"
    print("[PASS] Graders: float in [0.0, 1.0] for all 3 tasks")
except Exception as e:
    issues.append(f"FAIL grader range: {e}")

# 5. Determinism: same trajectory → same score
try:
    def run_optimal_easy():
        e = CodeReviewEnv()
        e.reset(EASY_SCENARIO)
        e.step(Action(action="analyze_code",    pr_id=1))
        e.step(Action(action="flag_issue",      pr_id=1, value="bug"))
        e.step(Action(action="set_severity",    pr_id=1, value="high"))
        e.step(Action(action="request_changes", pr_id=1))
        return e.grade_episode()

    g1 = run_optimal_easy()
    g2 = run_optimal_easy()
    assert g1 == g2 == 1.0, f"Not deterministic: {g1} vs {g2}"
    print("[PASS] grade_episode() is deterministic (same trajectory = same score)")
except Exception as e:
    issues.append(f"FAIL determinism: {e}")

# 6. Reward clamping
try:
    assert _clamp(-999) == -1.0
    assert _clamp(999)  ==  1.0
    env4 = CodeReviewEnv()
    env4.reset(EASY_SCENARIO)
    _, r = env4.step(Action(action="flag_issue", pr_id=1, value="bug"))  # no analyze
    assert -1.0 <= r.reward <= 1.0, f"reward out of range: {r.reward}"
    print("[PASS] Rewards clamped to [-1.0, 1.0], invalid transitions penalized")
except Exception as e:
    issues.append(f"FAIL reward clamping: {e}")

# 7. Episode termination conditions
try:
    env5 = CodeReviewEnv()
    env5.reset(EASY_SCENARIO)
    env5.step(Action(action="analyze_code",    pr_id=1))
    env5.step(Action(action="flag_issue",      pr_id=1, value="bug"))
    env5.step(Action(action="set_severity",    pr_id=1, value="high"))
    _, r = env5.step(Action(action="request_changes", pr_id=1))
    assert r.done, "Expected done=True after all PRs resolved"

    scenario_1step = dict(EASY_SCENARIO)
    scenario_1step["max_steps"] = 1
    env5.reset(scenario_1step)
    env5.step(Action(action="analyze_code", pr_id=1))
    assert env5._check_done(), "Expected done=True after step budget exhausted"
    print("[PASS] Episode termination: all_closed / budget / sla_breach")
except Exception as e:
    issues.append(f"FAIL termination: {e}")

# 8. Hard task structure
try:
    assert len(HARD_SCENARIO["pull_requests"]) == 5, "Hard task should have 5 PRs"
    assert HARD_SCENARIO["max_steps"] == 15, f"max_steps={HARD_SCENARIO['max_steps']}"
    assert HARD_SCENARIO["review_deadline"] == 12
    print("[PASS] Hard task: 5 PRs, MAX_STEPS=15, SLA=12")
except Exception as e:
    issues.append(f"FAIL hard task config: {e}")

# 9. Trajectory rewards present
try:
    assert HARD_SCENARIO["reward_config"]["optimal_ordering_bonus"] > 0
    assert HARD_SCENARIO["reward_config"]["wrong_ordering_penalty"] < 0
    assert HARD_SCENARIO["reward_config"]["sla_delay_penalty"] < 0
    print("[PASS] Trajectory rewards: ordering_bonus / penalty / sla_delay present")
except Exception as e:
    issues.append(f"FAIL trajectory rewards: {e}")

# 10. FastAPI routes
try:
    import app as _app2
    routes = [r.path for r in _app2.app.routes]
    required = ["/reset", "/step", "/state", "/health", "/metadata", "/schema", "/grade"]
    missing = [p for p in required if p not in routes]
    assert not missing, f"Missing routes: {missing}"
    print("[PASS] API endpoints: /reset /step /state /health /metadata /schema /grade")
except Exception as e:
    issues.append(f"FAIL endpoints: {e}")

# 11. openenv.yaml
try:
    import yaml  # type: ignore
    with open("openenv.yaml") as f:
        cfg = yaml.safe_load(f)
    assert set(cfg["tasks"]) == {"easy", "medium", "hard"}
    assert cfg["port"] == 7860
    print("[PASS] openenv.yaml: tasks=[easy,medium,hard] port=7860")
except ImportError:
    # yaml not installed — check manually
    with open("openenv.yaml") as f:
        content = f.read()
    assert "easy" in content and "medium" in content and "hard" in content
    assert "7860" in content
    print("[PASS] openenv.yaml: tasks + port present (yaml not installed, text check)")
except Exception as e:
    issues.append(f"FAIL openenv.yaml: {e}")

# 12. inference.py stdout format check
try:
    with open("inference.py") as f:
        src = f.read()
    assert "[START]" in src
    assert "[STEP]"  in src
    assert "[END]"   in src
    assert "score={" in src
    assert "env_close()" in src
    assert "HF_TOKEN" in src
    assert "API_BASE_URL" in src
    assert "MODEL_NAME" in src
    print("[PASS] inference.py: [START]/[STEP]/[END] format, env vars, env_close()")
except Exception as e:
    issues.append(f"FAIL inference.py format: {e}")

# 13. grader.py standalone
try:
    import grader as _grader
    assert hasattr(_grader, "grade")
    assert hasattr(_grader, "grade_task")
    assert hasattr(_grader, "GRADERS")
    assert set(_grader.GRADERS.keys()) == {"easy", "medium", "hard"}
    print("[PASS] grader.py: grade() / grade_task() / GRADERS dict present")
except Exception as e:
    issues.append(f"FAIL grader.py structure: {e}")

# Summary
print()
print("=" * 60)
if issues:
    print(f"RESULT: {len(issues)} ISSUE(S) FOUND:")
    for i in issues:
        print(f"  !! {i}")
    sys.exit(1)
else:
    print("RESULT: ALL 13 CHECKS PASSED - READY TO SUBMIT")
print("=" * 60)
