# tests/test_main.py
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, ANY
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect

# ---------- 确保项目根目录在 sys.path 中 ----------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ---------- 设置环境变量，避免无法导入 agent 内部模块 ----------
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")

# ---------- 提前 mock 所有数据库和 agent 依赖，防止 import 时意外初始化 ----------
with patch("agent.backend.database.get_connection") as mock_db_conn, \
     patch("agent.backend.database.init_db"), \
     patch("agent.backend.graph.build_graph"), \
     patch("agent.backend.graph.run_manual_fallback"), \
     patch("agent.backend.utils.sync_workspace_file_back"), \
     patch("agent.backend.utils.register_log_callback"), \
     patch("agent.backend.utils.unregister_log_callback"):
    from agent.main import app

# 创建 TestClient
client = TestClient(app)


# ==================== Fixtures ====================
@pytest.fixture
def mock_db():
    """提供模拟的数据库连接和游标"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None
    mock_conn.execute.return_value = mock_cursor
    return mock_conn, mock_cursor


# ==================== 1. Projects ====================
class TestProjects:
    def test_list_projects_empty(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = []  # 空列表
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_projects_with_data(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = [
            {"id": "p1", "name": "Proj1", "workspace_path": "/path", "created_at": "2026-01-01", "description": "desc"}
        ]
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "p1"

    def test_create_project_new(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 模拟 uuid 生成固定值
        with patch("agent.main.uuid.uuid4") as mock_uuid, \
             patch("agent.main.os.makedirs") as mock_makedirs, \
             patch("agent.main.get_connection", return_value=mock_conn):
            mock_uuid.return_value.hex = "1a2b3c4d"
            mock_cursor.fetchone.return_value = None  # 不查询

            response = client.post("/projects", json={
                "name": "Test Project",
                "description": "A test"
            })
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "1a2b3c4d"
            assert data["name"] == "Test Project"
            assert data["workspace_path"].endswith("project_1a2b3c4d")
            mock_makedirs.assert_called_once()

    def test_create_project_open_existing(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 指定已存在路径
        existing_path = os.path.abspath("/existing_workspace")
        with patch("agent.main.os.path.isdir", return_value=True), \
             patch("agent.main.uuid.uuid4") as mock_uuid, \
             patch("agent.main.get_connection", return_value=mock_conn):
            mock_uuid.return_value.hex = "opened01"
            response = client.post("/projects", json={
                "name": "Existing",
                "workspace_path": existing_path
            })
            assert response.status_code == 201
            data = response.json()
            assert data["workspace_path"] == existing_path

    def test_create_project_open_nonexistent(self):
        # 路径不存在应返回 400
        response = client.post("/projects", json={
            "name": "Bad",
            "workspace_path": "/nonexistent/dir"
        })
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]


# ==================== 2. Sessions ====================
class TestSessions:
    def test_list_sessions_project_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/badid/sessions")
            assert response.status_code == 404

    def test_list_sessions_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 先返回项目存在，再返回会话列表
        mock_cursor.fetchone.side_effect = [{"id": "p1"}, None]  # 第二次调用是 list 查询
        mock_cursor.fetchall.return_value = [
            {"id": "s1", "project_id": "p1", "title": "Session1", "created_at": "now", "status": "idle"}
        ]
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/sessions")
            assert response.status_code == 200
            assert len(response.json()) == 1

    def test_create_session_project_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.post("/projects/badid/sessions", json={"title": "New"})
            assert response.status_code == 404

    def test_create_session_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 模拟项目存在，返回 workspace_path
        mock_cursor.fetchone.return_value = {"id": "p1", "workspace_path": "/workspace/p1"}
        with patch("agent.main.uuid.uuid4") as mock_uuid, \
             patch("agent.main.get_connection", return_value=mock_conn):
            mock_uuid.return_value.hex = "sess001"
            response = client.post("/projects/p1/sessions", json={"title": "My Session"})
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "sess001"
            assert data["title"] == "My Session"
            assert data["status"] == "idle"
            # 检查 INSERT 被调用且 state_snapshot 中包含 workspace_dir
            call_args = mock_conn.execute.call_args_list[1]  # 第一个是查询，第二个是插入
            # 寻找包含 "INSERT INTO sessions" 的调用
            insert_call = None
            for call in mock_conn.execute.call_args_list:
                if "INSERT INTO sessions" in call[0][0]:
                    insert_call = call
                    break
            assert insert_call is not None, "Should have called INSERT INTO sessions"
            # 检查传入的 state_snapshot JSON
            snapshot = json.loads(insert_call[0][1][4])  # 第五个参数是 state_snapshot
            assert snapshot["workspace_dir"] == "/workspace/p1"


# ==================== 3. State ====================
class TestState:
    def test_get_state_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/sessions/s1/state")
            assert response.status_code == 404

    def test_get_state_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = {
            "id": "s1",
            "project_id": "p1",
            "status": "running",
            "state_snapshot": json.dumps({"task": "hello", "status": "running"})
        }
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/sessions/s1/state")
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "s1"
            assert data["status"] == "running"
            assert data["snapshot"]["task"] == "hello"


# ==================== 4. Chat (HTTP) ====================
class TestChat:
    def test_chat_session_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.post("/projects/p1/sessions/s1/chat", json={"message": "Hello"})
            assert response.status_code == 404

    def test_chat_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        original_state = {
            "task": "",
            "messages": [],
            "status": "idle"
        }
        mock_cursor.fetchone.return_value = {
            "id": "s1",
            "project_id": "p1",
            "state_snapshot": json.dumps(original_state)
        }
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.post("/projects/p1/sessions/s1/chat", json={"message": "Do something"})
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "s1"
            assert data["status"] == "running"
            # 验证数据库状态更新被调用，且 messages 添加了用户消息
            update_call = mock_conn.execute.call_args_list[1]  # 第一个是 select，第二个是 update
            assert "UPDATE sessions" in update_call[0][0]
            new_state = json.loads(update_call[0][1][0])
            assert new_state["task"] == "Do something"
            assert new_state["messages"][-1] == {"role": "user", "content": "Do something"}


# ==================== 5. WebSocket (简化版) ====================
class TestWebSocket:
    def test_websocket_connect_and_immediate_error(self, mock_db):
        # 模拟会话不存在
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn), \
             patch("agent.main.build_graph"), \
             patch("agent.main.run_manual_fallback"):
            with client.websocket_connect("/projects/p1/sessions/s1/chat/stream") as websocket:
                data = websocket.receive_json()
                assert "error" in data
                # 由于代码中 WebSocket 会关闭，可能引发异常，捕获即可
                try:
                    websocket.close()
                except WebSocketDisconnect:
                    pass

    # 更完整的 WebSocket 测试可以通过 mock 整个 agent 运行流程进行，但所需模拟较多，此处略作示范


# ==================== 6. Plan ====================
class TestPlan:
    def test_get_plan_session_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/sessions/s1/plan")
            assert response.status_code == 404

    def test_get_plan_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 首次 fetchone 返回会话存在
        mock_cursor.fetchone.return_value = {"id": "s1", "project_id": "p1"}
        mock_cursor.fetchall.return_value = [
            {"id": "plan1", "session_id": "s1", "content": "plan content", "status": "pending", "created_at": "now"}
        ]
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/sessions/s1/plan")
            assert response.status_code == 200
            plans = response.json()
            assert len(plans) == 1
            assert plans[0]["id"] == "plan1"

    def test_plan_action_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        # 会话存在，但计划不存在
        mock_cursor.fetchone.side_effect = [
            {"id": "s1", "project_id": "p1"},  # 会话存在
            None  # 计划不存在
        ]
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.post("/projects/p1/sessions/s1/plan/plan1/action", json={"action": "agree"})
            assert response.status_code == 404

    def test_plan_action_success(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.side_effect = [
            {"id": "s1", "project_id": "p1"},  # 会话
            {"id": "plan1", "session_id": "s1", "status": "pending"}  # 计划
        ]
        with patch("agent.main.uuid.uuid4") as mock_uuid, \
             patch("agent.main.get_connection", return_value=mock_conn):
            mock_uuid.return_value.hex = "act001"
            response = client.post("/projects/p1/sessions/s1/plan/plan1/action", json={"action": "agree"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"
            # 验证 INSERT 和 UPDATE 被调用
            # 可以检查 execute 调用次数等


# ==================== 7. File Tree ====================
class TestFileTree:
    def test_file_tree_project_not_found(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = None
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/badid/files")
            assert response.status_code == 404

    def test_file_tree_success(self, mock_db, tmp_path):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = {"workspace_path": str(tmp_path)}
        # 创建一些文件
        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.py").write_text("print(1)")
        with patch("agent.main.get_connection", return_value=mock_conn):
            response = client.get("/projects/p1/files")
            assert response.status_code == 200
            tree = response.json()
            # 简单检查返回的列表包含两个元素
            assert len(tree) == 2
            names = [item["path"] for item in tree]
            assert "file1.txt" in names
            assert "subdir" in names
            # 检查目录类型和 children
            for item in tree:
                if item["path"] == "subdir":
                    assert item["type"] == "directory"
                    assert len(item["children"]) == 1