"""Output formatting helpers."""

from __future__ import annotations

import json
import sys
from typing import Any


def print_json(data: Any) -> None:
    """Print data as pretty-printed JSON."""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def print_table(rows: list[dict], columns: list[str] | None = None) -> None:
    """Print a list of dicts as an aligned table.

    If columns is not specified, all keys from the first row are used.
    """
    if not rows:
        print("(empty)")
        return

    keys = columns or list(rows[0].keys())
    widths = {
        k: max(
            len(k),
            max((len(str(r.get(k, ""))) for r in rows), default=0),
        )
        for k in keys
    }

    header = "  ".join(k.ljust(widths[k]) for k in keys)
    print(header)
    print("-" * len(header))

    for row in rows:
        line = "  ".join(str(row.get(k, "")).ljust(widths[k]) for k in keys)
        print(line)


def format_result(result: dict, table: bool = False) -> None:
    """Auto-format API response based on presence of items list."""
    data = result.get("data")
    if data is None:
        print("No data")
        return

    if table and isinstance(data, dict) and "items" in data:
        items = data["items"]
        if items and isinstance(items, list) and isinstance(items[0], dict):
            total = data.get("total", len(items))
            page = data.get("page", "-")
            psize = data.get("page_size", "-")
            print(f"Total: {total}  Page: {page}/{psize}")
            print()
            print_table(items)
            return

    print_json(result)
