# 对接 OpenAI 的相关接口，包含代码文件的推演逻辑
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from agent.backend.config import get_effective_model
from agent.backend.platform_settings import get_enabled_skills
from agent.backend.runtime_metrics import record_llm_usage
from agent.backend.utils import parse_json_object, load_prompts, log_state, resolve_workspace_path, safe_trim

load_dotenv()

PLAN_MAX_STEPS = 20

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            "Set the OPENAI_API_KEY environment variable before calling any LLM function."
        )
    _client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL")
    )
    return _client


class _ClientProxy:
    def __getattr__(self, name):
        return getattr(_get_client(), name)


client = _ClientProxy()


def fallback_session_title(message: str) -> str:
    text = " ".join((message or "").split())
    if not text:
        return "New Session"
    return text[:32].rstrip() + ("..." if len(text) > 32 else "")


def generate_session_title(message: str) -> str:
    """Generate a short conversation title from the user's first message."""
    fallback = fallback_session_title(message)
    if not (message or "").strip():
        return fallback
    try:
        response = _get_client().chat.completions.create(
            model=get_effective_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You name coding-agent conversations. Return only a concise title, "
                        "no quotes, no markdown, no punctuation-only title. Use the same "
                        "language as the user when possible. Keep it within 12 Chinese "
                        "characters or 6 English words."
                    ),
                },
                {"role": "user", "content": message},
            ],
            temperature=0.2,
            max_tokens=32,
        )
        title = (response.choices[0].message.content or "").strip()
        title = title.strip("\"'“”‘’`").splitlines()[0].strip()
        return title[:40] if title else fallback
    except Exception:
        return fallback


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """调用 OpenAI 兼容的 Embedding API 对文本列表进行向量化（供 RAG 使用）。"""
    from agent.backend.config import RAG_EMBEDDING_MODEL
    response = _get_client().embeddings.create(
        model=RAG_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def llm_json(system_prompt: str, user_prompt: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = _get_client().chat.completions.create(
        model=get_effective_model(),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    record_llm_usage(state, response)
    return parse_json_object(response.choices[0].message.content or "{}")


def build_system_prompt(memory: str, workspace_dir: str) -> str:
    try:
        prompts_config = load_prompts()
        sys_config = prompts_config.get("system_prompt", {})
    except Exception as e:
        print(f"Warning: 加载 prompts.yaml 失败，使用后备提示词。({e})")
        sys_config = {}

    role = sys_config.get("role", "You are Agent-Plus, an autonomous coding and research agent.")
    principles = sys_config.get("principles", "Please write robust code.")
    constraints = sys_config.get("constraints", "Stay inside the workspace.")
    skills = get_enabled_skills()
    skills_block = ""
    if skills:
        skills_block = "\n\nUser-added skills:\n" + "\n\n".join(
            f"### {skill['name']}\n{skill['content']}" for skill in skills
        )

    return f"""{role}

principles:
{principles}
Constraints:
{constraints}
{skills_block}
Workspace:
{workspace_dir}
Memory:
{memory}
""".strip()


def create_plan(
    task: str,
    memory: str,
    trace: List[Dict[str, Any]],
    state: Optional[Dict[str, Any]] = None,
) -> List[str]:
    log_state(trace, "plan", f"正在为任务制定执行计划: {task}", state=state)
    try:
        prompts_config = load_prompts()
        planner_config = prompts_config.get("planner_prompt", {})
        system_prompt = planner_config.get(
            "system",
            "你是一个自动智能体的任务规划器。请务必返回 JSON 格式，包含 'steps' 数组字段。",
        )
        system_prompt += (
            "\n\nPlan display rules:"
            "\n- First classify task difficulty as easy, medium, or hard, then choose the number of steps accordingly."
            "\n- Each item in steps must be a short user-facing natural-language sentence."
            "\n- Do not include JSON, code blocks, tool call names, function arguments, diffs, or internal metadata."
            "\n- Describe intent and outcome, not raw implementation parameters."
            f"\n- Return between 1 and {PLAN_MAX_STEPS} steps. Simple tasks should use 1-2 steps; do not pad the plan."
            f"\n- Never return more than {PLAN_MAX_STEPS} steps."
        )
        template = planner_config.get("template", "用户任务:\n{user_task}")
        user_prompt = template.format(user_task=task)
        if memory:
            user_prompt += f"\n\n过往记忆:\n{memory}"
        feedback = (state or {}).get("plan_feedback", "")
        if feedback:
            user_prompt += f"\n\n用户对计划的修改要求:\n{feedback}"

        data = llm_json(system_prompt, user_prompt, state)
        difficulty = str(data.get("difficulty") or "").strip().lower()
        if difficulty:
            if state is not None:
                state["task_difficulty"] = difficulty
            log_state(trace, "plan_difficulty", difficulty)

        # Extract task_type from LLM output
        task_type = str(data.get("task_type", "")).strip().lower()
        if task_type and state is not None:
            state["task_type"] = task_type
            log_state(trace, "plan_task_type", task_type)

        # Extract acceptance_criteria from LLM output
        criteria = data.get("acceptance_criteria", [])
        if isinstance(criteria, list) and criteria and state is not None:
            state["acceptance_criteria"] = [str(c).strip() for c in criteria if str(c).strip()]

        steps = data.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return [task]
        # Save raw structured steps to state before converting to strings
        if state is not None and isinstance(steps, list):
            state["_structured_steps"] = steps
        result = [_normalize_plan_step(s) for s in steps[:PLAN_MAX_STEPS]]
        result = [s for s in result if s]
        log_state(trace, "plan_result", "\n".join(f"{i + 1}. {s}" for i, s in enumerate(result)))
        return result or [task]
    except Exception as e:
        log_state(trace, "plan_error", str(e))
        return [task]


def _normalize_plan_step(step: Any) -> str:
    if isinstance(step, str):
        text = step.strip()
        if text.startswith(("{", "[")):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list) and parsed:
                    return _normalize_plan_step(parsed[0])
                if isinstance(parsed, dict):
                    return _normalize_plan_step(parsed)
            except Exception:
                pass
    elif isinstance(step, dict):
        for key in ("description", "summary", "task", "goal", "title", "step"):
            value = step.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        else:
            action = str(step.get("action") or step.get("tool") or "").replace("_", " ").strip()
            target = str(step.get("target") or step.get("path") or step.get("file") or "").strip()
            text = f"{action} {target}".strip() or "Complete one planned task."
    else:
        text = str(step).strip()

    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\{[\s\S]*?\}", " ", text)
    text = re.sub(r"\[[\s\S]*?\]", " ", text)
    text = re.sub(
        r"\b(command|args|arguments|content|tool_call|function_call|returncode|stdout|stderr)"
        r"\s*[:=]\s*\\?\"?.*?(,|$)",
        " ",
        text,
        flags=re.I,
    )
    text = " ".join(text.split())
    text = text.strip("-:：,，. {}[]")

    if not text:
        return ""
    if len(text) > 120:
        text = text[:117].rstrip() + "..."
    return text


def infer_coding_targets(
    task: str,
    workspace_dir: str,
    trace: List[Dict[str, Any]],
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    log_state(trace, "infer_targets", "Using LLM to infer target file and run command...", state=state)

    # 从 YAML 配置文件中加载提示词
    try:
        prompts_config = load_prompts()
        infer_config = prompts_config.get("infer_targets_prompt", {})

        system_prompt = infer_config.get(
            "system",
            "You are an expert coding environment configurator. "
            "Return ONLY a JSON object with keys 'target_file' and 'run_command'."
        )
        template = infer_config.get(
            "template",
            "Task:\n{user_task}"
        )
        user_prompt = template.format(user_task=task)
    except Exception as e:
        log_state(trace, "infer_targets_prompt_error", f"Failed to load prompt: {e}")
        system_prompt = (
            "You are an expert coding environment configurator. "
            "Return ONLY a JSON object with keys 'target_file' and 'run_command'."
        )
        user_prompt = f"Task:\n{task}"

    # 2. 调用大模型进行智能推断
    try:
        data = llm_json(system_prompt, user_prompt, state)
        target_file = data.get("target_file", "main.py")
        run_command = data.get("run_command", f"python {target_file}")
    except Exception as e:
        # 如果返回了非 JSON，我们保留一个兜底（Fallback）机制
        log_state(trace, "infer_targets_error", f"LLM inference failed: {e}. Using fallback.")
        target_file = "main.py"
        run_command = "python main.py"

    # 3. 安全校验：确保大模型猜出的路径没有逃逸出我们的沙盒工作区
    try:
        safe_target = resolve_workspace_path(workspace_dir, target_file)
        rel = os.path.relpath(safe_target, workspace_dir)
        target_file = rel
    except Exception:
        pass

    log_state(trace, "infer_targets_result", f"target_file={target_file}, run_command={run_command}")
    return {"target_file": target_file, "run_command": run_command}


def extract_code_context(target_file: str, workspace_dir: str) -> str:
    try:
        safe_path = resolve_workspace_path(workspace_dir, target_file)
        with open(safe_path, "r", encoding="utf-8") as f:
            return safe_trim(f.read(), 6000)
    except Exception as e:
        return f"[code_context unavailable: {e}]"


# ── Executor Prompt ──
def build_executor_prompt(current_step, step_index, total_steps, state):
    prompts_config = load_prompts()
    executor_cfg = prompts_config.get("executor_prompt", {})
    template = executor_cfg.get("template", "当前执行步骤：{step_goal}")
    criteria = "\n".join(f"- {c}" for c in state.get("acceptance_criteria", [])[:6]) or "没有设定验收标准"
    codebase_summary = safe_trim(state.get("codebase_summary", ""), 1600) or "无代码结构摘要"
    retrieved = "\n\n".join(
        f"[{item.get('source')}]\n{safe_trim(str(item.get('content') or item.get('error') or ''), 1200)}"
        for item in state.get("retrieved_context", [])[:4] if isinstance(item, dict)
    ) or "无检索结果"
    tool_history = (
        "\n".join(
            safe_trim(json.dumps(t, ensure_ascii=False), 400)
            for t in state.get("tool_history", [])[-3:]
        )
        or "无工具调用记录"
    )
    return template.format(
        step_id=step_index, total_steps=total_steps,
        step_goal=current_step.get("goal", ""),
        step_verification=current_step.get("verification", ""),
        task_type=state.get("task_type", "coding"),
        task_difficulty=state.get("task_difficulty", "unknown"),
        acceptance_criteria=criteria, codebase_summary=codebase_summary,
        retrieved_context=retrieved, tool_history=tool_history,
    )


# ── Verifier Prompt ──
def build_verifier_prompt(current_step, state):
    prompts_config = load_prompts()
    verifier_cfg = prompts_config.get("verifier_prompt", {})
    template = verifier_cfg.get("template", "Step: {step_goal}\nTool: {tool_status}")
    step_goal = current_step.get("goal", "")
    tool_result = state.get("last_tool_result", {}) or {}
    execution = state.get("last_execution", {}) or {}
    tool_status = tool_result.get("status", "none")
    if execution:
        tool_status = "success" if execution.get("returncode") == 0 else "error"
    returncode = execution.get("returncode") if execution else tool_result.get("returncode", "none")
    criteria = "\n".join(f"- {c}" for c in state.get("acceptance_criteria", [])[:6]) or "无验收标准"
    output = str(tool_result.get("output", "") or execution.get("output", "") or "")
    modified = ", ".join(state.get("modified_files", [])[-8:]) or "无"
    return template.format(
        task_type=state.get("task_type", "coding"),
        step_goal=step_goal, step_index=state.get("current_task_index", 0),
        acceptance_criteria=criteria, tool_status=tool_status,
        returncode=returncode, stdout_len=len(str(tool_result.get("stdout", ""))),
        stderr_len=len(str(tool_result.get("stderr", ""))),
        output_summary=safe_trim(output, 600),
        modified_files=modified, modified_files_count=len(state.get("modified_files", [])),
        task_difficulty=state.get("task_difficulty", "unknown"),
    )


def verifier_llm_check(current_step, state):
    prompts_config = load_prompts()
    verifier_cfg = prompts_config.get("verifier_prompt", {})
    system_prompt = verifier_cfg.get("system", "你是一个严谨的 Verifier。")
    user_prompt = build_verifier_prompt(current_step, state)
    try:
        data = llm_json(system_prompt, user_prompt, state)
        return {
            "failed": bool(data.get("failed", False)),
            "reason": str(data.get("reason", "")),
            "needs_repair": bool(data.get("needs_repair", False)),
            "repair_suggestion": str(data.get("repair_suggestion", "")),
            "more_steps_remaining": bool(data.get("more_steps_remaining", False)),
            "task_fully_done": bool(data.get("task_fully_done", False)),
        }
    except Exception as e:
        log_state(state.get("trace", []), "verifier_llm_error", str(e))
        return {
            "failed": False, "reason": f"LLM verifier error: {e}",
            "needs_repair": False, "repair_suggestion": "",
            "more_steps_remaining": False, "task_fully_done": False,
        }


# ── Final Summary Prompt ──
def build_final_summary(state):
    prompts_config = load_prompts()
    summary_cfg = prompts_config.get("final_summary_prompt", {})
    system_prompt = summary_cfg.get("system", "你是一个 Final Summarizer。")
    template = summary_cfg.get("template", "Task: {task}")
    used_tools = ", ".join(sorted(set(state.get("used_tools", [])))) or "无"
    modified = ", ".join(state.get("modified_files", [])[-8:]) or "无"
    v_results = state.get("verification_results", []) or []
    v_summary = "\n".join(
        f"  - 步骤{r.get('step_index', '?')}: {'通过' if not r.get('failed') else '失败'} ({r.get('reason', '')})"
        for r in v_results
    ) or "无验证记录"
    execution_log = "\n".join(state.get("result_history", [])[-8:]) or "无执行记录"
    repair_count = state.get("retry_count", 0)
    repair_log = (
        f"修复次数: {repair_count}\n自修正次数: {state.get('reflections', 0)}"
        if repair_count > 0 or state.get("reflections", 0) > 0
        else "无修复"
    )
    plan = state.get("current_plan", []) or []
    total = len(plan)
    done = sum(1 for s in plan if isinstance(s, dict) and s.get("status") == "done")
    user_prompt = template.format(
        task=state.get("task", ""), task_type=state.get("task_type", "unknown"),
        task_difficulty=state.get("task_difficulty", "unknown"),
        total_plan_steps=total, completed_steps=done,
        status=state.get("status", "unknown"), used_tools=used_tools,
        modified_files=modified, verification_summary=v_summary,
        execution_log=execution_log, repair_log=repair_log,
    )
    try:
        from agent.backend.config import get_effective_model
        response = _get_client().chat.completions.create(
            model=get_effective_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3, max_tokens=1500,
        )
        summary = (response.choices[0].message.content or "").strip()
        record_llm_usage(state, response)
        return summary or _fallback_summary(state)
    except Exception as e:
        log_state(state.get("trace", []), "final_summary_error", str(e))
        return _fallback_summary(state)


def _fallback_summary(state):
    modified = ", ".join(state.get("modified_files", [])[-8:]) or "无"
    status = state.get("status", "unknown")
    task_type = state.get("task_type", "unknown")
    failure = state.get("failure_reason", "")
    parts = [f"任务类型: {task_type}", f"最终状态: {status}", f"修改文件: {modified}"]
    if failure:
        parts.append(f"失败原因: {failure}")
    used = sorted(set(state.get("used_tools", [])))
    parts.append(f"工具调用: {', '.join(used) or '无'}")
    return "\n".join(parts)
