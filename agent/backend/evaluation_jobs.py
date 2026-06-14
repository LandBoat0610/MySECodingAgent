"""评测任务 CRUD、数据集持久化与后台执行（复用 LangGraph Agent）。"""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.backend.database import get_connection
from agent.backend.eval_dataset import (
    canonical_dataset_document,
    load_dataset_items_from_path,
    normalize_dataset_payload,
    parse_upload_json_bytes,
)
from agent.backend.eval_scoring import build_eval_prompt, decide_passed
from agent.backend.eval_storage import DATASETS_DIR, WORKSPACES_DIR, ensure_eval_storage_dirs
from agent.backend.platform_settings import get_agent_config
from agent.backend.utils import sync_workspace_file_back

_eval_threads: Dict[str, threading.Thread] = {}
_eval_cancel: Dict[str, threading.Event] = {}
_registry_lock = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat()


def _quality_metrics_enabled() -> bool:
    return os.environ.get("EVAL_ENABLE_QUALITY", "").lower() in ("1", "true", "yes")


def _update_task_progress(
    task_id: str,
    *,
    phase: str,
    item_index: int = -1,
    item: Optional[Dict[str, Any]] = None,
    completed: Optional[int] = None,
    passed: Optional[int] = None,
    failed: Optional[int] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
) -> None:
    updates = [
        "current_phase = ?",
        "current_item_index = ?",
        "current_item_key = ?",
        "current_item_description = ?",
        "updated_at = ?",
    ]
    params: List[Any] = [
        phase,
        item_index,
        str((item or {}).get("id") or ""),
        str((item or {}).get("description") or "")[:500],
        _now(),
    ]
    if completed is not None:
        updates.append("completed_items = ?")
        params.append(completed)
    if passed is not None:
        updates.append("passed_count = ?")
        params.append(passed)
    if failed is not None:
        updates.append("failed_count = ?")
        params.append(failed)
    if trace is not None:
        updates.append("current_trace_json = ?")
        params.append(json.dumps(trace[-200:], ensure_ascii=False))
    params.append(task_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE eval_tasks SET {', '.join(updates)} WHERE id = ?", tuple(params))


def create_dataset_from_bytes(filename: str | None, raw: bytes, display_name: Optional[str] = None) -> Dict[str, Any]:
    ensure_eval_storage_dirs()
    name_from_payload, items = parse_upload_json_bytes(raw)
    ds_name = (display_name or "").strip() or name_from_payload or (filename or "dataset")
    doc = canonical_dataset_document(ds_name, items)
    dataset_id = uuid.uuid4().hex[:12]
    path = os.path.join(DATASETS_DIR, f"{dataset_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    created_at = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO eval_datasets (id, name, created_at, item_count, storage_path)
               VALUES (?, ?, ?, ?, ?)""",
            (dataset_id, ds_name, created_at, len(items), path),
        )
    return {"id": dataset_id, "name": ds_name, "created_at": created_at, "item_count": len(items)}


def create_dataset_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_eval_storage_dirs()
    name_in, items = normalize_dataset_payload(payload)
    ds_name = str(payload.get("name") or "").strip() or name_in
    doc = canonical_dataset_document(ds_name, items)
    dataset_id = uuid.uuid4().hex[:12]
    path = os.path.join(DATASETS_DIR, f"{dataset_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    created_at = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO eval_datasets (id, name, created_at, item_count, storage_path)
               VALUES (?, ?, ?, ?, ?)""",
            (dataset_id, ds_name, created_at, len(items), path),
        )
    return {"id": dataset_id, "name": ds_name, "created_at": created_at, "item_count": len(items)}


def list_datasets() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM eval_datasets ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_dataset_row(dataset_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM eval_datasets WHERE id = ?", (dataset_id,)).fetchone()
    return dict(row) if row else None


def delete_dataset(dataset_id: str, cascade_tasks: bool = False) -> None:
    row = get_dataset_row(dataset_id)
    if not row:
        raise LookupError("数据集不存在")

    with get_connection() as conn:
        task_rows = conn.execute(
            "SELECT id, status FROM eval_tasks WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    refs = [dict(r) for r in task_rows]

    if refs:
        if not cascade_tasks:
            raise ValueError("仍有评测任务引用该数据集，无法删除。请先删除相关评测任务，或在界面勾选「同时删除关联任务」。")
        for tr in refs:
            if tr.get("status") in ("running", "cancelling"):
                raise ValueError("存在运行中的评测任务，请先点「取消」结束后再删除数据集。")
        for tr in refs:
            delete_eval_task(tr["id"])

    with get_connection() as conn:
        conn.execute("DELETE FROM eval_datasets WHERE id = ?", (dataset_id,))
    path = row.get("storage_path")
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def create_eval_task(name: str, dataset_id: str, eval_method: str) -> Dict[str, Any]:
    if eval_method not in ("result", "process", "combined"):
        raise ValueError('eval_method 须为 "result"、"process" 或 "combined"')
    ds = get_dataset_row(dataset_id)
    if not ds:
        raise LookupError("数据集不存在")

    cfg = get_agent_config()
    task_id = uuid.uuid4().hex[:12]
    created_at = _now()
    total_items = int(ds["item_count"])

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO eval_tasks (
                id, name, created_at, updated_at, dataset_id, eval_method,
                agent_model_snapshot, agent_version_label_snapshot,
                status, total_items, completed_items, passed_count, failed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 0, 0, 0)""",
            (
                task_id,
                name.strip(),
                created_at,
                created_at,
                dataset_id,
                eval_method,
                str(cfg.get("model") or ""),
                str(cfg.get("version_label") or ""),
                total_items,
            ),
        )
    return get_eval_task(task_id)


def get_eval_task(task_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM eval_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        raise LookupError("评测任务不存在")
    return dict(row)


def list_eval_tasks() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.*, d.name AS dataset_name
               FROM eval_tasks t
               JOIN eval_datasets d ON d.id = t.dataset_id
               ORDER BY t.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def patch_eval_task(task_id: str, name: Optional[str] = None, eval_method: Optional[str] = None) -> Dict[str, Any]:
    task = get_eval_task(task_id)
    if task["status"] != "pending":
        raise ValueError("仅「待运行」状态的任务可修改配置")

    updates = []
    params: List[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if eval_method is not None:
        if eval_method not in ("result", "process", "combined"):
            raise ValueError('eval_method 须为 "result"、"process" 或 "combined"')
        updates.append("eval_method = ?")
        params.append(eval_method)

    if not updates:
        return task

    params.append(_now())
    params.append(task_id)
    sql = f"UPDATE eval_tasks SET {', '.join(updates)}, updated_at = ? WHERE id = ?"
    with get_connection() as conn:
        conn.execute(sql, tuple(params))
    return get_eval_task(task_id)


def delete_eval_task(task_id: str) -> None:
    task = get_eval_task(task_id)
    if task["status"] in ("running", "cancelling"):
        raise ValueError("任务运行中，请先取消")
    with get_connection() as conn:
        conn.execute("DELETE FROM eval_task_results WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM eval_tasks WHERE id = ?", (task_id,))
    base = os.path.join(WORKSPACES_DIR, task_id)
    if os.path.isdir(base):
        try:
            shutil.rmtree(base, ignore_errors=True)
        except OSError:
            pass


def list_task_results(task_id: str) -> List[Dict[str, Any]]:
    _ = get_eval_task(task_id)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM eval_task_results WHERE task_id = ?
               ORDER BY item_index ASC""",
            (task_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["score_detail"] = json.loads(d.get("score_detail") or "{}")
        except json.JSONDecodeError:
            d["score_detail"] = {}
        try:
            d["trace_json"] = json.loads(d.get("trace_json") or "[]")
        except json.JSONDecodeError:
            d["trace_json"] = []
        for key in ("ragas_json", "judge_json", "runtime_metrics_json", "radar_json", "security_json"):
            try:
                d[key] = json.loads(d.get(key) or "{}")
            except json.JSONDecodeError:
                d[key] = {}
        out.append(d)
    return out


def aggregate_task_analytics(task_id: str) -> Dict[str, Any]:
    from agent.backend.eval_quality import build_radar_vector, mean_radar
    from agent.backend.runtime_metrics import summarize_runtime_metrics

    rows = list_task_results(task_id)
    radars: List[Dict[str, float]] = []
    item_views: List[Dict[str, Any]] = []

    # 显式指标聚合
    tokens_total_sum = 0
    tokens_prompt_sum = 0
    tokens_completion_sum = 0
    llm_calls_sum = 0
    tool_success_rates: List[float] = []
    tool_latencies: List[float] = []
    response_times_ms: List[float] = []
    security_band_counts: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    ragas_ar_vals: List[float] = []
    ragas_ff_vals: List[float] = []
    judge_rq_vals: List[float] = []
    judge_hs_vals: List[float] = []

    for r in rows:
        rv = r.get("radar_json") or {}
        if isinstance(rv, dict) and rv:
            radars.append({k: float(v) for k, v in rv.items()})

        # 运行时指标
        rm = r.get("runtime_metrics_json") or {}
        if isinstance(rm, dict):
            tokens_total_sum += int(rm.get("tokens_total") or 0)
            tokens_prompt_sum += int(rm.get("tokens_prompt") or 0)
            tokens_completion_sum += int(rm.get("tokens_completion") or 0)
            llm_calls_sum += int(rm.get("llm_calls") or 0)
            tsr = rm.get("tool_success_rate")
            if tsr is not None:
                try:
                    tool_success_rates.append(float(tsr))
                except (TypeError, ValueError):
                    pass
            tal = rm.get("tool_avg_latency_ms")
            if tal is not None:
                try:
                    tool_latencies.append(float(tal))
                except (TypeError, ValueError):
                    pass

        # 响应时间（基于 started_at / finished_at）
        sa = r.get("started_at")
        fa_time = r.get("finished_at")
        if sa and fa_time:
            try:
                from datetime import datetime as _dt
                t0 = _dt.fromisoformat(sa)
                t1 = _dt.fromisoformat(fa_time)
                response_times_ms.append((t1 - t0).total_seconds() * 1000)
            except Exception:
                pass

        # 安全风险分布
        sec = r.get("security_json") or {}
        if isinstance(sec, dict) and sec:
            band = sec.get("risk_band") or "unknown"
            if band not in security_band_counts:
                band = "unknown"
            security_band_counts[band] += 1

        # Ragas 指标
        ragas = r.get("ragas_json") or {}
        if isinstance(ragas, dict):
            ar = ragas.get("answer_relevancy")
            if ar is not None:
                try:
                    ragas_ar_vals.append(float(ar))
                except (TypeError, ValueError):
                    pass
            ff = ragas.get("faithfulness")
            if ff is not None:
                try:
                    ragas_ff_vals.append(float(ff))
                except (TypeError, ValueError):
                    pass

        # Judge 指标
        judge = r.get("judge_json") or {}
        if isinstance(judge, dict):
            rq = judge.get("reasoning_quality")
            if rq is not None:
                try:
                    judge_rq_vals.append(float(rq))
                except (TypeError, ValueError):
                    pass
            hs = judge.get("hallucination_severity")
            if hs is not None:
                try:
                    judge_hs_vals.append(float(hs))
                except (TypeError, ValueError):
                    pass

        item_views.append(
            {
                "item_index": r["item_index"],
                "item_key": r.get("item_key") or str(r["item_index"]),
                "description_snapshot": r.get("description_snapshot") or "",
                "passed": bool(r["passed"]) if r.get("passed") is not None else None,
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "radar": rv,
                "ragas": r.get("ragas_json"),
                "judge": r.get("judge_json"),
                "runtime_metrics": rm,
                "security": r.get("security_json"),
                "score_detail": r.get("score_detail"),
            }
        )

    n = len(rows)
    default_axes = build_radar_vector({}, {}, summarize_runtime_metrics(None), {})
    mean_vec = mean_radar(radars, list(default_axes.keys())) if radars else {}

    def _safe_mean(lst: List[float]) -> Optional[float]:
        return round(sum(lst) / len(lst), 4) if lst else None

    explicit_metrics = {
        "tokens_total_sum": tokens_total_sum,
        "tokens_prompt_sum": tokens_prompt_sum,
        "tokens_completion_sum": tokens_completion_sum,
        "tokens_avg_per_item": round(tokens_total_sum / n, 1) if n else None,
        "llm_calls_sum": llm_calls_sum,
        "llm_calls_avg": round(llm_calls_sum / n, 2) if n else None,
        "tool_success_rate_avg": _safe_mean(tool_success_rates),
        "tool_avg_latency_ms_avg": _safe_mean(tool_latencies),
        "response_time_avg_ms": _safe_mean(response_times_ms),
        "response_time_max_ms": round(max(response_times_ms), 1) if response_times_ms else None,
        "security_band_counts": security_band_counts,
        "ragas_answer_relevancy_avg": _safe_mean(ragas_ar_vals),
        "ragas_faithfulness_avg": _safe_mean(ragas_ff_vals),
        "judge_reasoning_quality_avg": _safe_mean(judge_rq_vals),
        "judge_hallucination_severity_avg": _safe_mean(judge_hs_vals),
    }

    return {
        "task_id": task_id,
        "radar_mean": mean_vec,
        "radar_axes": list(default_axes.keys()),
        "items": item_views,
        "items_with_radar": len(radars),
        "explicit_metrics": explicit_metrics,
        "total_items": n,
    }


def _get_cancel_event(task_id: str) -> threading.Event:
    with _registry_lock:
        if task_id not in _eval_cancel:
            _eval_cancel[task_id] = threading.Event()
        return _eval_cancel[task_id]


def cancel_eval_task(task_id: str) -> Dict[str, Any]:
    task = get_eval_task(task_id)
    if task["status"] not in ("running", "cancelling"):
        raise ValueError("当前任务未在运行")
    ev = _get_cancel_event(task_id)
    ev.set()
    if task["status"] == "running":
        now = _now()
        with get_connection() as conn:
            conn.execute(
                """UPDATE eval_tasks SET status = 'cancelling', updated_at = ?, error_message = ''
                   WHERE id = ? AND status = 'running'""",
                (now, task_id),
            )
    return get_eval_task(task_id)


def start_eval_task(task_id: str, concurrency: int = 1) -> Dict[str, Any]:
    task = get_eval_task(task_id)
    if task["status"] not in ("pending", "completed", "failed", "cancelled"):
        raise ValueError("任务状态不允许启动")

    with _registry_lock:
        if task_id in _eval_threads and _eval_threads[task_id].is_alive():
            raise ValueError("任务已在运行中")

    ds_row = get_dataset_row(task["dataset_id"])
    if not ds_row:
        raise LookupError("数据集不存在")

    storage_path = ds_row["storage_path"]
    _, items = load_dataset_items_from_path(storage_path)

    cancel_ev = threading.Event()
    with _registry_lock:
        _eval_cancel[task_id] = cancel_ev

    now = _now()
    with get_connection() as conn:
        conn.execute("DELETE FROM eval_task_results WHERE task_id = ?", (task_id,))
        conn.execute(
            """UPDATE eval_tasks SET status = 'running', updated_at = ?, error_message = '',
               completed_items = 0, passed_count = 0, failed_count = 0,
               current_item_index = -1, current_item_key = '', current_item_description = '',
               current_phase = 'queued', current_trace_json = '[]' WHERE id = ?""",
            (now, task_id),
        )

    th = threading.Thread(target=_eval_worker, args=(task_id, items, cancel_ev, concurrency), daemon=True)
    with _registry_lock:
        _eval_threads[task_id] = th
    th.start()
    return get_eval_task(task_id)


def _build_initial_state(
    workspace_dir: str,
    prompt: str,
    cancel_event: threading.Event,
    log_callback_key: str = "",
) -> Dict[str, Any]:
    return {
        "project_id": "eval",
        "workspace_dir": workspace_dir,
        "project_root": workspace_dir,
        "task": prompt,
        "messages": [],
        "trace": [],
        "errors": [],
        "reflections": 0,
        "used_tools": [],
        "result_history": [],
        "modified_files": [],
        "task_list": [],
        "current_task_index": 0,
        "current_task": "",
        "code_context": "",
        "target_file": "",
        "run_command": "",
        "last_tool_result": {},
        "last_execution": {},
        "final_answer": "",
        "task_type": "",
        "task_difficulty": "",
        "current_plan": [],
        "acceptance_criteria": [],
        "relevant_files": [],
        "retrieved_context": [],
        "codebase_summary": "",
        "test_commands": [],
        "tool_history": [],
        "verification_results": [],
        "patch_history": [],
        "failure_reason": "",
        "retry_count": 0,
        "last_review": {},
        "original_target_path": "",
        "should_sync_back": False,
        "status": "idle",
        "memory": "",
        "_cancel_event": cancel_event,
        "_log_callback_key": log_callback_key,
        "eval_mode": True,
        "runtime_metrics": {
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "llm_calls": 0,
            "tool_calls": [],
        },
    }


def _process_single_item(idx: int, item: Dict[str, Any], task_id: str, base_ws: str,
                         cancel_ev: threading.Event, model_snap: str, eval_method: str) -> Dict[str, Any]:
    """处理单条评测用例，返回结果字典。"""
    rid = uuid.uuid4().hex[:10]
    item_ws = os.path.join(base_ws, f"{idx:03d}_{rid}")
    os.makedirs(item_ws, exist_ok=True)

    prompt = build_eval_prompt(item)
    started = _now()
    log_key = f"eval:{task_id}:{idx}:{rid}"
    state = _build_initial_state(item_ws, prompt, cancel_ev, log_key)
    live_trace: List[Dict[str, Any]] = []

    final_state: Dict[str, Any]
    err_text = ""

    from agent.backend.config import eval_model_context as _emc
    from agent.backend.utils import register_log_callback, unregister_log_callback

    def on_log(item_: Dict[str, Any]) -> None:
        live_trace.append(item_)
        _update_task_progress(task_id, phase="running_agent", item_index=idx, item=item, trace=live_trace)

    register_log_callback(on_log, session_id=log_key)
    with _emc(model_snap if model_snap else None):
        try:
            from agent.backend.graph import build_graph, run_manual_fallback
            graph = build_graph()
            if graph:
                final_state = graph.invoke(dict(state))
            else:
                final_state = run_manual_fallback(dict(state))
            sync_workspace_file_back(final_state)
        except Exception as e:
            err_text = str(e)
            final_state = dict(state)
            final_state.setdefault("errors", []).append({"status": "error", "output": err_text})
        finally:
            unregister_log_callback(on_log, session_id=log_key)

    finished = _now()
    fa = str(final_state.get("final_answer") or "")
    trace = final_state.get("trace") or []
    errors = final_state.get("errors") or []

    passed: Optional[bool] = None
    score_detail: Dict[str, Any] = {}
    if err_text and not fa:
        passed = False
        score_detail = {"runner_error": err_text}
    else:
        passed, score_detail = decide_passed(eval_method, fa, item, errors, trace)

    trace_serializable = trace
    try:
        json.dumps(trace_serializable)
    except Exception:
        trace_serializable = [{"phase": "serialize_error", "content": "trace not JSON serializable"}]

    return {
        "rid": rid, "idx": idx, "item": item, "passed": passed,
        "score_detail": score_detail, "fa": fa, "err_text": err_text,
        "trace": trace_serializable, "started": started, "finished": finished,
        "final_state": final_state, "item_ws": item_ws,
    }


def _compute_quality_metrics(row: Dict[str, Any]) -> None:
    from agent.backend.eval_quality import (
        build_contexts_for_ragas, build_radar_vector,
        compute_judge_scores, compute_ragas_scores,
    )
    from agent.backend.eval_security import compute_security_assessment, gather_code_blob_for_security_scan
    from agent.backend.runtime_metrics import summarize_runtime_metrics

    fs = row["final_state"]
    iw = row["item_ws"]
    fa = row["fa"]
    ctxs = build_contexts_for_ragas(fs, iw)
    item_desc = row["item"].get("description", "")
    row["ragas_scores"] = compute_ragas_scores(item_desc, fa, ctxs)
    row["judge_scores"] = compute_judge_scores(item_desc, fa, ctxs)
    security_blob = gather_code_blob_for_security_scan(fs, iw)
    row["security_scores"] = compute_security_assessment(security_blob)
    rm_blob = fs.get("runtime_metrics")
    row["rm_summary"] = summarize_runtime_metrics(
        rm_blob if isinstance(rm_blob, dict) else None
    )
    row["radar_vec"] = build_radar_vector(
        row["ragas_scores"], row["judge_scores"],
        row["rm_summary"], row["security_scores"],
    )


def _compute_fast_metrics(row: Dict[str, Any]) -> None:
    from agent.backend.eval_quality import build_radar_vector
    from agent.backend.eval_security import compute_security_assessment, gather_code_blob_for_security_scan
    from agent.backend.runtime_metrics import summarize_runtime_metrics

    fs = row["final_state"]
    iw = row["item_ws"]
    security_blob = gather_code_blob_for_security_scan(fs, iw)
    row["ragas_scores"] = {}
    row["judge_scores"] = {}
    row["security_scores"] = compute_security_assessment(security_blob)
    rm_blob = fs.get("runtime_metrics")
    row["rm_summary"] = summarize_runtime_metrics(
        rm_blob if isinstance(rm_blob, dict) else None
    )
    row["radar_vec"] = build_radar_vector(
        row["ragas_scores"], row["judge_scores"],
        row["rm_summary"], row["security_scores"],
    )


def _write_result_row(row: Dict[str, Any], task_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO eval_task_results (
                id, task_id, item_index, item_key, description_snapshot,
                status, passed, score_detail, final_answer, trace_json, run_error,
                ragas_json, judge_json, runtime_metrics_json, radar_json, security_json,
                started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["rid"], task_id, row["idx"],
                str(row["item"].get("id", row["idx"])), row["item"].get("description", ""),
                "completed", 1 if row["passed"] else 0,
                json.dumps(row["score_detail"], ensure_ascii=False),
                row["fa"][:50000] if row["fa"] else "",
                json.dumps(row["trace"], ensure_ascii=False),
                row["err_text"][:8000] if row["err_text"] else "",
                json.dumps(row.get("ragas_scores", {}), ensure_ascii=False),
                json.dumps(row.get("judge_scores", {}), ensure_ascii=False),
                json.dumps(row.get("rm_summary", {}), ensure_ascii=False),
                json.dumps(row.get("radar_vec", {}), ensure_ascii=False),
                json.dumps(row.get("security_scores", {}), ensure_ascii=False),
                row["started"], row["finished"],
            ),
        )


def _run_items_sequential(task_id: str, items: List[Dict[str, Any]], cancel_ev: threading.Event,
                          model_snap: str, eval_method: str, base_ws: str) -> None:
    passed_n = 0
    failed_n = 0
    for idx, item in enumerate(items):
        if cancel_ev.is_set():
            break
        _update_task_progress(task_id, phase="running_agent", item_index=idx, item=item)
        row = _process_single_item(idx, item, task_id, base_ws, cancel_ev, model_snap, eval_method)
        _update_task_progress(task_id, phase="scoring", item_index=idx, item=item)
        if _quality_metrics_enabled():
            _compute_quality_metrics(row)
        else:
            _compute_fast_metrics(row)
        _write_result_row(row, task_id)
        if row["passed"]:
            passed_n += 1
        else:
            failed_n += 1
        _update_task_progress(
            task_id,
            phase="item_completed",
            item_index=idx,
            item=item,
            completed=idx + 1,
            passed=passed_n,
            failed=failed_n,
        )


def _run_items_concurrent(task_id: str, items: List[Dict[str, Any]], cancel_ev: threading.Event,
                          model_snap: str, eval_method: str, base_ws: str, concurrency: int) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    passed_n = 0
    failed_n = 0
    results_by_idx: Dict[int, Any] = {}

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(_process_single_item, idx, item, task_id, base_ws, cancel_ev, model_snap, eval_method): idx
            for idx, item in enumerate(items) if not cancel_ev.is_set()
        }
        for future in as_completed(futures):
            if cancel_ev.is_set():
                continue
            try:
                row = future.result()
                idx = row["idx"]
                _update_task_progress(task_id, phase="scoring", item_index=idx, item=row["item"])
                if _quality_metrics_enabled():
                    _compute_quality_metrics(row)
                else:
                    _compute_fast_metrics(row)
                _write_result_row(row, task_id)
                if row["passed"]:
                    passed_n += 1
                else:
                    failed_n += 1
                results_by_idx[idx] = row

                completed = len(results_by_idx)
                _update_task_progress(
                    task_id,
                    phase="item_completed",
                    item_index=idx,
                    item=row["item"],
                    completed=completed,
                    passed=passed_n,
                    failed=failed_n,
                )
            except Exception:
                pass


def _eval_worker(task_id: str, items: List[Dict[str, Any]], cancel_ev: threading.Event, concurrency: int = 1) -> None:
    try:
        task_row = get_eval_task(task_id)
    except LookupError:
        return

    model_snap = (task_row.get("agent_model_snapshot") or "").strip()
    eval_method = task_row.get("eval_method") or "result"

    base_ws = os.path.join(WORKSPACES_DIR, task_id)
    try:
        shutil.rmtree(base_ws, ignore_errors=True)
        os.makedirs(base_ws, exist_ok=True)
    except OSError:
        pass

    try:
        if concurrency <= 1:
            _run_items_sequential(task_id, items, cancel_ev, model_snap, eval_method, base_ws)
        else:
            _run_items_concurrent(task_id, items, cancel_ev, model_snap, eval_method, base_ws, concurrency)

        final_status = "cancelled" if cancel_ev.is_set() else "completed"

        with get_connection() as conn:
            conn.execute(
                """UPDATE eval_tasks SET status = ?, current_phase = ?, updated_at = ? WHERE id = ?""",
                (final_status, final_status, _now(), task_id),
            )

    except Exception as e:
        with get_connection() as conn:
            conn.execute(
                """UPDATE eval_tasks SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?""",
                (str(e)[:4000], _now(), task_id),
            )
    finally:
        with _registry_lock:
            _eval_cancel.pop(task_id, None)
            _eval_threads.pop(task_id, None)
