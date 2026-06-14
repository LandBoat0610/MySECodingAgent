"""平台级键值设置（与项目/会话隔离），供 IDE 与评测等多入口共享。"""
import json
import sqlite3
import uuid
from typing import Any, Dict

from agent.backend.database import get_connection

AGENT_CONFIG_KEY = "agent_config"
TOOL_SETTINGS_KEY = "tool_settings"
SKILLS_KEY = "skills"


def get_registered_tools() -> list[Dict[str, str]]:
    """Return the real backend tools registered for LLM function calling."""
    try:
        from agent.backend.tools import tools
    except Exception:
        return []

    registered = []
    for tool in tools:
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        registered.append({
            "name": name,
            "description": str(function.get("description") or "").strip(),
        })
    return registered


def get_registered_tool_names() -> tuple[str, ...]:
    return tuple(tool["name"] for tool in get_registered_tools())


def _read_setting_value(key: str) -> str | None:
    """Read a persisted setting, tolerating calls before DB initialization."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM platform_settings WHERE key = ?",
                (key,),
            ).fetchone()
    except sqlite3.OperationalError as error:
        if "no such table: platform_settings" in str(error):
            return None
        raise
    return row["value"] if row else None


def _default_agent_config() -> Dict[str, Any]:
    from agent.backend.config import CROSS_SESSION_ENABLED, MODEL

    return {
        "model": MODEL,
        "version_label": "",
        "cross_session_enabled": CROSS_SESSION_ENABLED,
    }


def get_agent_config() -> Dict[str, Any]:
    base = _default_agent_config()
    value = _read_setting_value(AGENT_CONFIG_KEY)
    if value is None:
        return base
    try:
        stored = json.loads(value)
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
    if "cross_session_enabled" in data:
        merged["cross_session_enabled"] = bool(data["cross_session_enabled"])
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


def _default_tool_settings() -> Dict[str, bool]:
    return {name: True for name in get_registered_tool_names()}


def get_tool_settings() -> Dict[str, bool]:
    base = _default_tool_settings()
    value = _read_setting_value(TOOL_SETTINGS_KEY)
    if value is None:
        return base
    try:
        stored = json.loads(value)
        if isinstance(stored, dict):
            for name in base:
                if name in stored:
                    base[name] = bool(stored[name])
    except (json.JSONDecodeError, TypeError):
        pass
    return base


def set_tool_settings(data: Dict[str, bool]) -> Dict[str, bool]:
    merged = get_tool_settings()
    for name, enabled in data.items():
        if name in merged:
            merged[name] = bool(enabled)
    payload = json.dumps(merged, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO platform_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (TOOL_SETTINGS_KEY, payload),
        )
    return merged


def is_tool_enabled(name: str) -> bool:
    return get_tool_settings().get(name, False)


def get_skills() -> list[Dict[str, Any]]:
    value = _read_setting_value(SKILLS_KEY)
    if value is None:
        return []
    try:
        stored = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(stored, list):
        return []
    skills = []
    for item in stored:
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("id") or uuid.uuid4().hex[:8])
        name = str(item.get("name") or "").strip()
        content = str(item.get("content") or "").strip()
        if not name or not content:
            continue
        skills.append({
            "id": skill_id,
            "name": name,
            "content": content,
            "enabled": bool(item.get("enabled", True)),
        })
    return skills


def _save_skills(skills: list[Dict[str, Any]]) -> None:
    payload = json.dumps(skills, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO platform_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SKILLS_KEY, payload),
        )


def create_skill(data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name") or "").strip()
    content = str(data.get("content") or "").strip()
    if not name or not content:
        raise ValueError("Skill name and content are required")
    skills = get_skills()
    skill = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "content": content,
        "enabled": bool(data.get("enabled", True)),
    }
    skills.append(skill)
    _save_skills(skills)
    return skill


def update_skill(skill_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    skills = get_skills()
    for skill in skills:
        if skill["id"] != skill_id:
            continue
        if data.get("name") is not None:
            name = str(data["name"]).strip()
            if not name:
                raise ValueError("Skill name is required")
            skill["name"] = name
        if data.get("content") is not None:
            content = str(data["content"]).strip()
            if not content:
                raise ValueError("Skill content is required")
            skill["content"] = content
        if data.get("enabled") is not None:
            skill["enabled"] = bool(data["enabled"])
        _save_skills(skills)
        return skill
    raise KeyError(skill_id)


def delete_skill(skill_id: str) -> None:
    skills = get_skills()
    next_skills = [skill for skill in skills if skill["id"] != skill_id]
    if len(next_skills) == len(skills):
        raise KeyError(skill_id)
    _save_skills(next_skills)


def get_enabled_skills() -> list[Dict[str, Any]]:
    return [skill for skill in get_skills() if skill.get("enabled")]
