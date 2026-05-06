"""根据评测方法判定单条用例是否通过。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _contains_ci(haystack: str, needle: str) -> bool:
    if not needle.strip():
        return True
    return needle.strip().lower() in (haystack or "").lower()


def evaluate_result_oriented(final_answer: str, item: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    detail: Dict[str, Any] = {}
    fa = final_answer or ""

    exp = item.get("expected_output")
    if exp:
        ok = _contains_ci(fa, str(exp))
        detail["expected_output_match"] = ok
        if not ok:
            return False, detail

    for i, tc in enumerate(item.get("test_cases") or []):
        ex = tc.get("expected")
        if ex is None or str(ex).strip() == "":
            continue
        key = f"test_case_{i}"
        ok = _contains_ci(fa, str(ex))
        detail[key] = ok
        if not ok:
            return False, detail

    return True, detail


def evaluate_process_oriented(
    final_answer: str,
    item: Dict[str, Any],
    errors: List[Any],
    trace: List[Any],
) -> Tuple[bool, Dict[str, Any]]:
    detail: Dict[str, Any] = {
        "trace_steps": len(trace or []),
        "errors_count": len(errors or []),
    }
    if detail["errors_count"] > 0:
        return False, detail
    if detail["trace_steps"] < 2:
        return False, detail

    if item.get("expected_output"):
        ok, sub = evaluate_result_oriented(final_answer, item)
        detail["result_subcheck"] = sub
        return ok, detail

    return True, detail


def decide_passed(
    eval_method: str,
    final_answer: str,
    item: Dict[str, Any],
    state_errors: List[Any],
    trace: List[Any],
) -> Tuple[bool, Dict[str, Any]]:
    if eval_method == "process":
        return evaluate_process_oriented(final_answer, item, state_errors, trace)
    return evaluate_result_oriented(final_answer, item)


def build_eval_prompt(item: Dict[str, Any]) -> str:
    parts: List[str] = [item["description"]]
    exp = item.get("expected_output")
    if exp:
        parts.append(
            "\n【评测说明】请在最终答复中包含或与下列预期输出语义一致的关键内容（可简述）：\n"
            + str(exp).strip()
        )
    tcs = item.get("test_cases") or []
    if tcs:
        lines = ["\n【测试要点】"]
        for tc in tcs:
            inp = tc.get("input", "")
            ex = tc.get("expected", "")
            lines.append(f"- 情境/输入：{inp} → 答复应覆盖期望要点：{ex}")
        parts.append("\n".join(lines))
    return "\n".join(parts)
