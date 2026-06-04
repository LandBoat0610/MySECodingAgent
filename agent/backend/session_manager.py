"""
跨对话记忆与上下文工程模块。

负责：
- session_summary：当前会话摘要生成与读取
- project_memory：项目级记忆的读写（跨 session 共享）
- user_preferences：用户偏好的读写
- relevant_history：从历史 sessions 中检索相关对话
- context_budget：上下文预算信息

给 Agent 的接口：
{
    "session_summary": "...",
    "project_memory": "...",
    "user_preferences": "...",
    "relevant_history": [...],
    "context_budget": 12000
}
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.backend.config import (
    CONTEXT_BUDGET,
    HISTORY_RETRIEVAL_LIMIT,
    MEMORY_MAX_ENTRIES,
    SESSION_SUMMARY_MAX_LENGTH,
)
from agent.backend.database import get_connection


# ── 公开接口（供 graph.py / main.py 调用）─────────────────────────────


def get_memory_context(project_id: str, session_id: str = "") -> Dict[str, Any]:
    """获取完整记忆上下文，返回给 Agent 使用的标准格式。

    Args:
        project_id: 项目 ID
        session_id: 当前会话 ID（用于跳过自身的摘要）

    Returns:
        标准化的记忆上下文字典
    """
    session_summary = get_session_summary(session_id) if session_id else ""
    project_memory = get_project_memory(project_id)
    user_preferences = get_user_preferences()
    relevant_history = get_relevant_history(project_id, limit=HISTORY_RETRIEVAL_LIMIT)

    return {
        "session_summary": session_summary,
        "project_memory": project_memory,
        "user_preferences": user_preferences,
        "relevant_history": relevant_history,
        "context_budget": CONTEXT_BUDGET,
    }


# ── Session Summary ─────────────────────────────────────────────────


def get_session_summary(session_id: str) -> str:
    """读取当前 session 的摘要（从 conversation_rounds 的 final_answer 中提取）。"""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT final_answer FROM conversation_rounds "
                "WHERE session_id = ? AND status = 'completed' "
                "ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if row and row[0]:
            return _shorten(row[0], SESSION_SUMMARY_MAX_LENGTH)
    except Exception:
        pass
    return ""


def generate_and_save_session_summary(
    session_id: str, project_id: str, task: str, final_answer: str
) -> str:
    """用 LLM 生成会话摘要并保存。保存到 sessions 表但主要供跨会话使用。"""
    summary = _summarize_with_llm(task, final_answer)
    if summary:
        try:
            with get_connection() as conn:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "INSERT OR REPLACE INTO project_memory "
                    "(project_id, key, value, category, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'session_summary', ?, ?)",
                    (project_id, f"session:{session_id}", summary, now, now),
                )
                conn.execute(
                    "DELETE FROM project_memory WHERE project_id = ? "
                    "AND category = 'session_summary' AND id NOT IN ("
                    "    SELECT id FROM project_memory WHERE project_id = ? "
                    "    AND category = 'session_summary' "
                    "    ORDER BY updated_at DESC LIMIT 10"
                    ")",
                    (project_id, project_id),
                )
        except Exception:
            pass
    return summary


# ── Project Memory ──────────────────────────────────────────────────


def get_project_memory(project_id: str) -> str:
    """读取项目级记忆，返回格式化文本供 Agent 使用。

    按类别分组，每类保留最近的条目。
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value, category FROM project_memory "
                "WHERE project_id = ? AND category != 'session_summary' "
                "ORDER BY updated_at DESC LIMIT ?",
                (project_id, MEMORY_MAX_ENTRIES),
            ).fetchall()
    except Exception:
        return ""

    if not rows:
        return ""

    by_category: Dict[str, List[str]] = {}
    for key, value, category in rows:
        cat = category or "general"
        by_category.setdefault(cat, []).append(f"- {key}: {value}")

    lines: List[str] = []
    for category, entries in by_category.items():
        lines.append(f"### {category}")
        lines.extend(entries)
    return "\n".join(lines)


def save_project_memory(
    project_id: str, key: str, value: str, category: str = "general"
) -> bool:
    """保存一条项目级记忆条目。

    Args:
        project_id: 项目 ID
        key: 记忆键（如 "start_command", "test_command"）
        value: 记忆值
        category: 类别（如 "commands", "known_issues", "conventions"）

    Returns:
        是否保存成功
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO project_memory (project_id, key, value, category, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(project_id, key) DO UPDATE SET "
                "value = excluded.value, updated_at = excluded.updated_at",
                (project_id, key, value, category, now, now),
            )
        return True
    except Exception:
        return False


def list_project_memory(project_id: str) -> List[Dict[str, Any]]:
    """列出项目的所有记忆条目（用于 API 返回）。"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, key, value, category, created_at, updated_at "
                "FROM project_memory WHERE project_id = ? "
                "ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "key": row[1],
                "value": row[2],
                "category": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
            for row in rows
        ]
    except Exception:
        return []


# ── User Preferences ────────────────────────────────────────────────


_USER_ID = "default"


def get_user_preferences() -> str:
    """读取用户偏好，返回格式化文本。"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM user_preferences WHERE user_id = ?",
                (_USER_ID,),
            ).fetchall()
    except Exception:
        return ""

    if not rows:
        return ""

    return "\n".join(f"- {key}: {value}" for key, value in rows)


def save_user_preference(key: str, value: str) -> bool:
    """保存一条用户偏好。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO user_preferences (user_id, key, value, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET "
                "value = excluded.value, updated_at = excluded.updated_at",
                (_USER_ID, key, value, now),
            )
        return True
    except Exception:
        return False


def list_user_preferences() -> List[Dict[str, str]]:
    """列出所有用户偏好（用于 API 返回）。"""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value, updated_at FROM user_preferences WHERE user_id = ?",
                (_USER_ID,),
            ).fetchall()
        return [
            {"key": row[0], "value": row[1], "updated_at": row[2]} for row in rows
        ]
    except Exception:
        return []


# ── Relevant History ────────────────────────────────────────────────


def get_relevant_history(
    project_id: str, query: str = "", limit: int = None
) -> List[Dict[str, Any]]:
    """从历史 sessions 中检索相关对话。

    使用简单关键词匹配（非向量化）检索最近的完成对话轮次。
    如果提供了 query，则按关键词匹配度排序；否则按时间倒序。

    Args:
        project_id: 项目 ID
        query: 可选的查询关键词
        limit: 返回条数上限

    Returns:
        历史对话列表，每项包含 role 和 content
    """
    if limit is None:
        limit = HISTORY_RETRIEVAL_LIMIT

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT user_message, final_answer, created_at "
                "FROM conversation_rounds "
                "WHERE project_id = ? AND status = 'completed' AND final_answer != '' "
                "ORDER BY created_at DESC LIMIT 50",
                (project_id,),
            ).fetchall()
    except Exception:
        return []

    if not rows:
        return []

    results: List[Dict[str, Any]] = []
    for user_msg, final_answer, created_at in rows:
        if query and query.strip():
            score = _keyword_score(query, user_msg + " " + final_answer)
            if score == 0:
                continue
            results.append(
                {
                    "role": "user",
                    "content": _shorten(user_msg, 300),
                    "score": score,
                    "created_at": created_at,
                }
            )
        else:
            results.append(
                {
                    "role": "user",
                    "content": _shorten(user_msg, 300),
                    "created_at": created_at,
                }
            )

    if query and query.strip():
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return results[:limit]


# ── 内部辅助函数 ─────────────────────────────────────────────────────


def _summarize_with_llm(task: str, final_answer: str) -> str:
    """用 LLM 生成会话摘要。失败时回退到简单截断。"""
    try:
        from agent.backend.llm import get_openai_client

        client = get_openai_client()
        prompt = (
            f"请用中文为以下 Agent 会话生成一段简洁的摘要（不超过 3 句），"
            f"概括用户的任务、Agent 的解决方案和最终结果。\n\n"
            f"用户任务: {task}\n\n"
            f"最终结果: {_shorten(final_answer, 2000)}"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        return content.strip()
    except Exception:
        return _shorten(final_answer, SESSION_SUMMARY_MAX_LENGTH)


def _shorten(text: str, max_len: int) -> str:
    """截断文本到指定长度，保持语义完整。"""
    if len(text) <= max_len:
        return text
    # 优先在句号处断句
    truncated = text[:max_len]
    last_period = max(truncated.rfind("。"), truncated.rfind("\n"), truncated.rfind(". "))
    if last_period > max_len // 2:
        return truncated[: last_period + 1]
    return truncated + "..."


def _keyword_score(query: str, target: str) -> float:
    """简单关键词匹配打分（0-1 之间）。"""
    query_lower = query.lower()
    target_lower = target.lower()
    words = set(re.findall(r"\w+", query_lower))
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in target_lower)
    return hits / len(words)
