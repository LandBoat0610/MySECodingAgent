# tests/test_evaluation_jobs.py
"""测试 evaluation_jobs 模块的 CRUD 函数（使用 mock DB）。"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, ANY

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")


def _mock_conn(fetchone_returns=None, fetchall_returns=None):
    """构造一个模拟的 sqlite3 连接与游标。"""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_returns
    mock_cursor.fetchall.return_value = fetchall_returns or []
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None
    return mock_conn, mock_cursor


# ========== list_datasets ==========
class TestListDatasets:
    def test_empty(self):
        from agent.backend.evaluation_jobs import list_datasets
        mock_conn, _ = _mock_conn(fetchall_returns=[])
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            assert list_datasets() == []

    def test_with_rows(self):
        from agent.backend.evaluation_jobs import list_datasets
        rows = [
            {"id": "ds1", "name": "DS1", "created_at": "now", "item_count": 3, "storage_path": "/p"}
        ]
        mock_conn, _ = _mock_conn(fetchall_returns=rows)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = list_datasets()
            assert len(result) == 1
            assert result[0]["name"] == "DS1"


# ========== get_dataset_row ==========
class TestGetDatasetRow:
    def test_found(self):
        from agent.backend.evaluation_jobs import get_dataset_row
        row = {"id": "ds1", "name": "DS"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = get_dataset_row("ds1")
            assert result["name"] == "DS"

    def test_not_found(self):
        from agent.backend.evaluation_jobs import get_dataset_row
        mock_conn, _ = _mock_conn(fetchone_returns=None)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            assert get_dataset_row("nonexistent") is None


# ========== list_eval_tasks ==========
class TestListEvalTasks:
    def test_empty(self):
        from agent.backend.evaluation_jobs import list_eval_tasks
        mock_conn, _ = _mock_conn(fetchall_returns=[])
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            assert list_eval_tasks() == []

    def test_with_rows(self):
        from agent.backend.evaluation_jobs import list_eval_tasks
        rows = [{
            "id": "t1", "name": "Task1", "created_at": "n", "updated_at": "n",
            "dataset_id": "ds1", "dataset_name": "DS1", "eval_method": "result",
            "agent_model_snapshot": "", "agent_version_label_snapshot": "",
            "status": "pending", "error_message": "", "total_items": 5,
            "completed_items": 0, "passed_count": 0, "failed_count": 0
        }]
        mock_conn, _ = _mock_conn(fetchall_returns=rows)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = list_eval_tasks()
            assert len(result) == 1
            assert result[0]["dataset_name"] == "DS1"


# ========== get_eval_task ==========
class TestGetEvalTask:
    def test_found(self):
        from agent.backend.evaluation_jobs import get_eval_task
        row = {"id": "t1", "name": "Task", "status": "pending"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = get_eval_task("t1")
            assert result["name"] == "Task"

    def test_not_found_raises(self):
        from agent.backend.evaluation_jobs import get_eval_task
        mock_conn, _ = _mock_conn(fetchone_returns=None)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            with pytest.raises(LookupError, match="评测任务不存在"):
                get_eval_task("nonexistent")


# ========== delete_eval_task ==========
class TestDeleteEvalTask:
    def test_cannot_delete_running(self):
        from agent.backend.evaluation_jobs import delete_eval_task
        row = {"id": "t1", "status": "running"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            with pytest.raises(ValueError, match="任务运行中"):
                delete_eval_task("t1")

    def test_cannot_delete_cancelling(self):
        from agent.backend.evaluation_jobs import delete_eval_task
        row = {"id": "t1", "status": "cancelling"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            with pytest.raises(ValueError, match="任务运行中"):
                delete_eval_task("t1")


# ========== create_eval_task ==========
class TestCreateEvalTask:
    def test_invalid_eval_method(self):
        from agent.backend.evaluation_jobs import create_eval_task
        with pytest.raises(ValueError, match='eval_method'):
            create_eval_task("Test", "ds1", "invalid_method")

    def test_dataset_not_found(self):
        from agent.backend.evaluation_jobs import create_eval_task
        mock_conn, _ = _mock_conn(fetchone_returns=None)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn), \
             patch("agent.backend.evaluation_jobs.get_dataset_row", return_value=None):
            with pytest.raises(LookupError, match="数据集不存在"):
                create_eval_task("Test", "ds1", "result")


# ========== patch_eval_task ==========
class TestPatchEvalTask:
    def test_not_pending_raises(self):
        from agent.backend.evaluation_jobs import patch_eval_task
        row = {"id": "t1", "status": "running"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            with pytest.raises(ValueError, match="待运行"):
                patch_eval_task("t1", name="Renamed")


# ========== list_task_results ==========
class TestListTaskResults:
    def test_empty(self):
        from agent.backend.evaluation_jobs import list_task_results
        mock_conn, _ = _mock_conn(fetchone_returns={"id": "t1"}, fetchall_returns=[])
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = list_task_results("t1")
            assert result == []

    def test_with_results(self):
        from agent.backend.evaluation_jobs import list_task_results
        task_row = {"id": "t1", "status": "completed"}
        result_rows = [{
            "id": "r1", "task_id": "t1", "item_index": 0, "item_key": "k1",
            "description_snapshot": "desc", "status": "completed",
            "passed": 1, "score_detail": '{"ok":true}', "final_answer": "ans",
            "trace_json": '[]', "run_error": "",
            "ragas_json": '{}', "judge_json": '{}',
            "runtime_metrics_json": '{}', "radar_json": '{}', "security_json": '{}',
            "started_at": None, "finished_at": None
        }]
        mock_conn, mock_cursor = _mock_conn(fetchone_returns=task_row, fetchall_returns=result_rows)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            result = list_task_results("t1")
            assert len(result) == 1
            assert result[0]["id"] == "r1"
            assert result[0]["score_detail"] == {"ok": True}
            assert result[0]["trace_json"] == []


# ========== aggregate_task_analytics ==========
class TestAggregateTaskAnalytics:
    def test_empty_results(self):
        from agent.backend.evaluation_jobs import aggregate_task_analytics
        with patch("agent.backend.evaluation_jobs.list_task_results", return_value=[]):
            result = aggregate_task_analytics("t1")
            assert result["task_id"] == "t1"
            assert result["items"] == []
            assert result["items_with_radar"] == 0

    def test_with_results(self):
        from agent.backend.evaluation_jobs import aggregate_task_analytics
        mock_results = [{
            "id": "r1", "task_id": "t1", "item_index": 0,
            "passed": 1, "score_detail": {}, "final_answer": "ok",
            "trace_json": [], "run_error": "",
            "ragas_json": {"answer_relevancy": 0.8, "faithfulness": 0.9},
            "judge_json": {"reasoning_quality": 7, "hallucination_severity": 3},
            "runtime_metrics_json": {"tokens_total": 500},
            "radar_json": {"answer_relevancy": 0.7, "faithfulness": 0.8, "reasoning_quality": 0.6, "anti_hallucination": 0.7, "tool_success": 1.0, "token_efficiency": 0.9, "security_hygiene": 1.0},
            "security_json": {"risk_score": 0},
            "started_at": None, "finished_at": None
        }]
        with patch("agent.backend.evaluation_jobs.list_task_results", return_value=mock_results):
            result = aggregate_task_analytics("t1")
            assert result["items_with_radar"] == 1
            assert len(result["items"]) == 1
            assert len(result["radar_axes"]) == 7


# ========== cancel_eval_task ==========
class TestCancelEvalTask:
    def test_not_running_raises(self):
        from agent.backend.evaluation_jobs import cancel_eval_task
        row = {"id": "t1", "status": "completed"}
        mock_conn, _ = _mock_conn(fetchone_returns=row)
        with patch("agent.backend.evaluation_jobs.get_connection", return_value=mock_conn):
            with pytest.raises(ValueError, match="未在运行"):
                cancel_eval_task("t1")
