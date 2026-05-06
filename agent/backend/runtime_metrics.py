"""IDE / Agent 运行时显式指标：Token、工具调用成功率与耗时。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def ensure_runtime_metrics(state: Optional[Dict[str, Any]]) -> None:
    if not state:
        return
    if state.get("runtime_metrics") is None:
        state["runtime_metrics"] = {
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "llm_calls": 0,
            "tool_calls": [],
        }


def record_llm_usage(state: Optional[Dict[str, Any]], response: Any) -> None:
    if not state:
        return
    ensure_runtime_metrics(state)
    u = getattr(response, "usage", None)
    if not u:
        return
    pt = int(getattr(u, "prompt_tokens", None) or 0)
    ct = int(getattr(u, "completion_tokens", None) or 0)
    tt = getattr(u, "total_tokens", None)
    tt = int(tt) if tt is not None else pt + ct
    m = state["runtime_metrics"]
    m["tokens"]["prompt"] += pt
    m["tokens"]["completion"] += ct
    m["tokens"]["total"] += tt
    m["llm_calls"] = int(m.get("llm_calls") or 0) + 1


def record_tool_call(state: Optional[Dict[str, Any]], name: str, ok: bool, latency_ms: float) -> None:
    if not state:
        return
    ensure_runtime_metrics(state)
    state["runtime_metrics"].setdefault("tool_calls", []).append(
        {"name": name, "ok": ok, "latency_ms": round(latency_ms, 3)}
    )


def summarize_runtime_metrics(blob: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not blob:
        return {
            "tokens_total": 0,
            "llm_calls": 0,
            "tool_success_rate": None,
            "tool_avg_latency_ms": None,
            "tool_counts_by_name": {},
        }
    tokens = blob.get("tokens") or {}
    events = blob.get("tool_calls") or []
    by_name: Dict[str, Dict[str, Any]] = {}
    ok_n = 0
    lat_sum = 0.0
    for e in events:
        nm = str(e.get("name") or "")
        ok = bool(e.get("ok"))
        ms = float(e.get("latency_ms") or 0)
        if ok:
            ok_n += 1
        lat_sum += ms
        if nm not in by_name:
            by_name[nm] = {"count": 0, "ok": 0, "latency_sum_ms": 0.0}
        by_name[nm]["count"] += 1
        if ok:
            by_name[nm]["ok"] += 1
        by_name[nm]["latency_sum_ms"] += ms

    n_tools = len(events)
    return {
        "tokens_total": int(tokens.get("total") or 0),
        "tokens_prompt": int(tokens.get("prompt") or 0),
        "tokens_completion": int(tokens.get("completion") or 0),
        "llm_calls": int(blob.get("llm_calls") or 0),
        "tool_success_rate": (ok_n / n_tools) if n_tools else None,
        "tool_avg_latency_ms": (lat_sum / n_tools) if n_tools else None,
        "tool_counts_by_name": by_name,
        "tool_events_count": n_tools,
    }


def radar_tool_success_norm(summary: Dict[str, Any]) -> float:
    """0–1，越高越好；无工具调用时记为 1.0。"""
    r = summary.get("tool_success_rate")
    if r is None:
        return 1.0
    return max(0.0, min(1.0, float(r)))


def radar_token_efficiency_norm(summary: Dict[str, Any], ref_tokens: int = 8000) -> float:
    """产出同等任务时节俭更好：tokens 越少越接近 1。"""
    t = int(summary.get("tokens_total") or 0)
    if t <= 0:
        return 1.0
    import math

    return max(0.0, min(1.0, 1.0 - math.log1p(max(0, t - 500)) / math.log1p(ref_tokens)))
