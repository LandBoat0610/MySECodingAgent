# 对接 OpenAI 的相关接口，包含代码文件的推演逻辑
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI
from agent.backend.config import get_effective_model
from agent.backend.runtime_metrics import record_llm_usage
from agent.backend.utils import parse_json_object, load_prompts, log_state, resolve_workspace_path, safe_trim

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

def llm_json(system_prompt: str, user_prompt: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = client.chat.completions.create(
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

    return f"""{role}

principles:
{principles}
Constraints:
{constraints}
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
    log_state(trace, "plan", f"正在为任务制定执行计划: {task}")
    try:
        prompts_config = load_prompts()
        planner_config = prompts_config.get("planner_prompt", {})
        system_prompt = planner_config.get(
            "system",
            "你是一个自动智能体的任务规划器。请务必返回 JSON 格式，包含 'steps' 数组字段。",
        )
        template = planner_config.get("template", "用户任务:\n{user_task}")
        user_prompt = template.format(user_task=task)
        if memory:
            user_prompt += f"\n\n过往记忆:\n{memory}"

        data = llm_json(system_prompt, user_prompt, state)
        steps = data.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return [task]
        result = [str(s).strip() for s in steps if str(s).strip()]
        log_state(trace, "plan_result", "\n".join(f"{i + 1}. {s}" for i, s in enumerate(result)))
        return result or [task]
    except Exception as e:
        log_state(trace, "plan_error", str(e))
        return [task]


def infer_coding_targets(
    task: str,
    workspace_dir: str,
    trace: List[Dict[str, Any]],
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    log_state(trace, "infer_targets", "Using LLM to infer target file and run command...")
    
    # 从 YAML 配置文件中加载提示词
    try:
        prompts_config = load_prompts()
        infer_config = prompts_config.get("infer_targets_prompt", {})
        
        system_prompt = infer_config.get(
            "system", 
            "You are an expert coding environment configurator. Return ONLY a JSON object with keys 'target_file' and 'run_command'."
        )
        template = infer_config.get(
            "template", 
            "Task:\n{user_task}"
        )
        user_prompt = template.format(user_task=task)
    except Exception as e:
        log_state(trace, "infer_targets_prompt_error", f"Failed to load prompt: {e}")
        system_prompt = "You are an expert coding environment configurator. Return ONLY a JSON object with keys 'target_file' and 'run_command'."
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