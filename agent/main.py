# main.py
import os
import uuid
import json
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from agent.backend.database import init_db, get_connection
from agent.backend.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    SessionCreateRequest,
    SessionResponse,
    StateResponse,
    ChatRequest,
    ChatResponse,
    PlanResponse,
    PlanActionRequest,
    PlanActionResponse,
    FileTreeResponse,
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
            "session_id": session_id,
            "project_id": project_id,
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
            "trace": [],
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

# ------------------ 6. 发送消息（对话）------------------
@app.post("/projects/{project_id}/sessions/{sid}/chat", response_model=ChatResponse)
def chat(project_id: str, sid: str, req: ChatRequest):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        # 更新 state_snapshot 中的 task 和 messages
        state = json.loads(row["state_snapshot"])
        state["task"] = req.message
        state["messages"].append({"role": "user", "content": req.message})
        state["status"] = "running"

        conn.execute(
            "UPDATE sessions SET state_snapshot = ?, status = ? WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), "running", sid),
        )

    return ChatResponse(
        session_id=sid,
        reply="消息已接收，Agent 开始处理...",
        status="running",
    )

# 全局会话锁，用于并发控制
session_locks: Dict[str, asyncio.Lock] = {}

def get_session_lock(sid: str) -> asyncio.Lock:
    if sid not in session_locks:
        session_locks[sid] = asyncio.Lock()
    return session_locks[sid]

# ------------------ 7. WebSocket 流式对话 ------------------
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import threading
from agent.backend.graph import build_graph, run_manual_fallback
from agent.backend.utils import sync_workspace_file_back, register_log_callback, unregister_log_callback

_cancel_events: Dict[str, threading.Event] = {}

def get_cancel_event(sid: str) -> threading.Event:
    if sid not in _cancel_events:
        _cancel_events[sid] = threading.Event()
    return _cancel_events[sid]

@app.websocket("/projects/{project_id}/sessions/{sid}/chat/stream")
async def chat_stream(websocket: WebSocket, project_id: str, sid: str):
    await websocket.accept()
    
    lock = get_session_lock(sid)
    if lock.locked():
        await websocket.send_json({"error": "该会话已有 Agent 正在运行，请稍后再试。"})
        await websocket.close()
        return

    async with lock:
        loop = asyncio.get_running_loop()
        cancel_event = get_cancel_event(sid)
        cancel_event.clear()

        def on_log(item):
            if cancel_event.is_set():
                return
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "trace", "data": item}),
                loop,
            )

        register_log_callback(on_log)
        
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
                    (sid, project_id),
                ).fetchone()
                if not row:
                    await websocket.send_json({"error": "会话不存在于该项目下"})
                    await websocket.close()
                    return

            state = json.loads(row["state_snapshot"])
            if not state.get("task"):
                await websocket.send_json({"error": "请先通过 POST /chat 发送任务消息"})
                await websocket.close()
                return

            state["_cancel_event"] = cancel_event

            graph = build_graph()
            
            await websocket.send_json({"phase": "start", "message": "Agent 开始执行..."})
            
            if graph:
                final_state = await asyncio.to_thread(graph.invoke, state)
            else:
                final_state = await asyncio.to_thread(run_manual_fallback, state)
            
            sync_workspace_file_back(final_state)

            if cancel_event.is_set():
                await websocket.send_json({"phase": "cancelled", "message": "Agent 已终止"})
            else:
                await websocket.send_json({
                    "phase": "done", 
                    "message": "任务完成", 
                    "final_answer": final_state.get("final_answer", ""),
                    "status": final_state.get("status")
                })
        except WebSocketDisconnect:
            cancel_event.set()
        except Exception as e:
            try:
                await websocket.send_json({"error": str(e)})
            except Exception:
                pass
        finally:
            unregister_log_callback(on_log)
            try:
                await websocket.close()
            except Exception:
                pass

# ------------------ 8. 获取当前会话的计划树 ------------------
@app.get("/projects/{project_id}/sessions/{sid}/plan", response_model=list[PlanResponse])
def get_plan(project_id: str, sid: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        plans = conn.execute(
            "SELECT * FROM plans WHERE session_id = ? ORDER BY created_at DESC",
            (sid,),
        ).fetchall()

    return [dict(p) for p in plans]

# ------------------ 9. 用户对计划执行确认操作 ------------------
@app.post("/projects/{project_id}/sessions/{sid}/plan/{pid}/action", response_model=PlanActionResponse)
def plan_action(project_id: str, sid: str, pid: str, req: PlanActionRequest):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        plan = conn.execute(
            "SELECT * FROM plans WHERE id = ? AND session_id = ?",
            (pid, sid),
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="计划不存在")

        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO plan_actions (id, plan_id, action_type, created_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex[:8], pid, req.action, now),
        )
        # 更新计划状态
        status_map = {
            "agree": "approved",
            "refine": "refining",
            "skip": "skipped",
            "stop": "stopped",
        }
        new_status = status_map.get(req.action, "pending")
        conn.execute(
            "UPDATE plans SET status = ? WHERE id = ?",
            (new_status, pid),
        )
        conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?",
            (new_status, sid),
        )

    return PlanActionResponse(
        plan_id=pid,
        action=req.action,
        status=new_status,
    )

# ------------------ 10. 获取项目文件树 ------------------
@app.get("/projects/{project_id}/files", response_model=list[FileTreeResponse])
def get_file_tree(project_id: str):
    with get_connection() as conn:
        proj = conn.execute(
            "SELECT workspace_path FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

    workspace = proj["workspace_path"]

    def build_tree(path: str):
        items = []
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            rel = os.path.relpath(full, workspace)
            if os.path.isdir(full):
                items.append(FileTreeResponse(path=rel, type="directory", children=build_tree(full)))
            else:
                items.append(FileTreeResponse(path=rel, type="file"))
        return items

    return build_tree(workspace)