#!/usr/bin/env python3
"""Import Confluence scheduling PDF text dumps into roadmaps.json."""

from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path

from confluence_parse import parse_schedule_text

BOX = Path(__file__).resolve().parent
PROD = BOX.parent
SAFE = PROD / "safe_box"
STORE = SAFE / "roadmaps.json"
IMPORTS = SAFE / "imports"

QUARTER_FILES = [
    ("Scheduling-Q3 2026-280726-194407.txt", "Q3 2026"),
    ("Scheduling-Q4 2026-280726-194336.txt", "Q4 2026"),
    ("Scheduling-Q1 2027-280726-191320.txt", "Q1 2027"),
    ("Scheduling-Q2 2027-280726-194437.txt", "Q2 2027"),
]


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def load_store() -> dict:
    if STORE.is_file():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "product": "great-road-mapper",
        "chip": "CO.BBC-001-GRM",
        "templates": {},
        "product_lines": [
            {"id": "line-bsg", "name": "BSG", "hue": "amber"},
            {"id": "line-ng", "name": "NG", "hue": "rose"},
        ],
        "roles": [],
        "people": [],
        "titles": [],
    }


def main() -> int:
    SAFE.mkdir(parents=True, exist_ok=True)
    data = load_store()
    by_code = {
        (t.get("code") or "").upper(): t for t in data.get("titles") or []
    }
    added = 0
    updated = 0
    all_parsed = 0

    for fname, quarter in QUARTER_FILES:
        path = IMPORTS / fname
        if not path.is_file():
            print("missing", path)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_schedule_text(text, quarter)
        all_parsed += len(parsed)
        print(f"{quarter}: parsed {len(parsed)} titles from {fname}")
        for row in parsed:
            code = (row.get("code") or "").upper()
            if not code:
                continue
            existing = by_code.get(code)
            if existing:
                # refresh phases from PDF (locked truth)
                existing["name"] = row.get("name") or existing.get("name")
                existing["math_model"] = row.get("math_model") or existing.get(
                    "math_model"
                )
                existing["complexity"] = row.get("complexity") or existing.get(
                    "complexity"
                )
                existing["quarter"] = row.get("quarter") or existing.get("quarter")
                existing["release_date"] = row.get("release_date") or existing.get(
                    "release_date"
                )
                existing["phases"] = row.get("phases") or existing.get("phases")
                existing["kind"] = row.get("kind") or existing.get("kind") or "title"
                existing["product_line_id"] = row.get("product_line_id") or existing.get(
                    "product_line_id"
                )
                existing["notes"] = row.get("notes") or existing.get("notes")
                if row.get("twin_code"):
                    existing["twin_code"] = row["twin_code"]
                if row.get("rebrand_of"):
                    existing["rebrand_of"] = row["rebrand_of"]
                    existing["nucleus_code"] = row.get("nucleus_code") or row.get(
                        "rebrand_of"
                    )
                if row.get("theme"):
                    existing["theme"] = row["theme"]
                existing["updated"] = int(time.time())
                updated += 1
            else:
                t = {
                    "id": new_id("ttl"),
                    "code": row["code"],
                    "name": row.get("name") or row["code"],
                    "subtitle": row.get("math_model") or "",
                    "product_line_id": row.get("product_line_id") or "line-bsg",
                    "complexity": row.get("complexity") or "medium",
                    "status": "active",
                    "kind": row.get("kind") or "title",
                    "theme": row.get("theme") or "",
                    "math_model": row.get("math_model") or "",
                    "notes": row.get("notes") or "",
                    "release_date": row.get("release_date") or "",
                    "quarter": row.get("quarter") or quarter,
                    "bsg_twin": row.get("bsg_twin") or "",
                    "bsg_release_date": row.get("bsg_release_date") or "",
                    "twin_code": row.get("twin_code") or "",
                    "rebrand_of": row.get("rebrand_of") or "",
                    "nucleus_code": row.get("nucleus_code") or "",
                    "assignments": [],
                    "phases": row.get("phases") or [],
                    "created": int(time.time()),
                    "updated": int(time.time()),
                }
                data.setdefault("titles", []).append(t)
                by_code[code] = t
                added += 1

    data["updated"] = int(time.time())
    STORE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"done: parsed={all_parsed} added={added} updated={updated} "
        f"total_titles={len(data.get('titles') or [])}"
    )
    print("store", STORE)
    # sample buckets
    from schedule import pipeline_bucket, current_phase_name

    for t in (data.get("titles") or [])[:5]:
        print(
            " ",
            t.get("code"),
            t.get("name")[:40] if t.get("name") else "",
            "phases",
            len(t.get("phases") or []),
            "rel",
            t.get("release_date"),
            "lane",
            pipeline_bucket(t.get("phases") or [], release_fallback=t.get("release_date")),
            "phase",
            current_phase_name(t.get("phases") or []),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
