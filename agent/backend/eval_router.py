"""评测平台 HTTP 路由。"""
import json
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query

from agent.backend.evaluation_jobs import (
    aggregate_task_analytics,
    cancel_eval_task,
    create_dataset_from_bytes,
    create_dataset_from_payload,
    create_eval_task,
    delete_dataset,
    delete_eval_task,
    get_dataset_row,
    get_eval_task,
    list_datasets,
    list_eval_tasks,
    list_task_results,
    patch_eval_task,
    start_eval_task,
)
from agent.backend.schemas import (
    EvalDatasetJsonCreate,
    EvalDatasetRow,
    EvalTaskCreateRequest,
    EvalTaskPatchRequest,
    EvalTaskResponse,
    EvalTaskResultResponse,
)

router = APIRouter(prefix="/eval", tags=["evaluation"])


def _task_to_resp(row: Dict[str, Any]) -> EvalTaskResponse:
    data = dict(row)
    if "storage_path" in data:
        data.pop("storage_path", None)
    try:
        data["current_trace_json"] = json.loads(data.get("current_trace_json") or "[]")
    except json.JSONDecodeError:
        data["current_trace_json"] = []
    return EvalTaskResponse(**data)


def _result_to_resp(row: Dict[str, Any]) -> EvalTaskResultResponse:
    d = dict(row)
    p = d.get("passed")
    if p is None:
        passed_bool = None
    else:
        passed_bool = bool(p)
    return EvalTaskResultResponse(
        id=d["id"],
        task_id=d["task_id"],
        item_index=d["item_index"],
        item_key=d.get("item_key") or "",
        description_snapshot=d.get("description_snapshot"),
        status=d["status"],
        passed=passed_bool,
        score_detail=d.get("score_detail") or {},
        final_answer=d.get("final_answer") or "",
        trace_json=d.get("trace_json") or [],
        run_error=d.get("run_error") or "",
        ragas_json=d.get("ragas_json") or {},
        judge_json=d.get("judge_json") or {},
        runtime_metrics_json=d.get("runtime_metrics_json") or {},
        radar_json=d.get("radar_json") or {},
        security_json=d.get("security_json") or {},
        started_at=d.get("started_at"),
        finished_at=d.get("finished_at"),
    )


@router.post("/datasets/upload", response_model=EvalDatasetRow)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(None),
):
    raw = await file.read()
    try:
        row = create_dataset_from_bytes(file.filename, raw, display_name=name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row["storage_path"] = None
    return EvalDatasetRow(**row)


@router.post("/datasets", response_model=EvalDatasetRow)
def create_dataset_json(body: EvalDatasetJsonCreate):
    try:
        payload = {"name": body.name or "", "items": body.items}
        row = create_dataset_from_payload(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row["storage_path"] = None
    return EvalDatasetRow(**row)


@router.get("/datasets", response_model=List[EvalDatasetRow])
def api_list_datasets():
    rows = list_datasets()
    out = []
    for r in rows:
        d = dict(r)
        d.pop("storage_path", None)
        out.append(EvalDatasetRow(**d))
    return out


@router.get("/datasets/{dataset_id}", response_model=EvalDatasetRow)
def api_get_dataset(dataset_id: str):
    row = get_dataset_row(dataset_id)
    if not row:
        raise HTTPException(status_code=404, detail="数据集不存在")
    row.pop("storage_path", None)
    return EvalDatasetRow(id=row["id"], name=row["name"], created_at=row["created_at"], item_count=row["item_count"])


@router.delete("/datasets/{dataset_id}")
def api_delete_dataset(dataset_id: str, cascade: bool = Query(False)):
    try:
        delete_dataset(dataset_id, cascade_tasks=cascade)
    except LookupError:
        raise HTTPException(status_code=404, detail="数据集不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.post("/tasks", response_model=EvalTaskResponse)
def api_create_task(body: EvalTaskCreateRequest):
    try:
        row = create_eval_task(body.name, body.dataset_id, body.eval_method)
    except LookupError:
        raise HTTPException(status_code=404, detail="数据集不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    full = list_eval_tasks()
    match = next((x for x in full if x["id"] == row["id"]), row)
    return _task_to_resp(match)


@router.get("/tasks", response_model=List[EvalTaskResponse])
def api_list_tasks():
    return [_task_to_resp(r) for r in list_eval_tasks()]


@router.get("/tasks/{task_id}", response_model=EvalTaskResponse)
def api_get_task(task_id: str):
    try:
        rows = list_eval_tasks()
        match = next((x for x in rows if x["id"] == task_id), None)
        if match:
            return _task_to_resp(match)
        row = get_eval_task(task_id)
        return _task_to_resp(row)
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None


@router.patch("/tasks/{task_id}", response_model=EvalTaskResponse)
def api_patch_task(task_id: str, body: EvalTaskPatchRequest):
    try:
        row = patch_eval_task(task_id, name=body.name, eval_method=body.eval_method)
        rows = list_eval_tasks()
        match = next((x for x in rows if x["id"] == row["id"]), row)
        return _task_to_resp(match)
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/tasks/{task_id}")
def api_delete_task(task_id: str):
    try:
        delete_eval_task(task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.post("/tasks/{task_id}/start", response_model=EvalTaskResponse)
def api_start_task(task_id: str):
    try:
        start_eval_task(task_id)
        rows = list_eval_tasks()
        match = next((x for x in rows if x["id"] == task_id), None)
        if match:
            return _task_to_resp(match)
        return _task_to_resp(get_eval_task(task_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务或数据集不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/tasks/{task_id}/cancel", response_model=EvalTaskResponse)
def api_cancel_task(task_id: str):
    try:
        cancel_eval_task(task_id)
        rows = list_eval_tasks()
        match = next((x for x in rows if x["id"] == task_id), None)
        if match:
            return _task_to_resp(match)
        return _task_to_resp(get_eval_task(task_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/tasks/{task_id}/results", response_model=List[EvalTaskResultResponse])
def api_task_results(task_id: str):
    try:
        rows = list_task_results(task_id)
        return [_result_to_resp(r) for r in rows]
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None


@router.get("/tasks/{task_id}/analytics")
def api_task_analytics(task_id: str):
    try:
        return aggregate_task_analytics(task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None


@router.get("/analytics/compare")
def api_compare_analytics(
    left_task_id: str = Query(..., alias="left"),
    right_task_id: str = Query(..., alias="right"),
):
    try:
        return {
            "left": aggregate_task_analytics(left_task_id),
            "right": aggregate_task_analytics(right_task_id),
        }
    except LookupError:
        raise HTTPException(status_code=404, detail="评测任务不存在") from None
