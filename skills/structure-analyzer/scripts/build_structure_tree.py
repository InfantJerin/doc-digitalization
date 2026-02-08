#!/usr/bin/env python3
"""Build a hierarchical structure tree from heading entries."""

from __future__ import annotations

import json
import sys


def build_tree(entries: list[dict], total_pages: int) -> dict:
    root = {
        "id": "root",
        "title": "Document",
        "level": 0,
        "start_page": 1,
        "end_page": total_pages,
        "children": [],
    }

    stack: list[tuple[int, dict]] = [(0, root)]

    for idx, entry in enumerate(entries, start=1):
        node = {
            "id": f"node_{idx}",
            "title": entry.get("title", f"Section {idx}"),
            "level": int(entry.get("level", 1)),
            "start_page": int(entry.get("page", 1)),
            "end_page": total_pages,
            "children": [],
        }

        while stack and stack[-1][0] >= node["level"]:
            stack.pop()

        parent = stack[-1][1] if stack else root
        parent["children"].append(node)
        stack.append((node["level"], node))

    flat = []

    def walk(node: dict) -> None:
        if node["level"] > 0:
            flat.append(node)
        for child in node["children"]:
            walk(child)

    walk(root)
    flat.sort(key=lambda item: item["start_page"])

    for idx, node in enumerate(flat):
        next_start = flat[idx + 1]["start_page"] if idx + 1 < len(flat) else total_pages + 1
        node["end_page"] = max(node["start_page"], next_start - 1)

    return root


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_structure_tree.py <entries-json> <total-pages>", file=sys.stderr)
        return 1

    entries = json.loads(sys.argv[1])
    total_pages = int(sys.argv[2])
    root = build_tree(entries, total_pages)
    print(json.dumps(root, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
