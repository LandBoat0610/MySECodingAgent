"""评测数据文件目录（datasets / run_workspaces）。"""
import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))
EVAL_STORAGE_ROOT = os.path.join(_AGENT_ROOT, "eval_storage")
DATASETS_DIR = os.path.join(EVAL_STORAGE_ROOT, "datasets")
WORKSPACES_DIR = os.path.join(EVAL_STORAGE_ROOT, "run_workspaces")


def ensure_eval_storage_dirs() -> None:
    os.makedirs(DATASETS_DIR, exist_ok=True)
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
