"""根据评测方法判定单条用例是否通过。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def _contains_ci(haystack: str, needle: str) -> bool:
    if not needle.strip():
        return True
    return needle.strip().lower() in (haystack or "").lower()


def _normalize_text(text: str) -> str:
    return re.sub(r"[\s，,；;。.:：、（）()【】\[\]\"'“”‘’`*_《》<>/-]+", "", str(text or "").lower())


def _rubric_keywords(needle: str) -> List[str]:
    normalized = _normalize_text(needle)
    keywords: List[str] = []
    candidates = (
        "空列表", "除以0", "风险", "拒绝", "执行", "对话", "工具",
        "跨对话", "知识共享", "添加skill", "skill", "main", "passed",
    )
    for candidate in candidates:
        if _normalize_text(candidate) in normalized:
            keywords.append(_normalize_text(candidate))
    return keywords


def _contains_semantic(haystack: str, needle: str) -> bool:
    """Loose keyword coverage for short Chinese rubric phrases.

    The eval dataset often stores expectations as compact rubric sentences
    such as "拒绝执行并说明风险". A correct answer may express the same
    meaning across several sentences, so exact substring matching is too
    brittle for these small result-oriented checks.
    """
    raw_needle = str(needle or "").strip()
    if not raw_needle:
        return True
    if _contains_ci(haystack, raw_needle):
        return True

    h = _normalize_text(haystack)
    n = _normalize_text(raw_needle)
    if n and n in h:
        return True

    rubric_keywords = _rubric_keywords(raw_needle)
    if rubric_keywords:
        return all(keyword in h for keyword in rubric_keywords)

    stop_words = (
        "指出", "说明", "具体", "应该", "需要", "要求", "进行",
        "给出", "可以", "以及", "导致", "造成", "并", "和", "或", "的", "该",
    )
    parts = [p for p in re.split(r"[，,；;。.\s、：:（）()]+", n) if p]
    expanded: List[str] = []
    for part in parts or [n]:
        for word in stop_words:
            part = part.replace(word, " ")
        expanded.extend(x for x in part.split() if len(x) >= 2)

    if not expanded:
        return False
    return all(token in h for token in expanded)


def evaluate_result_oriented(final_answer: str, item: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    detail: Dict[str, Any] = {}
    fa = final_answer or ""

    exp = item.get("expected_output")
    if exp:
        ok = _contains_semantic(fa, str(exp))
        detail["expected_output_match"] = ok
        if not ok:
            return False, detail

    for i, tc in enumerate(item.get("test_cases") or []):
        ex = tc.get("expected")
        if ex is None or str(ex).strip() == "":
            continue
        key = f"test_case_{i}"
        ok = _contains_semantic(fa, str(ex))
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
    if detail["trace_steps"] < 2:
        detail["process_quality"] = "insufficient_trace"
        return False, detail

    result_ok = True
    if item.get("expected_output"):
        result_ok, sub = evaluate_result_oriented(final_answer, item)
        detail["result_subcheck"] = sub
        if not result_ok:
            detail["process_quality"] = "result_mismatch"
            return False, detail

    if detail["errors_count"] > 0:
        detail["recovered_from_errors"] = bool((final_answer or "").strip() and result_ok)
        detail["process_quality"] = "recovered_with_errors" if detail["recovered_from_errors"] else "unrecovered_errors"
        return detail["recovered_from_errors"], detail

    detail["recovered_from_errors"] = False
    detail["process_quality"] = "clean"

    return True, detail


def evaluate_combined(
    final_answer: str,
    item: Dict[str, Any],
    errors: List[Any],
    trace: List[Any],
) -> Tuple[bool, Dict[str, Any]]:
    """联合评估：同时检查输出匹配（结果维度）和过程质量（过程维度），两者均须通过。"""
    result_ok, result_detail = evaluate_result_oriented(final_answer, item)
    process_ok, process_detail = evaluate_process_oriented(final_answer, item, errors, trace)
    combined_ok = result_ok and process_ok
    return combined_ok, {
        "result_check": result_detail,
        "process_check": process_detail,
        "result_passed": result_ok,
        "process_passed": process_ok,
    }


def _trace_content(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("content") or entry.get("message") or "")


def _extract_plan_difficulty(trace: List[Any]) -> str:
    for entry in trace or []:
        if isinstance(entry, dict) and entry.get("phase") == "plan_difficulty":
            return _trace_content(entry).strip().lower()
    return ""


def _extract_plan_step_count(trace: List[Any]) -> int:
    for entry in trace or []:
        if not isinstance(entry, dict) or entry.get("phase") != "plan_result":
            continue
        content = _trace_content(entry)
        numbered = re.findall(r"(?m)^\s*\d+[.、)]\s+", content)
        if numbered:
            return len(numbered)
        lines = [line for line in content.splitlines() if line.strip()]
        if lines:
            return len(lines)
    return 0


def evaluate_plan_oriented(item: Dict[str, Any], trace: List[Any]) -> Tuple[bool, Dict[str, Any]]:
    expected = item.get("expected_plan") or {}
    if not isinstance(expected, dict):
        expected = {}
    expected_difficulty = str(expected.get("difficulty") or item.get("difficulty") or "").strip().lower()
    step_range = expected.get("step_range") or [1, 20]
    try:
        lo, hi = int(step_range[0]), int(step_range[1])
    except (TypeError, ValueError, IndexError):
        lo, hi = 1, 20

    actual_difficulty = _extract_plan_difficulty(trace)
    step_count = _extract_plan_step_count(trace)
    difficulty_ok = bool(expected_difficulty) and actual_difficulty == expected_difficulty
    step_count_ok = lo <= step_count <= hi
    detail = {
        "plan_expected_difficulty": expected_difficulty,
        "plan_actual_difficulty": actual_difficulty,
        "plan_expected_step_range": [lo, hi],
        "plan_actual_step_count": step_count,
        "plan_difficulty_ok": difficulty_ok,
        "plan_step_count_ok": step_count_ok,
    }
    return difficulty_ok and step_count_ok, detail


def _requires_rag(item: Dict[str, Any]) -> bool:
    text = f"{item.get('id', '')} {item.get('description', '')}".lower()
    return bool(re.search(r"(^|[^a-z])rag([^a-z]|$)", text)) or any(
        marker in text for marker in ("知识库", "检索")
    )


def _has_successful_rag_search(trace: List[Any]) -> bool:
    waiting_for_rag_observe = False
    for entry in trace or []:
        if not isinstance(entry, dict):
            continue
        content = _trace_content(entry)
        if entry.get("phase") == "act" and "rag_search" in content:
            waiting_for_rag_observe = True
            continue
        if entry.get("phase") != "observe" or not waiting_for_rag_observe:
            continue
        waiting_for_rag_observe = False
        if '"status": "error"' in content or "'status': 'error'" in content:
            continue
        if "RAG 检索失败" in content or "rag_error" in content:
            continue
        if '"results": []' in content or "'results': []" in content:
            continue
        return True
    return False


def decide_passed(
    eval_method: str,
    final_answer: str,
    item: Dict[str, Any],
    state_errors: List[Any],
    trace: List[Any],
) -> Tuple[bool, Dict[str, Any]]:
    if item.get("expected_plan") or item.get("difficulty"):
        return evaluate_plan_oriented(item, trace)
    if _requires_rag(item):
        result_ok, result_detail = evaluate_result_oriented(final_answer, item)
        rag_ok = _has_successful_rag_search(trace)
        detail = {
            "result_check": result_detail,
            "rag_search_success": rag_ok,
        }
        return result_ok and rag_ok, detail
    if eval_method == "process":
        return evaluate_process_oriented(final_answer, item, state_errors, trace)
    if eval_method == "combined":
        return evaluate_combined(final_answer, item, state_errors, trace)
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
