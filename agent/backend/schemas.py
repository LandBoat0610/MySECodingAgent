# agent/backend/schemas.py
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

from enum import Enum

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

FileTreeResponse.model_rebuild()