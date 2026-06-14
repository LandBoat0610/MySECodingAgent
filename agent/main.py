# flake8: noqa: E402
# main.py
import os
from dotenv import load_dotenv
load_dotenv()

from agent.backend.utils import sync_workspace_file_back
from agent.backend.graph import build_graph, run_manual_fallback
from agent.backend.llm import fallback_session_title, generate_session_title
import threading
import uuid
import json
import asyncio
from typing import Any, Dict
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from agent.backend.database import init_db, get_connection
from agent.backend.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
    SessionActionResponse,
    StateResponse,
    ChatRequest,
    ChatResponse,
    ConversationRoundResponse,
    PlanResponse,
    PlanActionRequest,
    PlanActionResponse,
    CommandApprovalRequest,
    CommandApprovalResponse,
    LoopApprovalRequest,
    LoopApprovalResponse,
    FileTreeResponse,
    FileContentResponse,
    AgentConfigResponse,
    AgentConfigUpdateRequest,
    ToolSettingsResponse,
    ToolSettingsUpdateRequest,
    SkillCreateRequest,
    SkillUpdateRequest,
    SkillItem,
    SkillListResponse,
)
from agent.backend.platform_settings import (
    get_agent_config,
    set_agent_config,
    get_tool_settings,
    get_registered_tools,
    set_tool_settings,
    get_skills,
    create_skill,
    update_skill,
    delete_skill,
)
from agent.backend.eval_router import router as eval_router
from agent.backend.session_manager import (
    get_memory_context,
    save_project_memory,
    list_project_memory,
    get_user_preferences,
    save_user_preference,
    list_user_preferences,
    get_relevant_history,
)


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(eval_router)


@app.get("/health")
def health_check():
    """健康检查端点 - 用于 Docker 健康检查和 CI/CD 部署验证"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ------------------ 平台 Agent 配置（IDE 与评测中心共用）------------------


@app.get("/settings/agent-config", response_model=AgentConfigResponse)
def read_agent_config():
    cfg = get_agent_config()
    return AgentConfigResponse(
        model=cfg.get("model", ""),
        version_label=cfg.get("version_label") or "",
        cross_session_enabled=cfg.get("cross_session_enabled", True),
    )


@app.put("/settings/agent-config", response_model=AgentConfigResponse)
def update_agent_config(req: AgentConfigUpdateRequest):
    payload = {}
    if req.model is not None:
        payload["model"] = req.model
    if req.version_label is not None:
        payload["version_label"] = req.version_label
    if req.cross_session_enabled is not None:
        payload["cross_session_enabled"] = req.cross_session_enabled
    if not payload:
        cfg = get_agent_config()
        return AgentConfigResponse(
            model=cfg.get("model", ""),
            version_label=cfg.get("version_label") or "",
            cross_session_enabled=cfg.get("cross_session_enabled", True),
        )
    cfg = set_agent_config(payload)
    return AgentConfigResponse(
        model=cfg.get("model", ""),
        version_label=cfg.get("version_label") or "",
        cross_session_enabled=cfg.get("cross_session_enabled", True),
    )


@app.get("/settings/tools", response_model=ToolSettingsResponse)
def read_tool_settings():
    settings = get_tool_settings()
    descriptions = {tool["name"]: tool.get("description", "") for tool in get_registered_tools()}
    return ToolSettingsResponse(
        tools=[
            {
                "name": name,
                "enabled": enabled,
                "description": descriptions.get(name, ""),
            }
            for name, enabled in settings.items()
        ]
    )


@app.put("/settings/tools", response_model=ToolSettingsResponse)
def update_tool_settings(req: ToolSettingsUpdateRequest):
    settings = set_tool_settings(req.tools)
    descriptions = {tool["name"]: tool.get("description", "") for tool in get_registered_tools()}
    return ToolSettingsResponse(
        tools=[
            {
                "name": name,
                "enabled": enabled,
                "description": descriptions.get(name, ""),
            }
            for name, enabled in settings.items()
        ]
    )


@app.get("/settings/skills", response_model=SkillListResponse)
def read_skills():
    return SkillListResponse(skills=[SkillItem(**skill) for skill in get_skills()])


@app.post("/settings/skills", response_model=SkillItem, status_code=201)
def create_skill_endpoint(req: SkillCreateRequest):
    try:
        return SkillItem(**create_skill(req.model_dump()))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.patch("/settings/skills/{skill_id}", response_model=SkillItem)
def update_skill_endpoint(skill_id: str, req: SkillUpdateRequest):
    try:
        return SkillItem(**update_skill(skill_id, req.model_dump(exclude_unset=True)))
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.delete("/settings/skills/{skill_id}")
def delete_skill_endpoint(skill_id: str):
    try:
        delete_skill(skill_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    return {"status": "deleted", "skill_id": skill_id}


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

# ------------------ 2.5 删除项目 ------------------


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    with get_connection() as conn:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

        sessions = conn.execute("SELECT id FROM sessions WHERE project_id = ?", (project_id,)).fetchall()
        session_ids = [s["id"] for s in sessions]

        for sid in session_ids:
            conn.execute(
                "DELETE FROM plan_actions WHERE plan_id IN (SELECT id FROM plans WHERE session_id = ?)",
                (sid,),
            )
            conn.execute("DELETE FROM plans WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM conversation_rounds WHERE session_id = ?", (sid,))

        conn.execute("DELETE FROM sessions WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    for sid in session_ids:
        cleanup_cancel_event(sid)
        runner = _agent_runners.pop(sid, None)
        if runner and runner.is_alive():
            runner.cancel_event.set()

    return {"status": "deleted", "project_id": project_id}

# ------------------ 3. 获取会话列表 ------------------


@app.get("/projects/{project_id}/sessions", response_model=list[SessionResponse])
def list_sessions(project_id: str):
    with get_connection() as conn:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")
        rows = conn.execute(
            "SELECT id, project_id, title, created_at, status, pinned "
            "FROM sessions WHERE project_id = ? ORDER BY pinned DESC, created_at DESC",
            (project_id,),
        ).fetchall()
    sessions = []
    for row in rows:
        data = dict(row)
        data["pinned"] = bool(data.get("pinned", False))
        sessions.append(data)
    return sessions

# ------------------ 4. 新建会话 ------------------


@app.post("/projects/{project_id}/sessions", response_model=SessionResponse, status_code=201)
def create_session(project_id: str, req: SessionCreateRequest):
    now = datetime.now().isoformat()
    session_id = uuid.uuid4().hex[:8]
    requested_title = (req.title or "").strip()
    should_generate_title = bool(req.initial_message and not requested_title)
    if requested_title:
        title = requested_title
    elif req.initial_message:
        title = fallback_session_title(req.initial_message)
    else:
        title = "New Session"

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
            "project_root": proj["workspace_path"],
            "trace": [],
            "runtime_metrics": {
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "llm_calls": 0,
                "tool_calls": [],
            },
            "current_round_id": "",
            "pending_tool_approval": None,
            "pending_loop_approval": None,
        }

        conn.execute(
            "INSERT INTO sessions "
            "(id, project_id, title, created_at, state_snapshot, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, project_id, title, now, json.dumps(initial_state, ensure_ascii=False), "idle"),
        )

    if should_generate_title:
        threading.Thread(
            target=_generate_and_save_session_title,
            args=(project_id, session_id, req.initial_message),
            daemon=True,
        ).start()

    return SessionResponse(
        id=session_id,
        project_id=project_id,
        title=title,
        created_at=now,
        status="idle",
        pinned=False,
    )


@app.patch("/projects/{project_id}/sessions/{sid}", response_model=SessionResponse)
def update_session(project_id: str, sid: str, req: SessionUpdateRequest):
    fields = []
    values = []
    if req.title is not None:
        title = req.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="会话标题不能为空")
        fields.append("title = ?")
        values.append(title)
    if req.pinned is not None:
        fields.append("pinned = ?")
        values.append(1 if req.pinned else 0)
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")
        conn.execute(
            f"UPDATE sessions SET {', '.join(fields)} WHERE id = ? AND project_id = ?",
            (*values, sid, project_id),
        )
        updated = conn.execute(
            "SELECT id, project_id, title, created_at, status, pinned FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()

    data = dict(updated)
    data["pinned"] = bool(data["pinned"])
    return SessionResponse(**data)


@app.delete("/projects/{project_id}/sessions/{sid}", response_model=SessionActionResponse)
def delete_session(project_id: str, sid: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")
        conn.execute("DELETE FROM plan_actions WHERE plan_id IN (SELECT id FROM plans WHERE session_id = ?)", (sid,))
        conn.execute("DELETE FROM plans WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM conversation_rounds WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM sessions WHERE id = ? AND project_id = ?", (sid, project_id))

    cleanup_cancel_event(sid)
    runner = _agent_runners.pop(sid, None)
    if runner and runner.is_alive():
        runner.cancel_event.set()
    return SessionActionResponse(status="deleted", session_id=sid)


@app.post("/projects/{project_id}/sessions/{sid}/clear", response_model=SessionActionResponse)
def clear_session(project_id: str, sid: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")
        state = json.loads(row["state_snapshot"])
        state.update({
            "task": "",
            "messages": [],
            "status": "idle",
            "errors": [],
            "used_tools": [],
            "result_history": [],
            "modified_files": [],
            "task_list": [],
            "current_task_index": 0,
            "current_task": "",
            "last_tool_result": {},
            "last_execution": {},
            "final_answer": "",
            "trace": [],
            "runtime_metrics": {
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "llm_calls": 0,
                "tool_calls": [],
            },
            "current_round_id": "",
            "pending_tool_approval": None,
            "pending_loop_approval": None,
        })
        conn.execute("DELETE FROM plan_actions WHERE plan_id IN (SELECT id FROM plans WHERE session_id = ?)", (sid,))
        conn.execute("DELETE FROM plans WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM conversation_rounds WHERE session_id = ?", (sid,))
        conn.execute(
            "UPDATE sessions SET state_snapshot = ?, status = 'idle' WHERE id = ? AND project_id = ?",
            (json.dumps(state, ensure_ascii=False), sid, project_id),
        )

    cleanup_cancel_event(sid)
    runner = _agent_runners.pop(sid, None)
    if runner and runner.is_alive():
        runner.cancel_event.set()
    return SessionActionResponse(status="cleared", session_id=sid)


def _generate_and_save_session_title(project_id: str, session_id: str, message: str) -> None:
    title = generate_session_title(message)
    if not title:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ? AND project_id = ?",
                (title, session_id, project_id),
            )
    except Exception as e:
        print(f"Warning: failed to generate session title for {session_id}: {e}")

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
    now = datetime.now().isoformat()
    round_id = uuid.uuid4().hex[:8]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")
        row_data = dict(row)
        if row_data.get("status") == "stopped":
            raise HTTPException(status_code=409, detail="会话已停止，请新建对话后继续")

        state = json.loads(row_data["state_snapshot"])
        state["task"] = req.message
        state["messages"].append({"role": "user", "content": req.message})
        state["status"] = "running"
        state["current_round_id"] = round_id
        state["trace"] = []
        state["final_answer"] = ""
        state["result_history"] = []
        state["errors"] = []
        state["used_tools"] = []
        state["modified_files"] = []
        state["task_list"] = []
        state["current_task_index"] = 0
        state["current_task"] = ""
        state["last_tool_result"] = {}
        state["last_execution"] = {}
        state["task_type"] = ""
        state["task_difficulty"] = ""
        state["current_plan"] = []
        state["acceptance_criteria"] = []
        state["relevant_files"] = []
        state["retrieved_context"] = []
        state["codebase_summary"] = ""
        state["test_commands"] = []
        state["tool_history"] = []
        state["verification_results"] = []
        state["patch_history"] = []
        state["failure_reason"] = ""
        state["retry_count"] = 0
        state["last_review"] = {}
        state["pending_tool_approval"] = None
        state["pending_loop_approval"] = None
        state["runtime_metrics"] = {
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "llm_calls": 0,
            "tool_calls": [],
        }

        conn.execute(
            """INSERT INTO conversation_rounds
               (id, session_id, project_id, user_message, status, created_at)
               VALUES (?, ?, ?, ?, 'running', ?)""",
            (round_id, sid, project_id, req.message, now),
        )

        conn.execute(
            "UPDATE sessions SET state_snapshot = ?, status = ? WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), "running", sid),
        )

    return ChatResponse(
        session_id=sid,
        reply="消息已接收，Agent 开始处理...",
        status="running",
        round_id=round_id,
    )


# ------------------ 7. WebSocket 流式对话 ------------------

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
            if self.run_id == my_run_id:
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT status FROM sessions WHERE id = ?",
                        (self.sid,),
                    ).fetchone()
                    if row and row["status"] in ("running", "awaiting_approval", "needs_fix", "next_step"):
                        conn.execute(
                            "UPDATE sessions SET status = 'completed' "
                            "WHERE id = ? AND status NOT IN ('stopped', 'skipped')",
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

    # 以 sid 为 key 注册，自动替换同会话的旧回调，消除重连后重复推送
    from agent.backend.utils import register_log_callback
    register_log_callback(on_log, session_id=sid)

    if need_start:
        runner.start(state)

    try:
        if runner.started.is_set():
            await websocket.send_json({"phase": "start", "message": "Agent 正在执行..."})

        while not runner.done.is_set():
            if runner.cancel_event.is_set():
                await websocket.send_json({
                    "phase": "cancelled",
                    "message": "任务已停止",
                    "status": "stopped",
                })
                return
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT status FROM sessions WHERE id = ?",
                    (sid,),
                ).fetchone()
            if row and row["status"] == "stopped":
                runner.cancel_event.set()
                await websocket.send_json({
                    "phase": "cancelled",
                    "message": "任务已停止",
                    "status": "stopped",
                })
                return
            await asyncio.sleep(0.5)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT state_snapshot FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        final_state = json.loads(row["state_snapshot"]) if row else {}

        if final_state.get("status") == "stopped":
            await websocket.send_json({
                "phase": "cancelled",
                "message": "任务已停止",
                "final_answer": final_state.get("final_answer", ""),
                "status": "stopped",
            })
        else:
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
        from agent.backend.utils import unregister_log_callback
        unregister_log_callback(on_log, session_id=sid)
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
            "SELECT *, rowid FROM plans WHERE session_id = ? ORDER BY rowid ASC",
            (sid,),
        ).fetchall()
        round_refs = conn.execute(
            "SELECT id, created_at FROM conversation_rounds WHERE session_id = ? ORDER BY created_at ASC",
            (sid,),
        ).fetchall()

    current_round_id = ""
    try:
        snapshot = json.loads(row["state_snapshot"] or "{}")
        current_round_id = snapshot.get("current_round_id") or ""
    except Exception:
        current_round_id = ""

    out = []
    all_round_items = [dict(r) for r in round_refs]
    for plan in plans:
        item = dict(plan)
        if current_round_id and not item.get("round_id") and item.get("status") == "pending":
            item["round_id"] = current_round_id
        if not item.get("round_id"):
            plan_created_at = item.get("created_at") or ""
            for idx, round_item in enumerate(all_round_items):
                current_created = round_item.get("created_at") or ""
                next_created = all_round_items[idx + 1].get("created_at") if idx + 1 < len(all_round_items) else None
                if plan_created_at >= current_created and (not next_created or plan_created_at < next_created):
                    item["round_id"] = round_item["id"]
                    break
        out.append(item)
    return out


@app.get("/projects/{project_id}/sessions/{sid}/rounds", response_model=list[ConversationRoundResponse])
def list_conversation_rounds(project_id: str, sid: str, limit: int = 8, before: str = ""):
    limit = max(1, min(int(limit or 8), 50))
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        if before:
            rounds = conn.execute(
                """SELECT * FROM conversation_rounds
                   WHERE session_id = ? AND created_at < ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (sid, before, limit),
            ).fetchall()
        else:
            rounds = conn.execute(
                """SELECT * FROM conversation_rounds
                   WHERE session_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (sid, limit),
            ).fetchall()
        rounds = list(reversed(rounds))
        round_refs = conn.execute(
            "SELECT id, created_at FROM conversation_rounds WHERE session_id = ? ORDER BY created_at ASC",
            (sid,),
        ).fetchall()
        plans = conn.execute(
            "SELECT *, rowid FROM plans WHERE session_id = ? ORDER BY rowid ASC",
            (sid,),
        ).fetchall()

    plans_by_round: Dict[str, list[dict]] = {}
    round_items = [dict(row) for row in rounds]
    all_round_items = [dict(row) for row in round_refs]
    for plan in plans:
        item = dict(plan)
        plan_round_id = item.get("round_id") or ""
        if not plan_round_id:
            # Backfill display ownership for older plan rows created before round_id existed.
            plan_created_at = item.get("created_at") or ""
            for idx, round_item in enumerate(all_round_items):
                current_created = round_item.get("created_at") or ""
                next_created = all_round_items[idx + 1].get("created_at") if idx + 1 < len(all_round_items) else None
                if plan_created_at >= current_created and (not next_created or plan_created_at < next_created):
                    plan_round_id = round_item["id"]
                    break
        if plan_round_id:
            plans_by_round.setdefault(plan_round_id, []).append(item)

    out = []
    for item in round_items:
        try:
            item["trace_json"] = json.loads(item.get("trace_json") or "[]")
        except json.JSONDecodeError:
            item["trace_json"] = []
        try:
            item["runtime_metrics_json"] = json.loads(item.get("runtime_metrics_json") or "{}")
        except json.JSONDecodeError:
            item["runtime_metrics_json"] = {}
        item["plans"] = plans_by_round.get(item["id"], [])
        out.append(item)
    return out

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
            "refine": "skipped",
            "skip": "skipped",
            "stop": "stopped",
        }
        new_status = status_map.get(req.action, "pending")
        session_status = "refining" if req.action == "refine" else new_status
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
        if req.action == "refine":
            feedback = (req.feedback or "").strip()
            state = json.loads(row["state_snapshot"] or "{}")
            state["plan_feedback"] = feedback
            conn.execute(
                "UPDATE sessions SET state_snapshot = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), sid),
            )
            conn.execute(
                "UPDATE plans SET status = 'skipped' WHERE session_id = ? AND status IN ('pending', 'refining')",
                (sid,),
            )
        if req.action in ("skip", "stop"):
            state = json.loads(row["state_snapshot"] or "{}")
            round_id = state.get("current_round_id")
            if round_id:
                conn.execute(
                    "UPDATE conversation_rounds SET status = ?, finished_at = ? WHERE id = ?",
                    (session_status, datetime.now().isoformat(), round_id),
                )
        conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?",
            (session_status, sid),
        )

    if req.action == "stop":
        get_cancel_event(sid).set()

    return PlanActionResponse(
        plan_id=pid,
        action=req.action,
        status=new_status,
    )


@app.post("/projects/{project_id}/sessions/{sid}/command-approval", response_model=CommandApprovalResponse)
def command_approval(project_id: str, sid: str, req: CommandApprovalRequest):
    action = (req.action or "").strip().lower()
    if action not in ("approve", "reject", "revise"):
        raise HTTPException(status_code=400, detail="action 须为 approve、reject 或 revise")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        state = json.loads(row["state_snapshot"] or "{}")
        pending = state.get("pending_tool_approval") or {}
        if pending.get("id") != req.approval_id or pending.get("status") != "pending":
            raise HTTPException(status_code=409, detail="没有匹配的待确认命令")

        next_status = {
            "approve": "approved",
            "reject": "rejected",
            "revise": "revision_requested",
        }[action]
        pending["status"] = next_status
        pending["feedback"] = (req.feedback or "").strip()
        state["pending_tool_approval"] = pending
        state["status"] = "running"
        conn.execute(
            "UPDATE sessions SET state_snapshot = ?, status = 'running' WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), sid),
        )

    return CommandApprovalResponse(
        approval_id=req.approval_id,
        action=action,
        status=next_status,
    )


@app.post("/projects/{project_id}/sessions/{sid}/continue-approval", response_model=LoopApprovalResponse)
def continue_approval(project_id: str, sid: str, req: LoopApprovalRequest):
    action = (req.action or "").strip().lower()
    if action not in ("continue", "stop"):
        raise HTTPException(status_code=400, detail="action 须为 continue 或 stop")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND project_id = ?",
            (sid, project_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在于该项目下")

        state = json.loads(row["state_snapshot"] or "{}")
        pending = state.get("pending_loop_approval") or {}
        if pending.get("id") != req.approval_id or pending.get("status") != "pending":
            raise HTTPException(status_code=409, detail="没有匹配的待确认继续请求")

        next_status = "continued" if action == "continue" else "stopped"
        pending["status"] = next_status
        state["pending_loop_approval"] = pending
        state["status"] = "running" if action == "continue" else "stopped"
        conn.execute(
            "UPDATE sessions SET state_snapshot = ?, status = ? WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), state["status"], sid),
        )

    if action == "stop":
        get_cancel_event(sid).set()

    return LoopApprovalResponse(
        approval_id=req.approval_id,
        action=action,
        status=next_status,
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
        state = json.loads(row["state_snapshot"] or "{}")
        round_id = state.get("current_round_id")
        if round_id:
            conn.execute(
                "UPDATE conversation_rounds SET status = 'stopped', finished_at = ? WHERE id = ?",
                (datetime.now().isoformat(), round_id),
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


# ------------------ 10.5 获取项目文件内容 ------------------
@app.get("/projects/{project_id}/files/content", response_model=FileContentResponse)
def get_file_content(project_id: str, path: str):
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="文件路径不能为空")

    with get_connection() as conn:
        proj = conn.execute(
            "SELECT workspace_path FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

    workspace = os.path.abspath(proj["workspace_path"])
    full_path = os.path.abspath(os.path.join(workspace, path))

    if not str(full_path).startswith(str(workspace) + os.sep) and full_path != workspace:
        raise HTTPException(status_code=403, detail="路径超出项目工作区范围")

    if full_path == workspace or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    size = os.path.getsize(full_path)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大，超过 10MB 限制")

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return FileContentResponse(path=path, content=content, size=size, encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="文件非文本格式，无法预览")


# ── RAG 知识增强 API ──────────────────────────────────
@app.post("/rag/ingest")
def rag_ingest(project_id: str):
    """将项目工作区中的文档入库到知识库。"""
    with get_connection() as conn:
        proj = conn.execute(
            "SELECT workspace_path FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

    from agent.backend.rag import auto_ingest_workspace
    result = auto_ingest_workspace(proj["workspace_path"])
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "入库失败"))
    return result


@app.get("/rag/search")
def rag_search_api(query: str, top_k: int = 5):
    """直接搜索知识库（主要用于调试，Agent 通过 tool 调用 rag_search）。"""
    from agent.backend.rag import rag_search
    return rag_search(query, top_k)


@app.get("/rag/stats")
def rag_stats_api():
    """返回知识库统计信息。"""
    from agent.backend.rag import get_rag_stats
    return get_rag_stats()


# ── 跨对话记忆与上下文工程 API ────────────────────────────────────


@app.get("/projects/{project_id}/memory/context")
def memory_context_api(project_id: str, session_id: str = ""):
    """获取完整记忆上下文，用于 Agent 初始化。"""
    return get_memory_context(project_id, session_id)


@app.get("/projects/{project_id}/memory")
def list_memory_api(project_id: str):
    """列出项目所有记忆条目。"""
    return list_project_memory(project_id)


@app.post("/projects/{project_id}/memory")
def save_memory_api(project_id: str, key: str = Form(...), value: str = Form(...), category: str = Form("general")):
    """保存一条项目记忆。"""
    ok = save_project_memory(project_id, key, value, category)
    if not ok:
        raise HTTPException(status_code=500, detail="保存记忆失败")
    return {"success": True, "key": key, "category": category}


@app.get("/projects/{project_id}/history")
def history_api(project_id: str, query: str = "", limit: int = 5):
    """检索项目历史对话。"""
    return get_relevant_history(project_id, query, limit)


@app.get("/preferences")
def get_preferences_api():
    """获取用户偏好列表。"""
    return list_user_preferences()


@app.post("/preferences")
def save_preference_api(key: str = Form(...), value: str = Form(...)):
    """保存一条用户偏好。"""
    ok = save_user_preference(key, value)
    if not ok:
        raise HTTPException(status_code=500, detail="保存偏好失败")
    return {"success": True, "key": key}
