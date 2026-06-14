"""Lightweight Planner difficulty smoke test.

This script calls the real LLM-backed create_plan() for each difficulty
sample, then checks only:

- whether the returned difficulty matches the expected difficulty;
- whether the number of planned steps falls inside the expected range.

It intentionally does not execute the Agent steps or check content keywords.
"""

from __future__ import annotations

import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.backend.llm import create_plan


DATASET_PATH = ROOT / "docs" / "iteration3_difficulty_eval_dataset.json"
OUTPUT_PATH = ROOT / "docs" / "iteration3_difficulty_smoke_results.json"
ITEM_TIMEOUT_SECONDS = 90


class PlannerTimeout(TimeoutError):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise PlannerTimeout(f"Planner call exceeded {ITEM_TIMEOUT_SECONDS}s")


def _trace_error(trace: list[dict[str, Any]]) -> str:
    for entry in trace:
        if entry.get("phase") == "plan_error":
            return str(entry.get("content") or entry.get("message") or "")
    return ""


def evaluate_item(item: dict[str, Any]) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    state: dict[str, Any] = {}
    steps: list[str] = []
    error = ""
    previous_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(ITEM_TIMEOUT_SECONDS)
    try:
        steps = create_plan(item["description"], "", trace, state)
        error = _trace_error(trace)
    except Exception as exc:
        error = str(exc)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)

    expected = item.get("expected_plan") or {}
    expected_difficulty = str(expected.get("difficulty") or item.get("difficulty") or "").strip().lower()
    lo, hi = expected.get("step_range", [1, 20])
    actual_difficulty = str(state.get("task_difficulty") or "").strip().lower()
    step_count = len(steps)

    difficulty_ok = bool(actual_difficulty) and actual_difficulty == expected_difficulty
    step_count_ok = int(lo) <= step_count <= int(hi)
    passed = not error and difficulty_ok and step_count_ok

    return {
        "id": item["id"],
        "expected_difficulty": expected_difficulty,
        "actual_difficulty": actual_difficulty,
        "expected_step_range": [int(lo), int(hi)],
        "actual_step_count": step_count,
        "passed": passed,
        "checks": {
            "difficulty_ok": difficulty_ok,
            "step_count_ok": step_count_ok,
            "planner_error": error,
        },
        "steps": steps,
    }


def main() -> int:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    results = []
    for index, item in enumerate(dataset["items"], start=1):
        print(f"[{index}/{len(dataset['items'])}] planning {item['id']}...", flush=True)
        result = evaluate_item(item)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        lo, hi = result["expected_step_range"]
        print(
            f"  {status}: expected={result['expected_difficulty']} "
            f"actual={result['actual_difficulty'] or '-'} "
            f"steps={result['actual_step_count']} expected_steps={lo}-{hi}",
            flush=True,
        )
    try:
        from agent.backend.config import get_effective_model

        model = get_effective_model()
    except Exception:
        model = "unknown"

    summary = {
        "name": "迭代三 Agent 难度规划轻量评测",
        "dataset": dataset.get("name", DATASET_PATH.name),
        "dataset_path": str(DATASET_PATH.relative_to(ROOT)),
        "model": model,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
        "model": model,
        "total": summary["total"],
        "passed": summary["passed"],
        "failed": summary["failed"],
    }, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
