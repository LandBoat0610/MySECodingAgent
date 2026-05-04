# main.py
import os
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from agent.backend.database import init_db, get_connection
from agent.backend.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    SessionCreateRequest,
    SessionResponse,
    StateResponse,
)
from agent.backend.utils import ensure_workspace  # 用于创建目录（或直接使用 os.makedirs）

app = FastAPI(title="Agent Platform", version="0.1.0")

# 全局工作区根目录（所有新建项目目录均放在此下）
WORKSPACES_ROOT = os.path.abspath("workspaces")
os.makedirs(WORKSPACES_ROOT, exist_ok=True)

@app.on_event("startup")
def startup():
    init_db()

# ------------------ 1. 获取项目列表 ------------------
@app.get("/projects", response_model=list[ProjectResponse])
def list_projects():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]

# ------------------ 2. 创建/打开项目 ------------------
@app.post("/projects", response_model=ProjectResponse, status_code=201)
def create_or_open_project(req: ProjectCreateRequest):
    now = datetime.now().isoformat()
    project_id = uuid.uuid4().hex[:8]

    if req.workspace_path:
        # 打开已有项目：验证路径存在
        workspace = os.path.abspath(req.workspace_path)
        if not os.path.isdir(workspace):
            raise HTTPException(status_code=400, detail="指定的工作区路径不存在")
    else:
        # 新建项目：在 workspaces 下创建专属目录
        workspace = os.path.join(WORKSPACES_ROOT, f"project_{project_id}")
        os.makedirs(workspace, exist_ok=True)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, workspace_path, created_at, description) VALUES (?, ?, ?, ?, ?)",
            (project_id, req.name, workspace, now, req.description),
        )

    return ProjectResponse(
        id=project_id,
        name=req.name,
        workspace_path=workspace,
        created_at=now,
        description=req.description,
    )

# ------------------ 3. 获取会话列表 ------------------
@app.get("/projects/{project_id}/sessions", response_model=list[SessionResponse])
def list_sessions(project_id: str):
    with get_connection() as conn:
        # 先确认项目存在
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")
        rows = conn.execute(
            "SELECT id, project_id, title, created_at, status FROM sessions WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]

# ------------------ 4. 新建会话 ------------------
@app.post("/projects/{project_id}/sessions", response_model=SessionResponse, status_code=201)
def create_session(project_id: str, req: SessionCreateRequest):
    now = datetime.now().isoformat()
    session_id = uuid.uuid4().hex[:8]

    with get_connection() as conn:
        proj = conn.execute("SELECT id, workspace_path FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 初始化 AgentState 快照，包含项目工作区等关键信息
        initial_state = {
            "task": "",
            "messages": [],
            "workspace_dir": proj["workspace_path"],   # ← 关键：与项目目录绑定
            "status": "idle",
            "reflections": 0,
            "errors": [],
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
            "original_target_path": "",
            "should_sync_back": False,
            "project_root": proj["workspace_path"],   # 也可以用于后续同步
        }

        conn.execute(
            "INSERT INTO sessions (id, project_id, title, created_at, state_snapshot, status) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, project_id, req.title, now, json.dumps(initial_state, ensure_ascii=False), "idle"),
        )

    return SessionResponse(
        id=session_id,
        project_id=project_id,
        title=req.title,
        created_at=now,
        status="idle",
    )

# ------------------ 5. 获取会话状态快照 ------------------
@app.get("/projects/{project_id}/sessions/{sid}/state", response_model=StateResponse)
def get_session_state(project_id: str, sid: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

    return StateResponse(
        session_id=row["id"],
        project_id=row["project_id"],
        status=row["status"],
        snapshot=json.loads(row["state_snapshot"]),
    )