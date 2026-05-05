import os

# 常量与环境配置
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MEMORY_FILE = "agent_memory.md"
TRACE_JSON = "agent_trace.json"
TRACE_MERMAID = "agent_trace.mmd"
MAX_TOOL_OUTPUT = 4000
MAX_STEP_ITERATIONS = 3
MAX_REFLECTIONS = 3
DEFAULT_WORKSPACE_PREFIX = "zizhiagent_workspace_"

# 安全拦截正则列表
BLOCKED_BASH_PATTERNS = [
    r"\brm\s+-rf\s+/\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:&\};:",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bchmod\s+-R\s+777\s+/\b",
]