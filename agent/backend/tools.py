# 存储和外界交互的业务核心工具、安全防护及 JSON Schema 的映射层
import os
import re
import json
import html
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, List

from agent.backend.config import BLOCKED_BASH_PATTERNS
from agent.backend.utils import ensure_workspace, resolve_workspace_path, tool_result, safe_trim

CURRENT_WORKSPACE_DIR = None

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": (
                "在 工作区 (workspace) 内执行一条 shell 命令（Windows cmd.exe）。"
                "适用场景：运行 Python 脚本、编译代码、创建目录 (mkdir)、检查环境 (python --version)。"
                "不适用：读取/写入文件内容（用 read_file / write_file）、列出目录（用 dir /b 组合命令已足够轻量）、"
                "网络请求（用 web_search / fetch_url）。"
                "注意：命令超时限制 20 秒，避免递归搜索超大目录；危险命令（rm -rf / 等）会被自动拦截。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令，在 cmd.exe 环境中运行"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "列出工作区指定目录下的文件和子目录，返回结构化 JSON 列表。"
                "适用场景：查看目录结构、确认文件是否存在、导航项目目录。"
                "注意：recursive=false 只返回一级子条目，recursive=true 递归列出所有文件。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径（相对或绝对），默认为当前工作区根目录"},
                    "recursive": {"type": "boolean", "description": "是否递归列出（默认 false）"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": (
                "读取文件指定行范围的内容，适用于大文件分段查看。"
                "适用场景：查看文件中间某段、调试大日志、避免一次性读取超大文件。"
                "注意：offset 从 1 开始计数；limit 为空则读到文件末尾。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "offset": {"type": "integer", "description": "起始行号（从 1 开始，默认 1）"},
                    "limit": {"type": "integer", "description": "读取行数（默认 200）"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取工作区中某个文件的内容并返回全文。"
                "适用场景：查看已有文件的代码、配置文件、输出日志。"
                "不适用：读取目录（会报错）；想搜索多个文件请用 execute_bash('findstr ...')；"
                "想获取网页内容请用 fetch_url。"
                "注意：参数 path 只需文件名或相对路径，系统自动在工作区内查找。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径（相对于工作区根目录，或绝对路径）"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "将内容写入工作区中的文件，若文件已存在则覆盖，若目录不存在则自动创建。"
                "适用场景：创建新代码文件、修改配置、写入测试数据。"
                "注意：参数 path 只需文件名或相对路径；content 为完整文本内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标文件路径（相对于工作区根目录）"},
                    "content": {"type": "string", "description": "要写入的完整文本内容"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "对外部信息进行网页搜索，返回标题和链接列表。内置多引擎降级（DuckDuckGo → Bing），"
                "单个引擎不可用时自动切换到备用引擎。"
                "适用场景：查找技术文档、API 用法、未知概念；需要先搜索再根据链接用 fetch_url 抓取详情。"
                "不适用：已知明确 URL 直接抓取（用 fetch_url）。"
                "注意：返回的是搜索摘要，如需页面全文必须追加 fetch_url。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词（中英文均可）"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "抓取指定网页的纯文本内容（已剥离 HTML 标签和脚本）。"
                "适用场景：已知确切 URL 需要读取页面全文；配合 web_search，先搜到链接再抓取详情。"
                "不适用：搜索未知关键词（用 web_search）；非 HTTP/HTTPS 协议。"
                "注意：返回的是纯文本，不含样式和图片；超时 20 秒。"
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "要抓取的完整 URL（需含 http:// 或 https://）"}},
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "在代码文件中搜索匹配模式的文本行，支持正则表达式。"
                "适用场景：查找函数定义、错误信息、特定模式；搜索多文件内容。"
                "注意：pattern 可为普通字符串或正则；不传 path 则搜索当前目录所有文本文件。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索模式（支持正则表达式）"},
                    "path": {"type": "string", "description": "文件或目录路径（可选，默认当前目录）"},
                    "case_sensitive": {"type": "boolean", "description": "是否区分大小写（默认 false）"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": (
                "将 unified diff patch 应用到目标文件。用于精确代码修改，比全文件重写更高效。"
                "适用场景：修复代码 Bug（少行修改）；按 diff 格式精准增删行。"
                "不适用：新增整个文件（用 write_file）。"
                "注意：patch 须为标准 unified diff 格式；目标文件必须已存在；冲突时静默跳过失败块。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "目标文件路径"},
                    "patch": {"type": "string", "description": "unified diff 格式的 patch 内容"}
                },
                "required": ["target", "patch"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_diff",
            "description": (
                "获取工作区 git 仓库的差异内容。"
                "适用场景：查看代码修改、验证改动正确性、生成 patch。"
                "注意：需要工作区已初始化 git 仓库（git init）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "是否查看暂存区（git diff --staged，默认 false 即未暂存）"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "运行 pytest 测试，返回测试结果摘要。"
                "适用场景：验证代码正确性、回归测试、CI 流程。"
                "注意：需要 Python 环境中已安装 pytest；无测试文件时返回 empty。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "测试文件或目录路径（可选，默认当前目录）"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_lint",
            "description": (
                "运行 flake8 代码风格检查，返回 lint 错误列表。"
                "适用场景：代码质量检查、提交前验证。"
                "注意：需要 Python 环境中已安装 flake8。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "要检查的文件或目录路径"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "在知识库中检索与查询相关的文档片段，返回内容、来源和相似度。"
                "适用场景：查找任务书要求、README 说明、技术文档、部署配置、项目上下文等。"
                "不适用：搜索代码内容（用 search_code）；搜索网络（用 web_search）。"
                "注意：需要在知识库中已有文档才能检索，返回结果包含来源路径和相似度分数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询文本"},
                    "top_k": {"type": "integer", "description": "返回最相关的结果数量（默认 5）"}
                },
                "required": ["query"]
            }
        }
    }
]


def parse_tool_arguments(raw_arguments: str) -> Dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}


def execute_bash(command: str) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        for pattern in BLOCKED_BASH_PATTERNS:
            if re.search(pattern, command):
                return tool_result("error", f"Blocked potentially dangerous command: {command}",
                                   summary="危险命令已被拦截",
                                   error_type="blocked")

        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            executable=os.environ.get("COMSPEC", None),
        )
        combined = f"STDOUT:\n{safe_trim(result.stdout)}\n\nSTDERR:\n{safe_trim(result.stderr)}"
        is_ok = result.returncode == 0
        return tool_result(
            "success" if is_ok else "error",
            combined,
            path=workspace_dir,
            returncode=result.returncode,
            meta={"command": command},
            stdout=safe_trim(result.stdout),
            stderr=safe_trim(result.stderr),
            summary=f"命令 {'成功' if is_ok else '失败'} (exit={result.returncode})",
            error_type=None if is_ok else "execution_error",
        )
    except subprocess.TimeoutExpired:
        return tool_result("error", "Command timed out", path=CURRENT_WORKSPACE_DIR,
                           returncode=124, summary="命令超时", error_type="timeout")
    except Exception as e:
        return tool_result("error", str(e), path=CURRENT_WORKSPACE_DIR,
                           summary=f"命令执行异常: {e}", error_type="execution_error")


def _resolve_dir(file_path: str) -> str:
    if os.path.isabs(file_path):
        return file_path
    workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
    return resolve_workspace_path(workspace_dir, file_path)


def list_files(path: str = ".", recursive: bool = False) -> str:
    try:
        safe_dir = _resolve_dir(path)
        if not os.path.isdir(safe_dir):
            return tool_result("error", f"Not a directory: {path}", path=safe_dir,
                               error_type="invalid_path", summary=f"不是目录: {path}")

        entries = []
        if recursive:
            for root, dirs, files in os.walk(safe_dir):
                rel = os.path.relpath(root, safe_dir)
                for d in dirs:
                    entries.append({"name": d, "type": "dir", "path": os.path.join(rel, d).replace("\\", "/")})
                for f in files:
                    entries.append({"name": f, "type": "file", "path": os.path.join(rel, f).replace("\\", "/")})
        else:
            for entry in os.listdir(safe_dir):
                full = os.path.join(safe_dir, entry)
                entries.append({
                    "name": entry,
                    "type": "dir" if os.path.isdir(full) else "file",
                    "path": entry.replace("\\", "/"),
                })

        return tool_result("success",
                           json.dumps({"path": path, "count": len(entries), "entries": entries}, ensure_ascii=False),
                           path=safe_dir,
                           summary=f"{path}: {len(entries)} 条")
    except Exception as e:
        return tool_result("error", str(e), path=path, summary=f"列出失败: {e}")


def read_file_range(path: str, offset: int = 1, limit: int = 200) -> str:
    try:
        safe_path = _resolve_dir(path)
        with open(safe_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        start = max(0, offset - 1)
        end = start + limit if limit else len(lines)
        selected = lines[start:end]

        if not selected:
            return tool_result(
                "success",
                json.dumps(
                    {"lines": [], "total_lines": len(lines), "offset": offset},
                    ensure_ascii=False,
                ),
                path=safe_path,
                summary=(
                    f"{path}: 行 {offset}-{min(end, len(lines))} 无内容"
                    f" (共 {len(lines)} 行)"
                ),
            )

        return tool_result("success",
                           "".join(selected),
                           path=safe_path,
                           summary=f"{path}: 行 {start+1}-{min(end, len(lines))}/{len(lines)}")
    except FileNotFoundError:
        return tool_result("error", f"File not found: {path}", path=path,
                           error_type="not_found", summary=f"文件不存在: {path}")
    except Exception as e:
        return tool_result("error", str(e), path=path, summary=f"读取范围异常: {e}")


def read_file(path: str) -> str:
    try:
        if os.path.isabs(path):
            safe_path = path
        else:
            workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
            safe_path = resolve_workspace_path(workspace_dir, path)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        return tool_result("success", content, path=safe_path, summary=f"已读取 {safe_path}")
    except FileNotFoundError:
        return tool_result("error", f"File not found: {path}", path=path,
                           error_type="not_found", summary=f"文件不存在: {path}")
    except PermissionError:
        return tool_result("error", f"Permission denied: {path}", path=path,
                           error_type="permission", summary=f"权限被拒绝: {path}")
    except Exception as e:
        return tool_result("error", str(e), path=path, summary=f"读取异常: {e}")


def write_file(path: str, content: str) -> str:
    try:
        if os.path.isabs(path):
            safe_path = path
        else:
            workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
            safe_path = resolve_workspace_path(workspace_dir, path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return tool_result("success", f"Successfully wrote to {safe_path}", path=safe_path,
                           summary=f"已写入 {safe_path}", modified_files=[safe_path])
    except PermissionError:
        return tool_result("error", f"Permission denied: {path}", path=path,
                           error_type="permission", summary=f"写入权限被拒绝: {path}")
    except Exception as e:
        return tool_result("error", str(e), path=path, summary=f"写入异常: {e}")


_WEB_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


def _do_web_search(query: str, timeout: int) -> list:
    """返回搜索结果列表，最多 5 条。"""
    encoded = urllib.parse.quote(query)
    url = f"https://duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(url, headers=_WEB_SEARCH_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_html = resp.read().decode("utf-8", errors="ignore")

    results = []
    for m in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
        raw_html, re.I | re.S
    ):
        href = html.unescape(m.group(1))
        title = re.sub(r"<.*?>", "", m.group(2))
        title = html.unescape(title).strip()
        if title and href:
            results.append({"title": title, "url": href})
        if len(results) >= 5:
            break
    return results


def _do_bing_search(query: str, timeout: int) -> list:
    """Bing 搜索作为 DuckDuckGo 的备用搜索引擎。"""
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/search?q={encoded}&setlang=zh-cn"
    req = urllib.request.Request(url, headers=_WEB_SEARCH_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_html = resp.read().decode("utf-8", errors="ignore")

    results = []
    for m in re.finditer(
        r'<li class="b_algo"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        raw_html, re.I | re.S
    ):
        href = html.unescape(m.group(1))
        title = re.sub(r"<.*?>", "", m.group(2))
        title = html.unescape(title).strip()
        if title and href and not href.startswith("javascript:"):
            results.append({"title": title, "url": href})
        if len(results) >= 5:
            break
    return results


_SEARCH_BACKENDS = [
    ("DuckDuckGo", _do_web_search),
    ("Bing", _do_bing_search),
]


def web_search(query: str) -> str:
    errors: List[str] = []
    for backend_name, backend_fn in _SEARCH_BACKENDS:
        for timeout in (20, 30):
            try:
                results = backend_fn(query, timeout)
                return tool_result(
                    "success",
                    json.dumps({
                        "query": query,
                        "results": results,
                        "backend": backend_name,
                    }, ensure_ascii=False),
                    summary=f"搜索'{query}': 找到{len(results)}条结果 ({backend_name})",
                )
            except Exception as e:
                errors.append(f"{backend_name}({timeout}s): {e}")
                continue
        continue

    return tool_result(
        "error",
        f"Web search failed on all backends: {'; '.join(errors[-4:])}. "
        "Tip: use fetch_url with a direct URL as an alternative.",
        summary=f"搜索'{query}'失败: 所有引擎不可达", error_type="network",
    )


def fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="ignore")

        text = re.sub(r"<script.*?>.*?</script>", " ", raw, flags=re.S | re.I)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<.*?>", " ", text, flags=re.S)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        return tool_result(
            "success",
            text,
            path=url,
            meta={"content_type": content_type},
            summary=f"已抓取 {url} ({len(text)} 字符)",
        )
    except urllib.error.URLError as e:
        return tool_result("error", str(e), path=url,
                           error_type="network", summary=f"抓取失败: {url}")
    except Exception as e:
        return tool_result("error", str(e), path=url,
                           summary=f"抓取异常: {e}")


def search_code(pattern: str, path: str = ".", case_sensitive: bool = False) -> str:
    try:
        safe_path = _resolve_dir(path)
        flags = 0 if case_sensitive else re.IGNORECASE

        if os.path.isfile(safe_path):
            targets = [safe_path]
        elif os.path.isdir(safe_path):
            targets = []
            for root, _, files in os.walk(safe_path):
                for f in files:
                    ext = f.endswith
                    if ext(('.py', '.js', '.ts', '.tsx', '.json', '.md', '.txt',
                            '.cfg', '.ini', '.yaml', '.yml', '.sh', '.bat', '.html', '.css')):
                        targets.append(os.path.join(root, f))
        else:
            return tool_result("error", f"Path not found: {path}", path=safe_path,
                               error_type="not_found", summary=f"路径不存在: {path}")

        matches = []
        for target in targets[:100]:
            try:
                with open(target, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line, flags):
                            matches.append({
                                "file": os.path.relpath(target, safe_path),
                                "line": i, "text": line.strip()[:200],
                            })
                            if len(matches) >= 50:
                                break
            except Exception:
                continue
            if len(matches) >= 50:
                break

        return tool_result(
            "success",
            json.dumps(
                {"pattern": pattern, "count": len(matches), "matches": matches},
                ensure_ascii=False,
            ),
            path=safe_path,
            summary=f"搜索'{pattern}': {len(matches)} 条匹配",
        )
    except Exception as e:
        return tool_result("error", str(e), path=path, summary=f"搜索异常: {e}")


def apply_patch(target: str, patch: str) -> str:
    try:
        safe_path = _resolve_dir(target)
        if not os.path.isfile(safe_path):
            return tool_result("error", f"Target file not found: {target}", path=safe_path,
                               error_type="not_found", summary=f"目标文件不存在: {target}")

        with open(safe_path, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()

        patched_lines = list(original_lines)
        hunks = re.findall(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*?)(?=@@|\Z)', patch, re.S)
        if not hunks:
            return tool_result("error", "No valid hunks found in patch", path=safe_path,
                               error_type="invalid_format", summary="Patch 不含有效 hunk")

        applied = 0
        for hunk_match in hunks:
            old_start = int(hunk_match[0])
            old_count = int(hunk_match[1]) if hunk_match[1] else 1
            hunk_body = hunk_match[4]

            new_lines = []
            for line in hunk_body.strip().split('\n'):
                if line.startswith('+'):
                    new_lines.append(line[1:] + '\n')
                elif not line.startswith('-'):
                    new_lines.append(line + '\n')

            line_idx = old_start - 1
            try:
                patched_lines[line_idx:line_idx + old_count] = new_lines
                applied += 1
            except Exception:
                continue

        with open(safe_path, 'w', encoding='utf-8') as f:
            f.writelines(patched_lines)

        return tool_result("success",
                           f"Patch applied: {applied} hunk(s)", path=safe_path,
                           summary=f"已应用 {applied} 个 hunk 到 {target}",
                           modified_files=[safe_path])
    except Exception as e:
        return tool_result("error", str(e), path=target, summary=f"Patch 失败: {e}")


def get_git_diff(staged: bool = False) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        args = ["git", "diff"]
        if staged:
            args.append("--staged")
        result = subprocess.run(args, cwd=workspace_dir, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=10)
        if result.returncode == 128 and "not a git repository" in result.stderr.lower():
            return tool_result("error", "Not a git repository. Run 'git init' first.",
                               path=workspace_dir, error_type="not_repo",
                               summary="不是 git 仓库，请先 git init")
        diff_text = result.stdout.strip()
        if not diff_text:
            return tool_result("success", "Working tree clean", path=workspace_dir,
                               summary="工作区干净，无差异")
        return tool_result("success", diff_text, path=workspace_dir,
                           summary=f"Git diff ({len(diff_text)} 字符)")
    except Exception as e:
        return tool_result("error", str(e), summary=f"git diff 异常: {e}")


def run_tests(target: str = ".") -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        safe_target = _resolve_dir(target)
        args = ["pytest", safe_target, "-q", "--tb=short"]
        result = subprocess.run(args, cwd=workspace_dir, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=60)
        combined = result.stdout + "\n" + result.stderr if result.stderr else result.stdout
        is_pass = result.returncode == 0
        if result.returncode == 5:
            return tool_result("success", "No tests collected", path=workspace_dir,
                               summary="无测试文件或测试被跳过")
        return tool_result("success" if is_pass else "error", combined,
                           path=workspace_dir, returncode=result.returncode,
                           stdout=result.stdout, stderr=result.stderr,
                           summary=f"测试 {'通过' if is_pass else '失败'}",
                           error_type=None if is_pass else "test_failure")
    except FileNotFoundError:
        return tool_result("error", "pytest not installed. Run 'pip install pytest' first.",
                           error_type="missing_tool", summary="pytest 未安装")
    except Exception as e:
        return tool_result("error", str(e), summary=f"pytest 异常: {e}")


def run_lint(target: str) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        safe_target = _resolve_dir(target)
        args = ["flake8", safe_target, "--max-line-length=120"]
        result = subprocess.run(args, cwd=workspace_dir, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=30)
        output = result.stdout.strip()
        if not output and result.returncode == 0:
            return tool_result("success", "No lint errors", path=safe_target,
                               summary=f"{target}: 无 lint 错误")
        return tool_result("success", output if output else result.stderr, path=safe_target,
                           stdout=output, stderr=result.stderr,
                           summary=f"{target}: lint 检查完成")
    except FileNotFoundError:
        return tool_result("error", "flake8 not installed. Run 'pip install flake8' first.",
                           error_type="missing_tool", summary="flake8 未安装")
    except Exception as e:
        return tool_result("error", str(e), summary=f"flake8 异常: {e}")


def rag_search(query: str, top_k: int = 5) -> str:
    """RAG 知识检索工具，供 Agent 调用。"""
    try:
        from agent.backend.rag import rag_search as _rag_search
        result = _rag_search(query, top_k)
        results = result.get("results", [])
        error = result.get("error")
        if error:
            return tool_result("error", error, summary=f"RAG 检索失败: {error}",
                               error_type="rag_error")
        if not results:
            return tool_result("success",
                               json.dumps(result, ensure_ascii=False, indent=2),
                               summary=f"RAG 检索'{query}': 无结果（知识库可能为空）")
        return tool_result(
            "success",
            json.dumps(result, ensure_ascii=False, indent=2),
            summary=f"RAG 检索'{query}': 返回{len(results)}条结果",
            rag_sources=results,
        )
    except ImportError:
        return tool_result("error", "RAG module not available (missing chromadb?)",
                           error_type="missing_dependency", summary="RAG 模块不可用")
    except Exception as e:
        return tool_result("error", f"rag_search failed: {e}",
                           error_type="rag_error", summary=f"RAG 检索异常: {e}")


available_functions = {
    "execute_bash": execute_bash,
    "list_files": list_files,
    "read_file": read_file,
    "read_file_range": read_file_range,
    "write_file": write_file,
    "apply_patch": apply_patch,
    "search_code": search_code,
    "web_search": web_search,
    "fetch_url": fetch_url,
    "get_git_diff": get_git_diff,
    "run_tests": run_tests,
    "run_lint": run_lint,
    "rag_search": rag_search,
}
