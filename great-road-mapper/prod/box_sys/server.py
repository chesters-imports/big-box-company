#!/usr/bin/env python3
"""Great Road Mapper — personal multi-title production board · CO.BBC-001-GRM"""

from __future__ import annotations

import json
import secrets
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from q1_2027_seed import Q1_2027_TITLES
from schedule import (
    PIPELINE_BUCKETS,
    apply_release,
    align_all_to_spine,
    align_title_to_spine,
    cleanup_all_labels,
    current_phase_name,
    default_templates,
    event_role,
    expected_spine_for_title,
    lifecycle_label,
    normalize_complexity,
    normalize_event_name,
    normalize_lifecycle,
    normalize_phases_list,
    parse_date,
    phase_status,
    cascade_earlier_phases,
    pipeline_bucket,
    plan_backward_make_room,
    quarter_key,
    quarter_label,
    rename_label_everywhere,
    spine_definition,
    spine_slot,
)

BOX_SYS = Path(__file__).resolve().parent
PROD = BOX_SYS.parent
SAFE_BOX = PROD / "safe_box"
STORE = SAFE_BOX / "roadmaps.json"
HOST = "127.0.0.1"
PORT = 42960


def ensure_dirs() -> None:
    SAFE_BOX.mkdir(parents=True, exist_ok=True)


def empty_store() -> dict[str, Any]:
    from spine import default_product_types

    return {
        "version": 1,
        "product": "great-road-mapper",
        "chip": "CO.BBC-001-GRM",
        "templates": default_templates(),
        "product_types": default_product_types(),
        "product_lines": [
            {"id": "line-bsg", "name": "BSG", "hue": "amber"},
            {"id": "line-ng", "name": "NG", "hue": "rose"},
        ],
        "roles": [
            "Game Design",
            "Math",
            "Static Art",
            "Previs",
            "FX / Animation",
            "Audio",
            "Dev",
            "QA",
            "Producer",
        ],
        "people": [],
        "titles": [],
        "updated": int(time.time()),
    }


def load_store() -> dict[str, Any]:
    from spine import default_product_types

    ensure_dirs()
    if not STORE.is_file():
        data = empty_store()
        save_store(data)
        return data
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = empty_store()
    if not data.get("templates"):
        data["templates"] = default_templates()
    else:
        # ensure new keys exist
        defs = default_templates()
        for k, v in defs.items():
            data["templates"].setdefault(k, v)
    # phases + workstream portions — re-seed built-ins when flag missing
    if not data.get("product_types_ws_portion_v1"):
        data["product_types"] = default_product_types()
        data["product_types_phases_v2"] = True
        data["product_types_duration_v1"] = True
        data["product_types_workstreams_v1"] = True
        data["product_types_ws_portion_v1"] = True
    elif not data.get("product_types"):
        data["product_types"] = default_product_types()
    # template vs variation (structure shared; numbers per scale)
    from spine import ensure_product_type_models

    if not data.get("product_types_template_v1"):
        data["product_types"] = ensure_product_type_models(
            list(data.get("product_types") or [])
        )
        data["product_types_template_v1"] = True
    else:
        data["product_types"] = ensure_product_type_models(
            list(data.get("product_types") or [])
        )
    data.setdefault("product_lines", empty_store()["product_lines"])
    data.setdefault("roles", empty_store()["roles"])
    data.setdefault("people", [])
    data.setdefault("titles", [])
    return data


def save_store(data: dict[str, Any]) -> None:
    ensure_dirs()
    data["updated"] = int(time.time())
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(STORE)


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def vocab_from_titles(titles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shared phase/gate labels with usage counts."""
    bag: dict[str, dict[str, Any]] = {}
    for t in titles:
        for p in t.get("phases") or []:
            name = normalize_event_name(p.get("name"))
            role = p.get("role") or event_role(name, p.get("kind"))
            if name not in bag:
                bag[name] = {"name": name, "role": role, "count": 0}
            bag[name]["count"] += 1
            # prefer gate if any instance is gate
            if role == "gate":
                bag[name]["role"] = "gate"
    rows = list(bag.values())
    rows.sort(key=lambda r: (0 if r["role"] == "phase" else 1, r["name"].lower()))
    return rows


def enrich_title(t: dict[str, Any]) -> dict[str, Any]:
    import secrets as _secrets

    phases = t.get("phases") or []
    # ensure workstream ids so ticket Edit can target ↳ lines
    for p in phases:
        for ws in p.get("workstreams") or []:
            if isinstance(ws, dict) and not ws.get("id"):
                ws["id"] = f"ws-{_secrets.token_hex(4)}"
    out = dict(t)
    # split for UI
    out["phase_events"] = [
        p
        for p in phases
        if (p.get("role") or event_role(p.get("name"), p.get("kind"))) == "phase"
    ]
    out["gate_events"] = [
        p
        for p in phases
        if (p.get("role") or event_role(p.get("name"), p.get("kind"))) == "gate"
    ]
    expected = expected_spine_for_title(t)
    present = {
        spine_slot(p.get("name")) or p.get("name")
        for p in phases
        if p.get("start") or p.get("end")
    }
    out["spine_expected"] = expected
    out["spine_missing"] = [n for n in expected if n not in present]
    out["spine_off"] = [
        p.get("name")
        for p in phases
        if p.get("spine") is False or not spine_slot(p.get("name"))
    ]
    kind = (t.get("kind") or "title").strip().lower()
    out["kind"] = kind
    from schedule import events_for_board

    board_ph = events_for_board(
        phases, kind=kind, product_line_id=t.get("product_line_id")
    )
    out["current_phase"] = current_phase_name(board_ph)
    # Lifecycle = operator intent (planning / production / scope change …)
    # Pipeline lane (bucket) = where the calendar says we are — separate.
    life = normalize_lifecycle(t.get("status"))
    out["lifecycle"] = life
    out["lifecycle_label"] = lifecycle_label(life)
    out["board_status"] = life  # compat for older UI
    out["status"] = life  # normalize on read so clients see new keys
    out["complexity"] = normalize_complexity(t.get("complexity"))
    out["bucket"] = pipeline_bucket(
        phases,
        release_fallback=t.get("release_date"),
        kind=kind,
        product_line_id=t.get("product_line_id"),
    )
    out["lane"] = out["bucket"]  # clearer alias
    rel = parse_date(t.get("release_date"))
    qk = quarter_key(rel, t.get("quarter"))
    out["quarter_key"] = qk
    out["quarter_label"] = t.get("quarter") or quarter_label(qk)
    # twin surface
    out["has_twin"] = bool(
        t.get("twin_code") or t.get("bsg_twin") or t.get("nucleus_code") or t.get("rebrand_of")
    )
    return out


def recompute_title(
    t: dict[str, Any],
    templates: dict[str, Any] | None = None,
    product_types: list[dict[str, Any]] | None = None,
    *,
    unlock_all: bool = False,
) -> dict[str, Any]:
    """Reverse-calc DOS spine from ship date (Global / Betsoft)."""
    from spine import apply_ship_date, build_spine_from_product_type, find_product_type

    rel = parse_date(t.get("release_date"))
    if not rel:
        return t
    kind = (t.get("kind") or "title").lower()
    cx = normalize_complexity(t.get("complexity"))
    t["complexity"] = cx
    pt = find_product_type(
        product_types,
        t.get("product_type_id") or t.get("complexity"),
        kind=kind,
        complexity=cx,
    )
    t["product_type_id"] = pt.get("id") or cx
    phases = t.get("phases") or []
    if not phases:
        phases = build_spine_from_product_type(pt)
    if unlock_all:
        for p in phases:
            p["locked"] = False
    t["phases"] = apply_ship_date(
        phases,
        rel,
        kind=kind,
        complexity=cx,
        product_type=pt,
        respect_locked=not unlock_all,
        reason="recompute from ship date",
    )
    return t


def body_type_id(body: dict[str, Any]) -> str:
    return (body.get("product_type_id") or body.get("complexity") or "medium").strip()


def mint_title(
    body: dict[str, Any],
    templates: dict[str, Any] | None = None,
    product_types: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """New title: name + product model + optional ship. Theme/math are dossier, not mint requirements."""
    from spine import build_spine_dated, find_product_type

    pt = find_product_type(
        product_types,
        body.get("product_type_id") or body.get("complexity"),
        kind=body.get("kind"),
        complexity=body.get("complexity"),
    )
    kind = (pt.get("kind") or body.get("kind") or "title").strip().lower()
    if kind not in ("title", "rebrand"):
        kind = "title"
    cx = normalize_complexity(
        pt.get("id")
        if pt.get("id") in ("medium", "complex", "math_clone")
        else body.get("complexity")
    )
    if (pt.get("id") or "") in ("medium", "complex", "math_clone"):
        cx = pt["id"]
    release = (body.get("release_date") or "").strip()[:10]
    # quarter is a board bin derived from ship unless explicitly overridden
    q_in = (body.get("quarter") or "").strip()
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip() or code or "Untitled"
    t: dict[str, Any] = {
        "id": new_id("ttl"),
        "code": code,
        # code is the stable key; name can wait (falls back to code)
        "name": name,
        "subtitle": (body.get("subtitle") or "").strip(),
        "product_line_id": body.get("product_line_id") or "line-bsg",
        "product_type_id": pt.get("id") or "medium",
        "complexity": cx,
        "status": normalize_lifecycle(body.get("status") or "planning"),
        "kind": kind,
        "theme": (body.get("theme") or "").strip(),
        "math_model": (body.get("math_model") or "").strip(),
        "notes": (body.get("notes") or "").strip(),
        "release_date": release,
        "quarter": q_in,
        "twin_code": (body.get("twin_code") or "").strip(),
        "rebrand_of": (body.get("rebrand_of") or "").strip(),
        "nucleus_code": (body.get("nucleus_code") or "").strip(),
        "assignments": [],
        "phases": body.get("phases")
        if body.get("phases")
        else build_spine_dated(
            release or None, kind=kind, complexity=cx, product_type=pt
        ),
        "created": int(time.time()),
        "updated": int(time.time()),
    }
    if not t["quarter"] and t["release_date"]:
        rel = parse_date(t["release_date"])
        if rel:
            t["quarter"] = quarter_label(quarter_key(rel))
    return t


def make_rebrand_from(nucleus: dict[str, Any], body: dict[str, Any] | None = None) -> dict[str, Any]:
    """BSG logo-swap twin of an NG (or any) nucleus title — thin DOS rebrand spine."""
    body = body or {}
    code = (body.get("code") or f"BSG-RE-{(nucleus.get('code') or 'GAME')}").strip()
    name = (body.get("name") or f"{nucleus.get('name') or 'Game'} (BSG rebrand)").strip()
    t = mint_title(
        {
            "code": code,
            "name": name,
            "product_line_id": body.get("product_line_id") or "line-bsg",
            "kind": "rebrand",
            "product_type_id": body.get("product_type_id") or "rebrand",
            "complexity": "medium",
            "status": "planning",
            "theme": nucleus.get("theme") or "",
            "math_model": nucleus.get("math_model") or "",
            "quarter": nucleus.get("quarter") or "",
            "release_date": (body.get("release_date") or "").strip()[:10],
            "twin_code": nucleus.get("code") or "",
            "rebrand_of": nucleus.get("code") or "",
            "nucleus_code": nucleus.get("code") or "",
            "notes": f"Rebrand of {nucleus.get('code') or nucleus.get('name')}",
        },
        product_types=None,  # filled by caller when available
    )
    return t


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BOX_SYS), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(
                200, {"ok": True, "service": "great-road-mapper", "port": PORT}
            )
        if path == "/api/state":
            data = load_store()
            titles = [enrich_title(t) for t in data.get("titles") or []]
            qset = sorted(
                {t.get("quarter_key") or "unassigned" for t in titles},
                reverse=True,
            )
            return self._json(
                200,
                {
                    "ok": True,
                    "product_lines": data.get("product_lines") or [],
                    "roles": data.get("roles") or [],
                    "people": data.get("people") or [],
                    "template_keys": ["medium", "complex", "math_clone"],
                    "product_types": data.get("product_types") or [],
                    "quarters": [
                        {"key": k, "label": quarter_label(k)} for k in qset
                    ],
                    "pipeline_buckets": list(PIPELINE_BUCKETS),
                    "titles": titles,
                    "vocab": vocab_from_titles(data.get("titles") or []),
                    "spine": spine_definition(),
                    "spine_note": "DOS Castaway labels · empty until you set dates",
                    "updated": data.get("updated"),
                    "store_path": str(STORE),
                },
            )
        if path == "/api/vocab":
            data = load_store()
            return self._json(
                200, {"ok": True, "vocab": vocab_from_titles(data.get("titles") or [])}
            )
        if path == "/api/templates":
            data = load_store()
            tpls = data.get("templates") or {}
            slim = {k: tpls[k] for k in ("medium", "complex", "math_clone") if k in tpls}
            return self._json(200, {"ok": True, "templates": slim})
        if path == "/api/product-types":
            data = load_store()
            return self._json(
                200, {"ok": True, "product_types": data.get("product_types") or []}
            )
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body = self._read_json()
        data = load_store()
        templates = data.get("templates") or default_templates()
        product_types = data.get("product_types") or []

        if path == "/api/vocab/cleanup":
            n = cleanup_all_labels(data.get("titles") or [])
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "changed_events": n,
                    "vocab": vocab_from_titles(data.get("titles") or []),
                    "message": f"cleaned {n} event labels (shared names)",
                },
            )

        if path == "/api/vocab/align-spine":
            fill = body.get("fill_missing", True)
            if isinstance(fill, str):
                fill = fill.lower() not in ("0", "false", "no")
            # clean first so aliases hit spine
            cleanup_all_labels(data.get("titles") or [])
            stats = align_all_to_spine(
                data.get("titles") or [], fill_missing=bool(fill)
            )
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    **stats,
                    "vocab": vocab_from_titles(data.get("titles") or []),
                    "spine": spine_definition(),
                    "message": (
                        f"aligned {stats['titles']} titles to house spine "
                        f"({stats['events']} events, {stats['off_spine']} off-spine leftovers)"
                    ),
                },
            )

        if path == "/api/vocab/rename":
            old = (body.get("from") or body.get("old") or "").strip()
            new = (body.get("to") or body.get("new") or "").strip()
            if not old or not new:
                return self._json(400, {"ok": False, "error": "from and to required"})
            if old == new:
                return self._json(200, {"ok": True, "changed": 0, "message": "no change"})
            n = rename_label_everywhere(data.get("titles") or [], old, new)
            # optional force role
            if body.get("role") in ("phase", "gate"):
                for t in data.get("titles") or []:
                    for p in t.get("phases") or []:
                        if (p.get("name") or "") == new:
                            p["role"] = body["role"]
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "changed": n,
                    "vocab": vocab_from_titles(data.get("titles") or []),
                    "message": f"renamed “{old}” → “{new}” on {n} events (all titles)",
                },
            )

        if path == "/api/vocab/set-role":
            name = (body.get("name") or "").strip()
            role = (body.get("role") or "").strip().lower()
            if not name or role not in ("phase", "gate"):
                return self._json(
                    400, {"ok": False, "error": "name + role phase|gate required"}
                )
            target = normalize_event_name(name)
            n = 0
            for t in data.get("titles") or []:
                for p in t.get("phases") or []:
                    if normalize_event_name(p.get("name")) == target or (
                        p.get("name") or ""
                    ) == name:
                        p["name"] = name  # keep the vocab spelling they set role on
                        p["role"] = role
                        n += 1
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "changed": n,
                    "vocab": vocab_from_titles(data.get("titles") or []),
                    "message": f"set “{name}” → {role} on {n} events (all titles)",
                },
            )

        if path == "/api/product-types":
            # Replace full list or upsert one type
            if isinstance(body.get("product_types"), list):
                data["product_types"] = body["product_types"]
                save_store(data)
                return self._json(
                    200,
                    {
                        "ok": True,
                        "product_types": data["product_types"],
                        "message": "product types saved",
                    },
                )
            pt = body.get("product_type") or body
            pid = (pt.get("id") or "").strip().lower().replace(" ", "_")
            # previous_id = rename-in-place (label can say MEDIUM; code can be primary / mdl-001)
            prev = (
                (body.get("previous_id") or pt.get("previous_id") or "").strip().lower()
            )
            if prev:
                prev = prev.replace(" ", "_")
            if not pid:
                return self._json(400, {"ok": False, "error": "id required"})
            # allow short codes: letters, digits, _ -
            import re

            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", pid):
                return self._json(
                    400,
                    {
                        "ok": False,
                        "error": "id must be a short code (a-z, 0-9, _ -)",
                    },
                )
            pt["id"] = pid
            pt["label"] = (pt.get("label") or pid).strip()
            pt["kind"] = (pt.get("kind") or "title").strip().lower()
            if pt["kind"] not in ("title", "rebrand"):
                pt["kind"] = "title"
            model = (pt.get("model") or "template").strip().lower()
            if model not in ("template", "variation"):
                model = "template"
            pt["model"] = model
            pts = list(data.get("product_types") or [])
            if model == "variation":
                tid = (pt.get("template_id") or "").strip().lower().replace(" ", "_")
                if not tid:
                    return self._json(
                        400, {"ok": False, "error": "variation needs template_id"}
                    )
                if tid == pid:
                    return self._json(
                        400, {"ok": False, "error": "variation cannot parent itself"}
                    )
                parent = next((x for x in pts if (x.get("id") or "") == tid), None)
                if not parent:
                    return self._json(400, {"ok": False, "error": "template not found"})
                if (parent.get("model") or "template") == "variation":
                    return self._json(
                        400, {"ok": False, "error": "template_id must be a template"}
                    )
                pt["template_id"] = tid
                pt["kind"] = parent.get("kind") or pt["kind"]
                pt["release_label"] = parent.get("release_label") or pt.get(
                    "release_label"
                )
            else:
                pt.pop("template_id", None)
            pt["struts"] = list(pt.get("struts") or [])
            # gate rules only on templates (variations inherit via materialize)
            if model == "variation":
                pt.pop("gates", None)
            else:
                raw_gates = pt.get("gates")
                if not isinstance(raw_gates, list):
                    raw_gates = []
                clean_gates = []
                for g in raw_gates:
                    if not isinstance(g, dict):
                        continue
                    gname = (g.get("name") or "").strip()
                    if not gname:
                        continue
                    anc = (g.get("anchor") or "phase").strip().lower()
                    if anc not in ("phase", "release", "workstream"):
                        anc = "phase"
                    unit = (g.get("offset_unit") or "weeks").strip().lower()
                    if unit not in ("weeks", "days"):
                        unit = "weeks"
                    # prefer explicit offset_days; else convert from weeks / raw offset
                    od = g.get("offset_days")
                    try:
                        if od is not None and od != "":
                            days_i = max(0, int(round(float(od))))
                        elif unit == "days":
                            days_i = max(
                                0, int(round(float(g.get("offset") or g.get("offset_weeks") or 0)))
                            )
                        else:
                            days_i = max(
                                0,
                                int(
                                    round(
                                        float(g.get("offset_weeks") or g.get("offset") or 0)
                                        * 7
                                    )
                                ),
                            )
                    except (TypeError, ValueError):
                        days_i = 0
                    clean_gates.append(
                        {
                            "id": (g.get("id") or "").strip()
                            or f"gt-{__import__('secrets').token_hex(4)}",
                            "name": gname,
                            "role": "gate",
                            "kind": "point",
                            "anchor": anc,
                            "phase_name": (g.get("phase_name") or "").strip(),
                            "workstream_name": (g.get("workstream_name") or "").strip(),
                            "relation": (g.get("relation") or "at_end").strip(),
                            "offset_unit": unit,
                            "offset_days": days_i,
                            "offset_weeks": round(days_i / 7, 4) if days_i else 0,
                        }
                    )
                pt["gates"] = clean_gates
            pt.pop("previous_id", None)

            renamed = 0
            if prev and prev != pid:
                # rename code: old row → new code; cascade refs
                if any((x.get("id") or "") == pid for x in pts):
                    return self._json(
                        400, {"ok": False, "error": f"code “{pid}” already in use"}
                    )
                old_row = next((x for x in pts if (x.get("id") or "") == prev), None)
                if not old_row:
                    return self._json(
                        404, {"ok": False, "error": f"previous code “{prev}” not found"}
                    )
                pts = [p for p in pts if (p.get("id") or "") != prev]
                pts.append(pt)
                for p in pts:
                    if (p.get("template_id") or "") == prev:
                        p["template_id"] = pid
                        renamed += 1
                for t in data.get("titles") or []:
                    if (t.get("product_type_id") or "") == prev:
                        t["product_type_id"] = pid
                        renamed += 1
                    if (t.get("complexity") or "") == prev:
                        t["complexity"] = pid
            else:
                found = False
                for i, existing in enumerate(pts):
                    if (existing.get("id") or "") == pid:
                        pts[i] = pt
                        found = True
                        break
                if not found:
                    pts.append(pt)

            data["product_types"] = pts
            data["product_types_template_v1"] = True
            save_store(data)
            msg = "saved " + pid
            if prev and prev != pid:
                msg = f"renamed {prev} → {pid}" + (
                    f" · updated {renamed} refs" if renamed else ""
                )
            return self._json(
                200,
                {
                    "ok": True,
                    "product_type": pt,
                    "product_types": pts,
                    "message": msg,
                    "renamed_from": prev if prev and prev != pid else None,
                },
            )

        if path == "/api/product-types/delete":
            pid = (body.get("id") or "").strip()
            if not pid:
                return self._json(400, {"ok": False, "error": "id required"})
            before = list(data.get("product_types") or [])
            if not any((p.get("id") or "") == pid for p in before):
                return self._json(404, {"ok": False, "error": "type not found"})
            kids = [
                p
                for p in before
                if (p.get("template_id") or "") == pid
                and (
                    (p.get("model") or "") == "variation" or bool(p.get("template_id"))
                )
            ]
            cascade = bool(body.get("cascade"))
            # Default: cascade template delete removes its variations too
            # (operator asked to delete templates without getting stuck on kids).
            if kids and not cascade and body.get("cascade") is False:
                labels = ", ".join(
                    (k.get("label") or k.get("id") or "?") for k in kids
                )
                return self._json(
                    400,
                    {
                        "ok": False,
                        "error": f"has variations: {labels}",
                        "variations": [k.get("id") for k in kids],
                    },
                )
            drop_ids = {pid}
            if kids:
                drop_ids |= {(k.get("id") or "") for k in kids}
            data["product_types"] = [
                p for p in before if (p.get("id") or "") not in drop_ids
            ]
            # allow empty list — operator will rebuild sheets; do not re-seed defaults
            save_store(data)
            msg = f"deleted {pid}"
            if kids:
                msg += f" + {len(kids)} variation(s)"
            return self._json(
                200,
                {
                    "ok": True,
                    "product_types": data["product_types"],
                    "message": msg,
                    "deleted_ids": list(drop_ids),
                },
            )

        if path == "/api/titles":
            if not (body.get("code") or "").strip():
                return self._json(400, {"ok": False, "error": "code required"})
            t = mint_title(body, templates, product_types)
            data.setdefault("titles", []).append(t)
            save_store(data)
            return self._json(200, {"ok": True, "title": enrich_title(t)})

        if path == "/api/titles/rebrand":
            # body: { from_id or from_code, code?, name?, release_date? }
            src_id = (body.get("from_id") or "").strip()
            src_code = (body.get("from_code") or "").strip().upper()
            nucleus = None
            for x in data.get("titles") or []:
                if src_id and x.get("id") == src_id:
                    nucleus = x
                    break
                if src_code and (x.get("code") or "").upper() == src_code:
                    nucleus = x
                    break
            if not nucleus:
                return self._json(404, {"ok": False, "error": "nucleus title not found"})
            t = make_rebrand_from(nucleus, body)
            # re-mint with store product types
            from spine import find_product_type, build_spine_dated

            pt = find_product_type(product_types, "rebrand", kind="rebrand")
            t["product_type_id"] = pt.get("id") or "rebrand"
            t["kind"] = "rebrand"
            if t.get("release_date"):
                t["phases"] = build_spine_dated(
                    t["release_date"], kind="rebrand", product_type=pt
                )
            # mutual twin
            nucleus["twin_code"] = t.get("code") or ""
            nucleus["updated"] = int(time.time())
            data.setdefault("titles", []).append(t)
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "title": enrich_title(t),
                    "nucleus": enrich_title(nucleus),
                    "message": f"rebrand {t.get('code')} linked to {nucleus.get('code')}",
                },
            )

        if path.startswith("/api/titles/") and path.endswith("/event"):
            # POST /api/titles/:id/event  { id?, name, role, start, end, reason }
            tid = path[len("/api/titles/") : -len("/event")]
            t = next((x for x in data.get("titles") or [] if x.get("id") == tid), None)
            if not t:
                return self._json(404, {"ok": False, "error": "title not found"})
            from spine import record_edit

            eid = (body.get("id") or "").strip()
            reason = (body.get("reason") or "").strip()
            phases = list(t.get("phases") or [])
            target = next((p for p in phases if p.get("id") == eid), None)
            if body.get("delete"):
                if not target:
                    return self._json(404, {"ok": False, "error": "event not found"})
                if not reason:
                    return self._json(
                        400, {"ok": False, "error": "reason required to remove a gate/phase"}
                    )
                before = dict(target)
                t["phases"] = [p for p in phases if p.get("id") != eid]
                # keep a ghost log on title notes trail
                t.setdefault("event_log", []).append(
                    {
                        "at": int(time.time()),
                        "action": "delete",
                        "reason": reason,
                        "event": before.get("name"),
                        "id": eid,
                    }
                )
                t["updated"] = int(time.time())
                save_store(data)
                return self._json(200, {"ok": True, "title": enrich_title(t)})

            name = (body.get("name") or (target or {}).get("name") or "Event").strip()
            role = (body.get("role") or (target or {}).get("role") or "gate").strip()
            start = (body.get("start") or "").strip()[:10] or None
            end = (body.get("end") or "").strip()[:10] or start
            kind = "point" if role == "gate" and start == end else "range"
            ws_id = (body.get("workstream_id") or "").strip()

            # --- workstream line (↳) under a parent phase ---
            if ws_id:
                if not target:
                    return self._json(404, {"ok": False, "error": "parent phase not found"})
                streams = list(target.get("workstreams") or [])
                ws = next((w for w in streams if (w.get("id") or "") == ws_id), None)
                if not ws:
                    return self._json(404, {"ok": False, "error": "workstream not found"})
                before = {
                    "name": ws.get("name"),
                    "start": ws.get("start"),
                    "end": ws.get("end"),
                    "role": "workstream",
                }
                after = {
                    "name": ws.get("name"),
                    "start": start,
                    "end": end or start,
                    "role": "workstream",
                }
                if not reason:
                    return self._json(
                        400,
                        {
                            "ok": False,
                            "error": "reason required when changing a workstream (edit trail)",
                        },
                    )
                ws["start"] = start
                ws["end"] = end or start
                # manual dates own the line — no longer a pure template fill
                ws["fill_parent"] = False
                record_edit(ws, reason=reason, before=before, after=after)
                ws["notes"] = reason
                t["updated"] = int(time.time())
                save_store(data)
                return self._json(200, {"ok": True, "title": enrich_title(t)})

            if target:
                before = {
                    "name": target.get("name"),
                    "start": target.get("start"),
                    "end": target.get("end"),
                    "role": target.get("role"),
                }
                if not reason:
                    return self._json(
                        400,
                        {
                            "ok": False,
                            "error": "reason required when changing a phase/gate (edit trail)",
                        },
                    )
                # Release is immovable. Make room only by going earlier (default on).
                cascade_on = body.get("cascade_earlier")
                if cascade_on is None:
                    cascade_on = True
                cascade_on = bool(cascade_on)
                # Workstreams / pure adds skip; gates may cascade if start moves earlier
                plan = {
                    "pivot_start": start,
                    "pivot_end": end,
                    "cascade_days": 0,
                    "note": "",
                }
                if cascade_on and not ws_id:
                    plan = plan_backward_make_room(
                        before.get("start"),
                        before.get("end"),
                        start,
                        end,
                    )
                    start = plan.get("pivot_start") or start
                    end = plan.get("pivot_end") or end or start
                    kind = "point" if role == "gate" and start == end else "range"

                after = {"name": name, "start": start, "end": end, "role": role}
                target["name"] = name
                target["role"] = role
                target["kind"] = kind
                target["start"] = start
                target["end"] = end
                target["placeholder"] = not bool(start or end)
                record_edit(target, reason=reason, before=before, after=after)
                target["notes"] = reason

                shifted = 0
                if cascade_on and int(plan.get("cascade_days") or 0) < 0:
                    shifted = cascade_earlier_phases(
                        phases,
                        eid,
                        int(plan["cascade_days"]),
                        reason=reason,
                        pivot_sort=int(target.get("sort") or 0),
                    )
                    t["phases"] = phases
                t.setdefault("event_log", []).append(
                    {
                        "at": int(time.time()),
                        "action": "edit",
                        "reason": reason,
                        "event": name,
                        "id": eid,
                        "cascade_days": int(plan.get("cascade_days") or 0),
                        "cascade_shifted": shifted,
                        "plan_note": plan.get("note") or "",
                    }
                )
                t["updated"] = int(time.time())
                save_store(data)
                msg = plan.get("note") or "dates saved"
                if shifted:
                    msg = f"{msg} · {shifted} earlier line(s) moved"
                return self._json(
                    200,
                    {
                        "ok": True,
                        "title": enrich_title(t),
                        "message": msg,
                        "cascade_days": int(plan.get("cascade_days") or 0),
                        "cascade_shifted": shifted,
                    },
                )
            else:
                from spine import empty_event

                ev = empty_event(name, role, kind, len(phases))
                ev["start"] = start
                ev["end"] = end
                ev["placeholder"] = not bool(start or end)
                if reason:
                    record_edit(
                        ev,
                        reason=reason,
                        before={"name": None, "start": None, "end": None, "role": None},
                        after={"name": name, "start": start, "end": end, "role": role},
                    )
                    ev["notes"] = reason
                phases.append(ev)
                t["phases"] = phases
            t["updated"] = int(time.time())
            save_store(data)
            return self._json(200, {"ok": True, "title": enrich_title(t)})

        if path == "/api/seed-q1-2027":
            existing_codes = {
                (t.get("code") or "").upper() for t in data.get("titles") or []
            }
            added = []
            for row in Q1_2027_TITLES:
                code = (row.get("code") or "").upper()
                if code in existing_codes:
                    continue
                t = mint_title({**row, "recompute": True}, templates, product_types)
                data.setdefault("titles", []).append(t)
                existing_codes.add(code)
                added.append(t["code"])
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "added": added,
                    "count": len(added),
                    "message": f"seeded {len(added)} Q1 2027 titles (reverse-calc from release)",
                },
            )

        if path.startswith("/api/titles/") and path.endswith("/recompute"):
            tid = path[len("/api/titles/") : -len("/recompute")]
            t = next((x for x in data.get("titles") or [] if x.get("id") == tid), None)
            if not t:
                return self._json(404, {"ok": False, "error": "title not found"})
            if body.get("release_date"):
                t["release_date"] = str(body["release_date"]).strip()[:10]
            if body.get("complexity"):
                t["complexity"] = normalize_complexity(body["complexity"])
            if body.get("product_type_id"):
                t["product_type_id"] = str(body["product_type_id"]).strip()
            unlock = bool(body.get("unlock_all"))
            recompute_title(
                t, templates, product_types=product_types, unlock_all=unlock
            )
            t["updated"] = int(time.time())
            save_store(data)
            return self._json(
                200,
                {
                    "ok": True,
                    "title": enrich_title(t),
                    "message": "dates reverse-filled from ship date",
                },
            )

        if path.startswith("/api/titles/") and path.count("/") == 3:
            tid = path.split("/")[-1]
            t = next((x for x in data.get("titles") or [] if x.get("id") == tid), None)
            if not t:
                return self._json(404, {"ok": False, "error": "title not found"})
            for key in (
                "code",
                "name",
                "subtitle",
                "product_line_id",
                "complexity",
                "product_type_id",
                "status",
                "kind",
                "theme",
                "math_model",
                "notes",
                "release_date",
                "quarter",
                "bsg_twin",
                "bsg_release_date",
                "twin_code",
                "rebrand_of",
                "nucleus_code",
            ):
                if key in body:
                    val = body[key]
                    if key in ("release_date", "bsg_release_date"):
                        t[key] = str(val or "").strip()[:10]
                    elif key == "complexity":
                        t[key] = normalize_complexity(val)
                    elif key == "product_type_id":
                        t[key] = str(val or "").strip()
                    elif key == "status":
                        t[key] = normalize_lifecycle(val)
                    else:
                        t[key] = val if not isinstance(val, str) else val.strip()
            if "assignments" in body and isinstance(body["assignments"], list):
                t["assignments"] = body["assignments"]
            if "phases" in body and isinstance(body["phases"], list):
                t["phases"] = body["phases"]
            if body.get("recompute"):
                recompute_title(
                    t,
                    templates,
                    product_types=product_types,
                    unlock_all=bool(body.get("unlock_all")),
                )
            # Mutual twin: if twin_code points at another title, link back
            twin_code = (t.get("twin_code") or "").strip()
            if twin_code:
                other = next(
                    (
                        x
                        for x in data.get("titles") or []
                        if (x.get("code") or "").upper() == twin_code.upper()
                        and x.get("id") != t.get("id")
                    ),
                    None,
                )
                if other:
                    other["twin_code"] = t.get("code") or ""
                    # if this is rebrand, mark other as nucleus link
                    if (t.get("kind") or "") == "rebrand":
                        t["rebrand_of"] = other.get("code") or ""
                        t["nucleus_code"] = other.get("code") or ""
                        other.setdefault("kind", other.get("kind") or "title")
                    other["updated"] = int(time.time())
            t["updated"] = int(time.time())
            save_store(data)
            return self._json(200, {"ok": True, "title": enrich_title(t)})

        if path == "/api/people":
            person = {
                "id": new_id("ppl"),
                "name": (body.get("name") or "Unnamed").strip(),
                "role": (body.get("role") or "").strip(),
                "active": True,
            }
            data.setdefault("people", []).append(person)
            save_store(data)
            return self._json(200, {"ok": True, "person": person})

        return self._json(404, {"ok": False, "error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/titles/"):
            tid = path.split("/")[-1]
            data = load_store()
            before = len(data.get("titles") or [])
            data["titles"] = [
                t for t in data.get("titles") or [] if t.get("id") != tid
            ]
            if len(data["titles"]) == before:
                return self._json(404, {"ok": False, "error": "title not found"})
            save_store(data)
            return self._json(200, {"ok": True})
        return self._json(404, {"ok": False, "error": "not found"})


def main() -> None:
    ensure_dirs()
    load_store()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Great Road Mapper · http://{HOST}:{PORT}/ · store {STORE}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstop")


if __name__ == "__main__":
    main()
