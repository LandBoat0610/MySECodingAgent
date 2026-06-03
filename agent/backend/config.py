import os
from contextlib import contextmanager
from contextvars import ContextVar

# 常量与环境配置
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_eval_model_override: ContextVar[str | None] = ContextVar("eval_model_override", default=None)
MEMORY_FILE = "agent_memory.md"
TRACE_JSON = "agent_trace.json"
TRACE_MERMAID = "agent_trace.mmd"
MAX_TOOL_OUTPUT = 4000
MAX_STEP_ITERATIONS = 5
STEP_ITERATIONS_BY_DIFFICULTY = {
    "easy": 4,
    "medium": 7,
    "hard": 10,
}
MAX_REFLECTIONS = 2
DEFAULT_WORKSPACE_PREFIX = "zizhiagent_workspace_"


def get_effective_model() -> str:
    """运行时模型：评测快照覆盖 > 平台设置 > 环境变量。"""
    ov = _eval_model_override.get()
    if ov and str(ov).strip():
        return str(ov).strip()
    try:
        from agent.backend.platform_settings import get_agent_config

        cfg = get_agent_config()
        m = cfg.get("model")
        if m and str(m).strip():
            return str(m).strip()
    except Exception:
        pass
    return MODEL


@contextmanager
def eval_model_context(model_id: str | None):
    """在上下文内固定 LLM 模型 ID（用于按任务快照复现评测）。"""
    if not model_id or not str(model_id).strip():
        yield
        return
    token = _eval_model_override.set(str(model_id).strip())
    try:
        yield
    finally:
        _eval_model_override.reset(token)


# 安全拦截正则列表
BLOCKED_BASH_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:&\};:",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bchmod\s+-R\s+777\s+/",
]

BASH_APPROVAL_REQUIRED = not os.environ.get("SKIP_BASH_APPROVAL", "").lower() in ("1", "true", "yes")

# ── RAG 配置 ──
RAG_STORE_DIR = os.environ.get("RAG_STORE_DIR", "rag_store")
RAG_EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
RAG_DEFAULT_TOP_K = int(os.environ.get("RAG_DEFAULT_TOP_K", "5"))
RAG_CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "50"))
RAG_COLLECTION_NAME = "agent_knowledge"
