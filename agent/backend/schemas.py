# agent/backend/schemas.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    workspace_path: Optional[str] = None  # 如果提供则表示“打开已有项目”


class ProjectResponse(BaseModel):
    id: str
    name: str
    workspace_path: str
    created_at: str
    description: str


class DeleteProjectResponse(BaseModel):
    status: str
    project_id: str


class SessionCreateRequest(BaseModel):
    title: Optional[str] = "New Session"


class SessionResponse(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: str
    status: str


class StateResponse(BaseModel):
    session_id: str
    project_id: str
    status: str
    snapshot: Dict[str, Any]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    status: str


class PlanResponse(BaseModel):
    id: str
    session_id: str
    content: str
    status: str
    created_at: str


class PlanAction(str, Enum):
    agree = "agree"
    refine = "refine"
    skip = "skip"
    stop = "stop"


class PlanActionRequest(BaseModel):
    action: PlanAction


class PlanActionResponse(BaseModel):
    plan_id: str
    action: str
    status: str


class FileTreeResponse(BaseModel):
    path: str
    type: str  # file or directory
    children: Optional[List['FileTreeResponse']] = None


class AgentConfigResponse(BaseModel):
    model: str
    version_label: str = ""


class AgentConfigUpdateRequest(BaseModel):
    model: Optional[str] = None
    version_label: Optional[str] = None


class EvalDatasetRow(BaseModel):
    id: str
    name: str
    created_at: str
    item_count: int
    storage_path: Optional[str] = None


class EvalDatasetJsonCreate(BaseModel):
    """JSON Body 创建数据集（items 内嵌）。"""
    name: Optional[str] = ""
    items: List[Dict[str, Any]]


class EvalTaskCreateRequest(BaseModel):
    name: str
    dataset_id: str
    eval_method: str = Field("result", description="result（面向结果）或 process（面向过程）")


class EvalTaskPatchRequest(BaseModel):
    name: Optional[str] = None
    eval_method: Optional[str] = None


class EvalTaskResponse(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    dataset_id: str
    dataset_name: Optional[str] = None
    eval_method: str
    agent_model_snapshot: str = ""
    agent_version_label_snapshot: str = ""
    status: str
    error_message: str = ""
    total_items: int = 0
    completed_items: int = 0
    passed_count: int = 0
    failed_count: int = 0


class EvalTaskResultResponse(BaseModel):
    id: str
    task_id: str
    item_index: int
    item_key: str = ""
    description_snapshot: Optional[str] = None
    status: str
    passed: Optional[bool] = None
    score_detail: Dict[str, Any] = Field(default_factory=dict)
    final_answer: str = ""
    trace_json: List[Any] = Field(default_factory=list)
    run_error: str = ""
    ragas_json: Dict[str, Any] = Field(default_factory=dict)
    judge_json: Dict[str, Any] = Field(default_factory=dict)
    runtime_metrics_json: Dict[str, Any] = Field(default_factory=dict)
    radar_json: Dict[str, Any] = Field(default_factory=dict)
    security_json: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    encoding: str = "utf-8"


FileTreeResponse.model_rebuild()
