# main.py
import os
import uuid
import json
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
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
    AgentConfigResponse,
    AgentConfigUpdateRequest,
)
from agent.backend.utils import ensure_workspace
from agent.backend.platform_settings import get_agent_config, set_agent_config
from agent.backend.eval_router import router as eval_router

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)
app.include_router(eval_router)

# ------------------ 平台 Agent 配置（IDE 与评测中心共用）------------------
@app.get("/settings/agent-config", response_model=AgentConfigResponse)
def read_agent_config():
    cfg = get_agent_config()
    return AgentConfigResponse(model=cfg.get("model", ""), version_label=cfg.get("version_label") or "")


@app.put("/settings/agent-config", response_model=AgentConfigResponse)
def update_agent_config(req: AgentConfigUpdateRequest):
    payload = {}
    if req.model is not None:
        payload["model"] = req.model
    if req.version_label is not None:
        payload["version_label"] = req.version_label
    if not payload:
        cfg = get_agent_config()
        return AgentConfigResponse(model=cfg.get("model", ""), version_label=cfg.get("version_label") or "")
    cfg = set_agent_config(payload)
    return AgentConfigResponse(model=cfg.get("model", ""), version_label=cfg.get("version_label") or "")


WORKSPACES_ROOT = os.path.abspath("workspaces")
os.makedirs(WORKSPACES_ROOT, exist_ok=True)

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
        workspace = os.path.abspath(req.workspace_path)
        if not os.path.isdir(workspace):
            raise HTTPException(status_code=400, detail="指定的工作区路径不存在")
    else:
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

        initial_state = {
            "session_id": session_id,
            "project_id": project_id,
            "task": "",
            "messages": [],
            "workspace_dir": proj["workspace_path"],
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
            "project_root": proj["workspace_path"],
            "trace": [],
            "runtime_metrics": {
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "llm_calls": 0,
                "tool_calls": [],
            },
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

# ------------------ 7. WebSocket 流式对话 ------------------
import threading
from agent.backend.graph import build_graph, run_manual_fallback
from agent.backend.utils import sync_workspace_file_back, register_log_callback, unregister_log_callback

_cancel_events: Dict[str, threading.Event] = {}

def get_cancel_event(sid: str) -> threading.Event:
    if sid not in _cancel_events:
        _cancel_events[sid] = threading.Event()
    return _cancel_events[sid]

def cleanup_cancel_event(sid: str):
    _cancel_events.pop(sid, None)


class AgentRunner:
    def __init__(self, sid: str):
        self.sid = sid
        self.run_id: str = ""
        self.cancel_event = get_cancel_event(sid)
        self._ws_ref: Any = None
        self._ws_loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.done = threading.Event()
        self.started = threading.Event()

    def set_ws(self, ws, loop: asyncio.AbstractEventLoop):
        with self._lock:
            self._ws_ref = ws
            self._ws_loop = loop

    def clear_ws_if_same(self, ws):
        with self._lock:
            if self._ws_ref is ws:
                self._ws_ref = None
                self._ws_loop = None

    def send_to_ws(self, item: dict):
        with self._lock:
            if self._ws_ref is None or self._ws_loop is None:
                return
            ws = self._ws_ref
            loop = self._ws_loop
        try:
            if not loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    ws.send_json(item), loop
                )
                future.add_done_callback(lambda f, w=ws: self._on_send_done(f, w))
        except Exception:
            pass

    def _on_send_done(self, future, ws_sent):
        try:
            future.result()
        except Exception:
            with self._lock:
                if self._ws_ref is ws_sent:
                    self._ws_ref = None
                    self._ws_loop = None

    def start(self, state: dict):
        if self._thread and self._thread.is_alive():
            return False
        self.cancel_event.clear()
        self.done.clear()
        self.started.clear()
        self.run_id = uuid.uuid4().hex[:8]
        self._thread = threading.Thread(target=self._run, args=(state,), daemon=True)
        self._thread.start()
        self.started.wait(timeout=2.0)
        return True

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self, state: dict):
        my_run_id = self.run_id
        self.started.set()
        try:
            state["_cancel_event"] = self.cancel_event
            graph = build_graph()
            if graph:
                final_state = graph.invoke(state)
            else:
                final_state = run_manual_fallback(state)
            sync_workspace_file_back(final_state)
        except Exception as e:
            print(f"Agent runner error: {e}")
        finally:
            self.done.set()
            if self.run_id != my_run_id:
                return
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT status FROM sessions WHERE id = ?",
                    (self.sid,),
                ).fetchone()
                if row and row["status"] in ("running", "awaiting_approval", "needs_fix", "next_step"):
                    conn.execute(
                        "UPDATE sessions SET status = 'completed' WHERE id = ? AND status NOT IN ('stopped', 'skipped')",
                        (self.sid,),
                    )
            cleanup_cancel_event(self.sid)


_agent_runners: Dict[str, AgentRunner] = {}

def get_or_create_agent_runner(sid: str) -> AgentRunner:
    existing = _agent_runners.get(sid)
    if existing and not existing.is_alive() and existing.done.is_set():
        del _agent_runners[sid]
    if sid not in _agent_runners:
        _agent_runners[sid] = AgentRunner(sid)
    return _agent_runners[sid]

_shared_log_callbacks_lock = threading.Lock()


@app.websocket("/projects/{project_id}/sessions/{sid}/chat/stream")
async def chat_stream(websocket: WebSocket, project_id: str, sid: str):
    await websocket.accept()

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

    runner = get_or_create_agent_runner(sid)

    if runner.is_alive() and not runner.done.is_set():
        runner.set_ws(websocket, asyncio.get_running_loop())
        need_start = False
    else:
        if runner.done.is_set():
            runner = AgentRunner(sid)
            _agent_runners[sid] = runner
        runner.set_ws(websocket, asyncio.get_running_loop())
        need_start = True

    def on_log(item):
        runner.send_to_ws({"type": "trace", "data": item})

    from agent.backend.utils import _LOG_CALLBACKS
    with _shared_log_callbacks_lock:
        _LOG_CALLBACKS.append(on_log)

    if need_start:
        runner.start(state)

    try:
        if runner.started.is_set():
            await websocket.send_json({"phase": "start", "message": "Agent 正在执行..."})

        while not runner.done.is_set():
            await asyncio.sleep(0.5)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT state_snapshot FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        final_state = json.loads(row["state_snapshot"]) if row else {}

        await websocket.send_json({
            "phase": "done",
            "message": "任务完成",
            "final_answer": final_state.get("final_answer", ""),
            "status": final_state.get("status"),
        })
        await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        from agent.backend.utils import _LOG_CALLBACKS as cb_list
        with _shared_log_callbacks_lock:
            if on_log in cb_list:
                cb_list.remove(on_log)
        runner.clear_ws_if_same(websocket)
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
        if req.action == "agree":
            conn.execute(
                "UPDATE plans SET status = 'approved' WHERE session_id = ? AND status = 'pending'",
                (sid,),
            )
        elif req.action == "skip":
            conn.execute(
                "UPDATE plans SET status = 'skipped' WHERE session_id = ? AND status = 'pending'",
                (sid,),
            )
        elif req.action == "stop":
            conn.execute(
                "UPDATE plans SET status = 'stopped' WHERE session_id = ? AND status = 'pending'",
                (sid,),
            )
        conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?",
            (new_status, sid),
        )

    if req.action == "stop":
        get_cancel_event(sid).set()

    return PlanActionResponse(
        plan_id=pid,
        action=req.action,
        status=new_status,
    )

# ------------------ 9.5 停止会话运行 ------------------
@app.post("/projects/{project_id}/sessions/{sid}/stop")
def stop_session(project_id: str, sid: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        conn.execute(
            "UPDATE sessions SET status = 'stopped' WHERE id = ?",
            (sid,),
        )
        conn.execute(
            "UPDATE plans SET status = 'stopped' WHERE session_id = ? AND status = 'pending'",
            (sid,),
        )

    get_cancel_event(sid).set()

    runner = _agent_runners.get(sid)
    if runner:
        runner.cancel_event.set()

    return {"status": "stopped", "session_id": sid}

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
