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