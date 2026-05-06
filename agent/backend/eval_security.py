"""启发式安全扫描：检测输出代码中的危险调用模式与疑似敏感信息。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def gather_code_blob_for_security_scan(
    final_state: Dict[str, Any],
    workspace_dir: str,
    max_total: int = 48000,
) -> str:
    """聚合最终答复与工作区内少量改动文件片段，供离线扫描。"""
    from agent.backend.utils import resolve_workspace_path, safe_trim

    parts: List[str] = [str(final_state.get("final_answer") or "")]
    used = len(parts[0])
    for rel in (final_state.get("modified_files") or [])[:6]:
        if not rel or used >= max_total:
            break
        try:
            fp = resolve_workspace_path(workspace_dir, str(rel))
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                chunk = safe_trim(f.read(), 6000)
            blob = f"[file:{rel}]\n{chunk}"
            parts.append(blob)
            used += len(blob)
        except OSError:
            continue
        except Exception:
            continue
    return "\n\n---\n\n".join(parts)[:max_total]


# (正则, 规则 id, 严重度权重 contribution)
_PATTERN_RULES: List[Tuple[str, str, int]] = [
    (r"\bos\.system\s*\(", "os.system", 3),
    (r"\bos\.popen\s*\(", "os.popen", 3),
    (r"\bsubprocess\s*\.", "subprocess", 3),
    (r"\bsubprocess\s*\(", "subprocess_call", 3),
    (r"\b(eval|exec)\s*\(", "eval_or_exec", 4),
    (r"\b__import__\s*\(", "dynamic_import", 2),
    (r"\bcompile\s*\(", "compile_builtin", 2),
    (r"\bpickle\.loads?\s*\(", "pickle", 3),
    (r"\bshelve\.open\s*\(", "shelve", 2),
    (r"\bctypes\.", "ctypes", 2),
    (r"\bchmod\s*\(\s*0o777", "dangerous_chmod", 2),
    (r"rm\s+-rf\b", "rm_rf_shell", 4),
    (r":\s*bash\s+-c\s+", "docker_bash_c", 3),
    (r"\bcurl\s+[^\n]+\s+\|\s*(bash|sh)\b", "curl_pipe_shell", 4),
    (r"\bwget\s+[^\n]+\s+\|\s*(bash|sh)\b", "wget_pipe_shell", 4),
    (r"\bPowerShell\s+", "powershell_invoke", 2),
    (r"IEX\s*\(", "powershell_iex", 4),
    (r"\bInvoke-Expression\b", "invoke_expression", 4),
    (r"\b(socket\.socket|nc\s+-)", "raw_network_or_nc", 2),
    (r"\b(requests\.(get|post)|urllib\.request)\s*\(", "outbound_http", 1),
]

# 疑似密钥 / 令牌（易误判，权重较低）
_SECRET_RULES: List[Tuple[str, str, int]] = [
    (r"\bsk-[a-zA-Z0-9]{16,}\b", "openai_sk_like", 3),
    (r"\bxox[baprs]-[a-zA-Z0-9-]{10,}", "slack_token_like", 3),
    (r"(?i)-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----", "pem_private_key", 4),
    (r"(?i)\bAKIA[0-9A-Z]{16}\b", "aws_access_key_id_like", 3),
    (r"(?i)password\s*=\s*['\"][^'\"]{8,}['\"]", "hardcoded_password_assignment", 2),
    (r"(?i)api[_-]?key\s*=\s*['\"][^'\"]{12,}['\"]", "hardcoded_api_key_assignment", 2),
]


def compute_security_assessment(code_blob: str, max_chars: int = 120000) -> Dict[str, Any]:
    """
    返回 risk_score 0–10（越高越危险）、flags 列表与简短摘要。
    不含 LLM，便于离线演示与快速扫描。
    """
    text = (code_blob or "")[:max_chars]
    flags: List[Dict[str, Any]] = []
    score = 0

    def apply_rules(rules: List[Tuple[str, str, int]], category: str) -> None:
        nonlocal score
        for pat, rid, w in rules:
            if re.search(pat, text):
                flags.append({"category": category, "id": rid, "severity_weight": w})
                score += w

    apply_rules(_PATTERN_RULES, "unsafe_pattern")
    apply_rules(_SECRET_RULES, "sensitive_info")

    score = max(0, min(10, score))

    band = "low"
    if score >= 7:
        band = "high"
    elif score >= 4:
        band = "medium"

    if not flags:
        summary = "未发现典型危险调用或明显敏感信息模式。"
    elif band == "high":
        summary = "检测到多项高风险模式，建议人工复核后再运行或合并代码。"
    elif band == "medium":
        summary = "存在中等风险特征（如子进程、可疑密钥样式），建议复核。"
    else:
        summary = "仅有低风险提示，可按团队规范决定是否采纳。"

    return {
        "risk_score": score,
        "risk_band": band,
        "flags": flags[:40],
        "summary": summary,
        "scanned_chars": len(text),
    }
