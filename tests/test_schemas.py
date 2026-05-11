# tests/test_schemas.py
from agent.backend import schemas
import os
import sys
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量，避免 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")


# ---------- ProjectCreateRequest ----------
def test_project_create_defaults():
    p = schemas.ProjectCreateRequest(name="myproject")
    assert p.name == "myproject"
    assert p.description == ""
    assert p.workspace_path is None


def test_project_create_with_optional():
    p = schemas.ProjectCreateRequest(
        name="proj", description="desc", workspace_path="/home/user"
    )
    assert p.workspace_path == "/home/user"


def test_project_create_missing_name():
    with pytest.raises(ValidationError):
        schemas.ProjectCreateRequest(description="test")


# ---------- SessionCreateRequest ----------
def test_session_create_default_title():
    s = schemas.SessionCreateRequest()
    assert s.title == "New Session"


def test_session_create_custom_title():
    s = schemas.SessionCreateRequest(title="My custom session")
    assert s.title == "My custom session"


# ---------- Response models (serialisation) ----------
def test_project_response():
    resp = schemas.ProjectResponse(
        id="abc", name="x", workspace_path="/", created_at="now", description=""
    )
    data = resp.model_dump()
    assert data["id"] == "abc"


def test_session_response():
    resp = schemas.SessionResponse(
        id="s1", project_id="p1", title="Session 1", created_at="now", status="idle"
    )
    assert resp.status == "idle"


# ---------- PlanAction Enum ----------
def test_plan_actions_valid():
    assert schemas.PlanAction.agree == "agree"
    assert schemas.PlanAction.refine == "refine"


def test_plan_action_request():
    req = schemas.PlanActionRequest(action=schemas.PlanAction.skip)
    assert req.action == schemas.PlanAction.skip


def test_plan_action_request_invalid():
    with pytest.raises(ValidationError):
        schemas.PlanActionRequest(action="invalid")


# ---------- FileTreeResponse recursion ----------
def test_file_tree_basic():
    file_node = schemas.FileTreeResponse(path="/a.txt", type="file")
    assert file_node.children is None


def test_file_tree_nested():
    tree = schemas.FileTreeResponse(
        path="/dir",
        type="directory",
        children=[
            schemas.FileTreeResponse(path="/dir/a.txt", type="file"),
            schemas.FileTreeResponse(
                path="/dir/sub",
                type="directory",
                children=[schemas.FileTreeResponse(path="/dir/sub/b.txt", type="file")]
            )
        ]
    )
    dict_tree = tree.model_dump()
    assert len(dict_tree["children"]) == 2
    assert dict_tree["children"][1]["type"] == "directory"


# ---------- Eval schemas ----------
class TestEvalSchemas:
    def test_eval_dataset_row(self):
        row = schemas.EvalDatasetRow(
            id="ds1", name="Test DS", created_at="now", item_count=5
        )
        assert row.id == "ds1"
        assert row.item_count == 5
        assert row.storage_path is None

    def test_eval_dataset_json_create(self):
        body = schemas.EvalDatasetJsonCreate(name="ds", items=[{"description": "t"}])
        assert body.name == "ds"
        assert len(body.items) == 1

    def test_eval_dataset_json_create_default_name(self):
        body = schemas.EvalDatasetJsonCreate(items=[{"description": "t"}])
        assert body.name == ""

    def test_eval_task_create_request(self):
        req = schemas.EvalTaskCreateRequest(
            name="My Task", dataset_id="ds1", eval_method="result"
        )
        assert req.eval_method == "result"

    def test_eval_task_create_request_default_method(self):
        req = schemas.EvalTaskCreateRequest(name="Task", dataset_id="ds1")
        assert req.eval_method == "result"

    def test_eval_task_response(self):
        resp = schemas.EvalTaskResponse(
            id="t1",
            name="Task",
            created_at="now",
            updated_at="now",
            dataset_id="ds1",
            eval_method="result",
            status="pending",
        )
        assert resp.id == "t1"
        assert resp.total_items == 0

    def test_eval_task_patch_request(self):
        req = schemas.EvalTaskPatchRequest(name="Renamed", eval_method="process")
        assert req.name == "Renamed"
        assert req.eval_method == "process"

    def test_eval_task_result_response(self):
        resp = schemas.EvalTaskResultResponse(
            id="r1",
            task_id="t1",
            item_index=0,
            status="completed",
            passed=True,
        )
        assert resp.item_index == 0
        assert resp.passed is True
        assert resp.score_detail == {}
        assert resp.ragas_json == {}

    def test_agent_config_response(self):
        resp = schemas.AgentConfigResponse(model="gpt-4o", version_label="v1")
        data = resp.model_dump()
        assert data["model"] == "gpt-4o"
        assert data["version_label"] == "v1"

    def test_agent_config_update_request(self):
        req = schemas.AgentConfigUpdateRequest(model="gpt-4-turbo")
        assert req.model == "gpt-4-turbo"
        assert req.version_label is None
