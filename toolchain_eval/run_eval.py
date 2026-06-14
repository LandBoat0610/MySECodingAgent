"""
工具链基准评测运行器。

用法:
    # 完整运行（创建数据集 + 创建任务 + 启动 + 等待完成 + 打印报告 + 保存 MD）
    python -m toolchain_eval.run_eval

    # 仅创建数据集（不运行评测）
    python -m toolchain_eval.run_eval --create-dataset-only

    # 指定已有数据集 ID，直接创建并运行评测任务
    python -m toolchain_eval.run_eval --dataset-id <id>

    # 自定义评测方法
    python -m toolchain_eval.run_eval --eval-method combined

    # 仅打印已有任务报告
    python -m toolchain_eval.run_eval --task-id <id> --report-only

依赖:
    - agent_platform.db 已初始化
    - OPENAI_API_KEY 环境变量已设置
"""

from __future__ import annotations

import json
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env", override=True)

os.environ.setdefault("SKIP_BASH_APPROVAL", "1")

DATASET_FILE = Path(__file__).resolve().parent / "toolchain_baseline.json"
DATASET_NAME = "toolchain-baseline-v1"
DEFAULT_EVAL_METHOD = "result"
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_MINUTES = 120


def check_environment() -> bool:
    """检查 LLM API 和网络搜索连通性。返回 True 表示全部通过。"""
    import json as _json
    all_ok = True

    print("[环境检查] LLM API ...")
    try:
        from agent.backend.llm import client
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": "Say 'ok' in one word."}],
            max_tokens=10,
        )
        reply = resp.choices[0].message.content
        print(f"  [OK] 模型回复: \"{reply}\"")
    except Exception as e:
        print(f"  [FAIL] {e}")
        all_ok = False

    print("[环境检查] 网络搜索 (DuckDuckGo) ...")
    try:
        from agent.backend.tools import web_search
        result = web_search("test connectivity")
        data = _json.loads(result)
        if data["status"] == "success":
            res = _json.loads(data["output"])
            print(f"  [OK] 搜索到 {len(res['results'])} 条结果")
        else:
            print(f"  [FAIL] {data['output'][:120]}")
            all_ok = False
    except Exception as e:
        print(f"  [FAIL] {e}")
        all_ok = False

    return all_ok


def _now() -> str:
    return datetime.now().isoformat()


def _pprint_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_dataset() -> Dict[str, Any]:
    if not DATASET_FILE.exists():
        raise FileNotFoundError(f"数据集文件不存在: {DATASET_FILE}")
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_existing_dataset(name: str) -> Optional[str]:
    from agent.backend.evaluation_jobs import list_datasets
    for ds in list_datasets():
        if ds.get("name") == name:
            return ds["id"]
    return None


def create_or_reuse_dataset(force_create: bool = False, include: Optional[str] = None, exclude: Optional[str] = None) -> str:
    from agent.backend.database import init_db
    init_db()

    from agent.backend.evaluation_jobs import create_dataset_from_payload, list_datasets

    existing_id = find_existing_dataset(DATASET_NAME)
    if existing_id and not force_create:
        print(f"[数据集] 已存在: {DATASET_NAME} (id={existing_id})，复用已有数据集。")
        print("  若要强制重建请使用 --force-create-dataset")
        return existing_id

    if existing_id and force_create:
        from agent.backend.evaluation_jobs import delete_dataset
        print(f"[数据集] 删除旧数据集 {existing_id} ...")
        try:
            delete_dataset(existing_id, cascade_tasks=True)
        except (ValueError, LookupError) as e:
            print(f"  删除失败: {e}")

    payload = load_dataset()
    items = payload["items"]

    if include:
        include_keys = set(include.split(","))
        items = [it for it in items if any(k in it.get("id", "") for k in include_keys)]
        print(f"[过滤] include={include} → 选中 {len(items)} 条")
    if exclude:
        exclude_keys = set(exclude.split(","))
        items = [it for it in items if not any(k in it.get("id", "") for k in exclude_keys)]
        print(f"[过滤] exclude={exclude} → 剩余 {len(items)} 条")

    if not items:
        raise SystemExit("过滤后无测试用例，请检查 include/exclude 参数。")

    filtered_payload = dict(payload, items=items)
    print(f"[数据集] 创建中: {DATASET_NAME} ({len(items)} 条用例) ...")
    result = create_dataset_from_payload(filtered_payload)
    print(f"[数据集] 创建完成: id={result['id']}")
    return result["id"]


def create_and_start_eval(
    dataset_id: str,
    eval_method: str,
    task_label: Optional[str] = None,
    concurrency: int = 1,
) -> str:
    from agent.backend.evaluation_jobs import create_eval_task, start_eval_task

    if task_label is None:
        task_label = f"toolchain-{eval_method}-{datetime.now().strftime('%m%d-%H%M')}"

    print(f"[任务] 创建评测任务: {task_label} (method={eval_method}) ...")
    task = create_eval_task(task_label, dataset_id, eval_method)
    task_id = task["id"]
    print(f"[任务] 创建完成: id={task_id}")

    if concurrency > 1:
        print(f"[任务] 并发执行 (concurrency={concurrency}) ...")
    print(f"[任务] 启动评测 ...")
    task = start_eval_task(task_id, concurrency=concurrency)
    print(f"[任务] 已启动: status={task['status']}, total={task['total_items']}")
    return task_id


def wait_for_completion(task_id: str) -> Dict[str, Any]:
    from agent.backend.evaluation_jobs import get_eval_task

    deadline = time.time() + POLL_TIMEOUT_MINUTES * 60
    print(f"[等待] 等待评测完成 (最长 {POLL_TIMEOUT_MINUTES} 分钟) ...")

    last_passed = -1
    while time.time() < deadline:
        task = get_eval_task(task_id)
        status = task["status"]
        completed = task["completed_items"]
        total = task["total_items"]
        passed = task["passed_count"]
        failed = task["failed_count"]

        if completed > last_passed:
            print(f"  进度: {completed}/{total} 完成, 通过={passed}, 失败={failed}, 状态={status}")
            last_passed = completed

        if status in ("completed", "failed", "cancelled"):
            print(f"[等待] 评测结束: status={status}")
            return task

        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"[等待] 超时 ({POLL_TIMEOUT_MINUTES} 分钟)，强制停止轮询。")
    return get_eval_task(task_id)


REPORT_FILE = _PROJECT_ROOT / "toolchain_eval_report.md"


def generate_report(task_id: str) -> str:
    from agent.backend.evaluation_jobs import (
        get_eval_task,
        list_task_results,
    )

    task = get_eval_task(task_id)
    results = list_task_results(task_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = task["total_items"]
    passed = task["passed_count"]
    failed = task["failed_count"]
    rate = passed / total * 100 if total > 0 else 0

    lines: List[str] = []
    lines.append("# 工具链基准评测报告")
    lines.append("")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| 生成时间 | {now} |")
    lines.append(f"| 任务名称 | {task['name']} |")
    lines.append(f"| 任务 ID | {task['id']} |")
    lines.append(f"| 状态 | {task['status']} |")
    lines.append(f"| 评测方法 | {task['eval_method']} |")
    lines.append(f"| 模型快照 | {task['agent_model_snapshot'] or '默认'} |")
    lines.append(f"| 用例总数 | {total} |")
    lines.append(f"| 通过数 | {passed} |")
    lines.append(f"| 失败数 | {failed} |")
    lines.append(f"| 通过率 | {rate:.1f}% |")
    lines.append("")

    total_elapsed_s = 0.0

    lines.append("## 逐条结果")
    lines.append("")
    lines.append(f"| # | 用例 ID | 耗时 | 状态 | 通过 | 备注 |")
    lines.append(f"| --- | --- | --- | --- | --- | --- |")
    for r in results:
        idx = r["item_index"]
        item_id = r.get("item_key") or str(idx)
        status = r["status"]
        passed_flag = "PASS" if r.get("passed") else ("FAIL" if r.get("passed") is False else "N/A")
        note = ""
        if r.get("run_error"):
            note = r["run_error"].replace("\n", " ")[:120]

        elapsed = ""
        sa = r.get("started_at")
        fa = r.get("finished_at")
        if sa and fa:
            try:
                from datetime import datetime as _dt
                t0 = _dt.fromisoformat(sa)
                t1 = _dt.fromisoformat(fa)
                delta = (t1 - t0).total_seconds()
                total_elapsed_s += delta
                if delta < 60:
                    elapsed = f"{delta:.0f}s"
                else:
                    m = int(delta // 60)
                    s = int(delta % 60)
                    elapsed = f"{m}m{s:02d}s"
            except Exception:
                elapsed = ""

        lines.append(f"| {idx} | {item_id} | {elapsed} | {status} | {passed_flag} | {note} |")
    lines.append("")

    if total_elapsed_s > 0:
        ts = total_elapsed_s
        if ts < 60:
            total_str = f"{ts:.0f}s"
        else:
            tm = int(ts // 60)
            ts_rem = int(ts % 60)
            total_str = f"{tm}m{ts_rem:02d}s"
        lines.insert(-1, f"| 总耗时(串行) | {total_str} |")
        lines.insert(-1, f"| 平均耗时 | {total_elapsed_s / total:.0f}s |")

    lines.append("## 按工具类别统计")
    lines.append("")
    categories: Dict[str, Dict[str, int]] = {}
    for r in results:
        item_id = r.get("item_key") or str(r["item_index"])
        cat = item_id.split("_")[0] if "_" in item_id else "other"
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r.get("passed"):
            categories[cat]["passed"] += 1

    cat_label_map = {
        "bash": "execute_bash",
        "read": "read_file",
        "range": "read_file_range",
        "write": "write_file",
        "search": "web_search",
        "srch": "search_code",
        "fetch": "fetch_url",
        "list": "list_files",
        "patch": "apply_patch",
        "diff": "get_git_diff",
        "test": "run_tests",
        "lint": "run_lint",
        "combo": "组合场景",
    }

    lines.append(f"| 类别 | 总数 | 通过 | 通过率 |")
    lines.append(f"| --- | --- | --- | --- |")
    for cat in sorted(categories.keys()):
        c = categories[cat]
        cr = c["passed"] / c["total"] * 100 if c["total"] else 0
        label = cat_label_map.get(cat, cat)
        lines.append(f"| {label} | {c['total']} | {c['passed']} | {cr:.0f}% |")
    lines.append("")

    report = "\n".join(lines)
    return report


def print_and_save_report(task_id: str) -> None:
    report = generate_report(task_id)
    print(report)

    try:
        REPORT_FILE.write_text(report, encoding="utf-8")
        print(f"\n[报告] 已保存至: {REPORT_FILE}")
    except OSError as e:
        print(f"\n[警告] 保存报告文件失败: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="工具链基准评测运行器")
    parser.add_argument(
        "--create-dataset-only",
        action="store_true",
        help="仅创建/更新数据集，不运行评测",
    )
    parser.add_argument(
        "--force-create-dataset",
        action="store_true",
        help="强制重建数据集（删除旧数据集及关联任务）",
    )
    parser.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help="使用已有的数据集 ID（跳过数据集创建步骤）",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="仅打印已有任务的报告",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="与 --task-id 配合使用，仅打印报告不等待",
    )
    parser.add_argument(
        "--eval-method",
        type=str,
        default=DEFAULT_EVAL_METHOD,
        choices=["result", "process", "combined"],
        help=f"评测方法 (默认: {DEFAULT_EVAL_METHOD})",
    )
    parser.add_argument(
        "--task-label",
        type=str,
        default=None,
        help="评测任务名称标签",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="启动评测后不等待，立即返回",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="跳过环境连通性检查",
    )
    parser.add_argument(
        "--include",
        type=str,
        default=None,
        help="仅运行匹配关键词的用例（逗号分隔，如 bash,read）",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default=None,
        help="排除匹配关键词的用例（逗号分隔，如 search,fetch,diff,test,lint）",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="并发执行评测的线程数（默认 1，即串行）",
    )

    args = parser.parse_args()

    if not args.skip_env_check:
        print("[环境检查] 检测 LLM API 和网络搜索连通性...")
        if not check_environment():
            print("\n[中止] 环境检查未通过，评测不会运行。修复后重试，或使用 --skip-env-check 跳过。")
            sys.exit(1)
        print("[环境检查] 全部通过。\n")

    # 纯报告模式
    if args.report_only and args.task_id:
        print_and_save_report(args.task_id)
        return

    if args.task_id and not args.report_only:
        wait_for_completion(args.task_id)
        print_and_save_report(args.task_id)
        return

    # 确定 dataset_id
    if args.dataset_id:
        dataset_id = args.dataset_id
        print(f"[配置] 使用已有数据集: {dataset_id}")
    else:
        dataset_id = create_or_reuse_dataset(
            force_create=args.force_create_dataset,
            include=args.include,
            exclude=args.exclude,
        )

    if args.create_dataset_only:
        print("[完成] 数据集已就绪。")
        return

    task_id = create_and_start_eval(
        dataset_id,
        eval_method=args.eval_method,
        task_label=args.task_label,
        concurrency=args.concurrency,
    )

    if args.no_wait:
        print(f"[完成] 评测已在后台启动。task_id={task_id}")
        print(f"  稍后可通过以下命令查看报告:")
        print(f"  python -m toolchain_eval.run_eval --task-id {task_id}")
        return

    wait_for_completion(task_id)
    print_and_save_report(task_id)


if __name__ == "__main__":
    main()
