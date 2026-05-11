# tests/test_eval_storage.py
"""测试 eval_storage 模块：评测数据存储目录配置。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestEvalStorage:
    def test_ensure_eval_storage_dirs_creates_directories(self, monkeypatch):
        import agent.backend.eval_storage as es

        with tempfile.TemporaryDirectory() as tmpdir:
            datasets_dir = os.path.join(tmpdir, "datasets")
            workspaces_dir = os.path.join(tmpdir, "run_workspaces")
            monkeypatch.setattr(es, "DATASETS_DIR", datasets_dir)
            monkeypatch.setattr(es, "WORKSPACES_DIR", workspaces_dir)

            es.ensure_eval_storage_dirs()
            assert os.path.isdir(datasets_dir)
            assert os.path.isdir(workspaces_dir)

    def test_constants_are_strings(self):
        from agent.backend.eval_storage import (
            EVAL_STORAGE_ROOT,
            DATASETS_DIR,
            WORKSPACES_DIR,
        )
        assert isinstance(EVAL_STORAGE_ROOT, str)
        assert isinstance(DATASETS_DIR, str)
        assert isinstance(WORKSPACES_DIR, str)
