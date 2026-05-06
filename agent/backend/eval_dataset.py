"""解析与校验评测数据集 JSON。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


def normalize_dataset_payload(raw: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    if not isinstance(raw, dict):
        raise ValueError("数据集必须是 JSON 对象")

    name = str(raw.get("name") or "").strip() or "unnamed"

    items = raw.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError('数据集必须包含非空数组 "items"')

    normalized: List[Dict[str, Any]] = []
    for i, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"items[{i}] 必须是对象")

        desc = raw_item.get("description") or raw_item.get("task") or ""
        desc = str(desc).strip()
        if not desc:
            raise ValueError(f"items[{i}] 缺少 description 或 task")

        test_cases = raw_item.get("test_cases")
        if test_cases is None:
            test_cases = []
        if not isinstance(test_cases, list):
            raise ValueError(f"items[{i}].test_cases 必须是数组")

        cleaned_cases: List[Dict[str, Any]] = []
        for j, tc in enumerate(test_cases):
            if not isinstance(tc, dict):
                raise ValueError(f"items[{i}].test_cases[{j}] 必须是对象")
            cleaned_cases.append(
                {
                    "input": tc.get("input", ""),
                    "expected": tc.get("expected", ""),
                }
            )

        expected_output = raw_item.get("expected_output")
        if expected_output is not None and not isinstance(expected_output, str):
            raise ValueError(f"items[{i}].expected_output 必须是字符串")

        normalized.append(
            {
                "id": str(raw_item.get("id", i)),
                "description": desc,
                "expected_output": expected_output if isinstance(expected_output, str) else None,
                "test_cases": cleaned_cases,
            }
        )

    return name, normalized


def canonical_dataset_document(name: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"name": name, "items": items}


def load_dataset_items_from_path(storage_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    with open(storage_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return normalize_dataset_payload(raw)


def parse_upload_json_bytes(data: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"无效的 JSON 文件: {e}") from e
    return normalize_dataset_payload(raw)
