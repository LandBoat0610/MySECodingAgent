"""平台级键值设置（与项目/会话隔离），供 IDE 与评测等多入口共享。"""
import json
from typing import Any, Dict

from agent.backend.database import get_connection

AGENT_CONFIG_KEY = "agent_config"


def _default_agent_config() -> Dict[str, Any]:
    from agent.backend.config import MODEL

    return {"model": MODEL, "version_label": ""}


def get_agent_config() -> Dict[str, Any]:
    base = _default_agent_config()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM platform_settings WHERE key = ?",
            (AGENT_CONFIG_KEY,),
        ).fetchone()
    if not row:
        return base
    try:
        stored = json.loads(row["value"])
        if isinstance(stored, dict):
            base.update({k: v for k, v in stored.items() if v is not None})
    except (json.JSONDecodeError, TypeError):
        pass
    return base


def set_agent_config(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = get_agent_config()
    if "model" in data and data["model"]:
        merged["model"] = str(data["model"]).strip()
    if "version_label" in data and data["version_label"] is not None:
        merged["version_label"] = str(data["version_label"]).strip()
    payload = json.dumps(merged, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO platform_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (AGENT_CONFIG_KEY, payload),
        )
    return merged
