# tests/test_schemas.py
import os
import sys
import pytest
from pydantic import ValidationError
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量，避免 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")

from agent.backend import schemas

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