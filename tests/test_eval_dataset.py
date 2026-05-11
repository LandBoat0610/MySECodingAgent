# tests/test_eval_dataset.py
"""测试 eval_dataset 模块：数据集规范化、序列化与解析。"""
from agent.backend.eval_dataset import (
    normalize_dataset_payload,
    canonical_dataset_document,
    load_dataset_items_from_path,
    parse_upload_json_bytes,
)
import json
import os
import sys
import pytest
from tempfile import NamedTemporaryFile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestNormalizeDatasetPayload:
    def test_minimal_valid(self):
        raw = {"items": [{"description": "test task"}]}
        name, items = normalize_dataset_payload(raw)
        assert name in ("", "unnamed")
        assert len(items) == 1
        assert items[0]["description"] == "test task"

    def test_with_custom_name(self):
        raw = {"name": "My Dataset", "items": [{"description": "t"}]}
        name, items = normalize_dataset_payload(raw)
        assert name == "My Dataset"

    def test_with_expected_output(self):
        raw = {"items": [{"description": "t", "expected_output": "result"}]}
        _, items = normalize_dataset_payload(raw)
        assert items[0]["expected_output"] == "result"

    def test_with_test_cases(self):
        raw = {
            "items": [
                {
                    "description": "t",
                    "test_cases": [
                        {"input": "in1", "expected": "out1"},
                        {"input": "in2", "expected": "out2"},
                    ],
                }
            ]
        }
        _, items = normalize_dataset_payload(raw)
        assert len(items[0]["test_cases"]) == 2
        assert items[0]["test_cases"][0]["input"] == "in1"
        assert items[0]["test_cases"][0]["expected"] == "out1"

    def test_uses_task_field_as_description(self):
        raw = {"items": [{"task": "build something"}]}
        _, items = normalize_dataset_payload(raw)
        assert items[0]["description"] == "build something"

    def test_description_takes_precedence_over_task(self):
        raw = {"items": [{"description": "desc", "task": "task"}]}
        _, items = normalize_dataset_payload(raw)
        assert items[0]["description"] == "desc"

    def test_item_id_from_field(self):
        raw = {"items": [{"id": "item-001", "description": "t"}]}
        _, items = normalize_dataset_payload(raw)
        assert items[0]["id"] == "item-001"

    def test_item_id_defaults_to_index(self):
        raw = {"items": [{"description": "first"}, {"description": "second"}]}
        _, items = normalize_dataset_payload(raw)
        assert items[0]["id"] == "0"
        assert items[1]["id"] == "1"

    # Error cases
    def test_non_dict_input_raises(self):
        with pytest.raises(ValueError, match="必须是 JSON 对象"):
            normalize_dataset_payload([])

    def test_items_not_list_raises(self):
        with pytest.raises(ValueError, match="非空数组"):
            normalize_dataset_payload({"items": "not-list"})

    def test_empty_items_raises(self):
        with pytest.raises(ValueError, match="非空数组"):
            normalize_dataset_payload({"items": []})

    def test_item_not_dict_raises(self):
        with pytest.raises(ValueError, match="必须是对象"):
            normalize_dataset_payload({"items": ["string_item"]})

    def test_item_missing_description_raises(self):
        with pytest.raises(ValueError, match="缺少 description"):
            normalize_dataset_payload({"items": [{"foo": "bar"}]})

    def test_test_cases_not_list_raises(self):
        with pytest.raises(ValueError, match="test_cases 必须是数组"):
            normalize_dataset_payload({"items": [{"description": "t", "test_cases": "bad"}]})

    def test_test_case_item_not_dict_raises(self):
        with pytest.raises(ValueError, match="必须是对象"):
            normalize_dataset_payload(
                {"items": [{"description": "t", "test_cases": ["bad"]}]}
            )

    def test_expected_output_not_string_raises(self):
        with pytest.raises(ValueError, match="expected_output 必须是字符串"):
            normalize_dataset_payload({"items": [{"description": "t", "expected_output": 123}]})


class TestCanonicalDatasetDocument:
    def test_roundtrip(self):
        items = [{"id": "0", "description": "t", "expected_output": None, "test_cases": []}]
        doc = canonical_dataset_document("my_ds", items)
        assert doc["name"] == "my_ds"
        assert doc["items"] == items


class TestLoadDatasetItemsFromPath:
    def test_loads_and_normalizes(self):
        content = {"name": "Loaded DS", "items": [{"description": "task1"}]}
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(content, f)
            path = f.name
        try:
            name, items = load_dataset_items_from_path(path)
            assert name == "Loaded DS"
            assert len(items) == 1
            assert items[0]["description"] == "task1"
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset_items_from_path("/nonexistent/path.json")


class TestParseUploadJsonBytes:
    def test_valid_bytes(self):
        data = b'{"items": [{"description": "test"}]}'
        name, items = parse_upload_json_bytes(data)
        assert len(items) == 1

    def test_invalid_utf8_bytes(self):
        data = b'\xff\xfe\x00'
        with pytest.raises(ValueError, match="无效的 JSON 文件"):
            parse_upload_json_bytes(data)

    def test_invalid_json_bytes(self):
        data = b'not json at all'
        with pytest.raises(ValueError, match="无效的 JSON 文件"):
            parse_upload_json_bytes(data)
