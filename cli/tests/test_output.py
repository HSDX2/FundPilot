"""Tests for output formatting helpers."""

from __future__ import annotations

import io
import json
import sys

from fundpilot.output import format_result, print_json, print_table


class TestPrintJson:
    def test_pretty_prints(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_json({"a": 1, "b": [2, 3]})
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        data = json.loads(output)
        assert data == {"a": 1, "b": [2, 3]}

    def test_chinese_characters(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_json({"name": "测试", "value": 100})
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        data = json.loads(output)
        assert data["name"] == "测试"


class TestPrintTable:
    def test_basic_table(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_table(
            [{"code": "000001", "name": "基金A"}, {"code": "000011", "name": "基金B"}],
            columns=["code", "name"],
        )
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        assert "000001" in output
        assert "000011" in output
        assert "基金A" in output
        assert "基金B" in output
        assert "code" in output
        assert "name" in output

    def test_auto_columns(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_table([{"a": 1, "b": 2}])
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        assert "a" in output
        assert "b" in output

    def test_empty_list(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_table([])
        sys.stdout = sys.__stdout__
        assert "(empty)" in buf.getvalue()

    def test_missing_values_default_to_empty(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        print_table(
            [{"code": "000001"}, {"code": "000011", "name": "B"}],
            columns=["code", "name"],
        )
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        assert "000001" in output
        assert "B" in output


class TestFormatResult:
    def test_no_data(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        format_result({"success": True, "data": None})
        sys.stdout = sys.__stdout__
        assert "No data" in buf.getvalue()

    def test_json_default(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        format_result({"success": True, "data": {"items": [{"a": 1}]}})
        sys.stdout = sys.__stdout__
        output = json.loads(buf.getvalue())
        assert output["data"]["items"] == [{"a": 1}]

    def test_table_mode_with_items(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        format_result(
            {
                "success": True,
                "data": {
                    "items": [{"code": "000001", "name": "Test"}],
                    "total": 1,
                    "page": 1,
                    "page_size": 20,
                },
            },
            table=True,
        )
        sys.stdout = sys.__stdout__
        output = buf.getvalue()
        assert "Total: 1" in output
        assert "000001" in output
        assert "Test" in output

    def test_table_mode_non_items_falls_back_to_json(self) -> None:
        buf = io.StringIO()
        sys.stdout = buf
        format_result({"success": True, "data": {"key": "value"}}, table=True)
        sys.stdout = sys.__stdout__
        output = json.loads(buf.getvalue())
        assert output["data"]["key"] == "value"
