"""DOS-aligned schedule spine — clean struts for a single game.

Labels match the Castaway / DOS Roadmaps ticket language Hands used
when materializing Confluence into the office.

Ship date (Global Release / Betsoft Release) reverse-fills phase dates
from product-type durations (template bins; variations = week numbers only).

Primary production variations share one template's ordered bins.
Gates = point deadlines from template rules (phase- or release-relative).
"""

from __future__ import annotations

import secrets
import time
from datetime import date, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Phase-only product pipeline (v2)
# Gates (deliveries / checkpoints) are NOT mixed into the phase stack —
# they need a separate model later (end-of-phase pins, one-off deadlines).
# Templates = ordered phases with durations + one hard release date.
# ---------------------------------------------------------------------------

# (name, role, kind) — phases only for house defaults
# Overlapping team work = workstreams under a parent (not two stacked phases)
SPINE_FULL: list[tuple[str, str, str]] = [
    ("Design Phase", "phase", "range"),
    ("Static Art Phase", "phase", "range"),
    ("FX Phase", "phase", "range"),
    ("Dev Phase", "phase", "range"),
    ("QA: Localization Phase", "phase", "range"),
    ("QA: LQA / RQA", "phase", "range"),  # parent window; LQA∥RQA as workstreams
    ("Active Rollout", "phase", "range"),
]

# NG → BSG thin phase set (release is Betsoft, not mixed into phase list)
SPINE_REBRAND: list[tuple[str, str, str]] = [
    ("QA: LQA / RQA", "phase", "range"),
    ("Active Rollout", "phase", "range"),
]

SPINE_CLONE: list[tuple[str, str, str]] = list(SPINE_FULL)

# Legacy full list (incl. gates) kept for vocab / old titles only
SPINE_FULL_WITH_GATES: list[tuple[str, str, str]] = [
    ("Design Phase", "phase", "range"),
    ("Static Art Phase", "phase", "range"),
    ("FX Phase", "phase", "range"),
    ("Deliver Math to Devs", "gate", "point"),
    ("Deliver Assets to Devs", "gate", "point"),
    ("Dev Phase", "phase", "range"),
    ("Deliver Audio to Devs", "gate", "point"),
    ("QA: Localization Phase", "phase", "range"),
    ("QA: LQA Phase", "phase", "range"),
    ("QA: RQA Localization Phase", "phase", "range"),
    ("Active Rollout", "phase", "range"),
    ("Exclusivity / Test Live", "gate", "point"),
    ("Global Release", "gate", "point"),
]


def _week(n: float) -> int:
    return int(round(n * 7))


# Days BEFORE ship date — used only to seed phase *durations* (start−end).
# Global Release (or Betsoft Release) = day 0.
_OFFSETS_FULL: dict[str, dict[str, Any]] = {
    "Design Phase": {"start": _week(33), "end": _week(29)},
    "Static Art Phase": {"start": _week(29), "end": _week(25)},
    "FX Phase": {"start": _week(25), "end": _week(21)},
    "Dev Phase": {"start": _week(21), "end": _week(9)},
    "QA: Localization Phase": {"start": _week(6), "end": _week(4)},
    "QA: LQA / RQA": {"start": _week(4), "end": _week(2)},  # one window, two streams
    "Active Rollout": {"start": _week(2), "end": 0},
    "Global Release": {"point": 0},
}

# Complex: longer Dev (14w)
_OFFSETS_COMPLEX: dict[str, dict[str, Any]] = {
    "Design Phase": {"start": _week(35), "end": _week(31)},
    "Static Art Phase": {"start": _week(31), "end": _week(27)},
    "FX Phase": {"start": _week(27), "end": _week(23)},
    "Dev Phase": {"start": _week(23), "end": _week(9)},
    "QA: Localization Phase": {"start": _week(6), "end": _week(4)},
    "QA: LQA / RQA": {"start": _week(4), "end": _week(2)},
    "Active Rollout": {"start": _week(2), "end": 0},
    "Global Release": {"point": 0},
}

# Math clone: shorter pre-dev
_OFFSETS_CLONE: dict[str, dict[str, Any]] = {
    "Design Phase": {"start": _week(30), "end": _week(26)},
    "Static Art Phase": {"start": _week(26), "end": _week(22)},
    "FX Phase": {"start": _week(22), "end": _week(18)},
    "Dev Phase": {"start": _week(18), "end": _week(8)},
    "QA: Localization Phase": {"start": _week(6), "end": _week(4)},
    "QA: LQA / RQA": {"start": _week(4), "end": _week(2)},
    "Active Rollout": {"start": _week(2), "end": 0},
    "Global Release": {"point": 0},
}

# Rebrand: thin tail before Betsoft Release (day 0)
_OFFSETS_REBRAND: dict[str, dict[str, Any]] = {
    "QA: LQA / RQA": {"start": _week(4), "end": _week(2)},
    "Active Rollout": {"start": _week(1), "end": 0},
    "Betsoft Release": {"point": 0},
}

# Default workstreams under parent phases (fill_parent = overlap full window)
_DEFAULT_WORKSTREAMS: dict[str, list[dict[str, Any]]] = {
    "Design Phase": [
        {"name": "Game Design", "kind": "workstream", "fill_parent": True},
        {"name": "Math", "kind": "workstream", "fill_parent": True},
        {
            "name": "GDD for AI previs",
            "kind": "workstream",
            "fill_parent": False,
            "offset_weeks_from_start": 0,
            "duration_weeks": 1,
        },
    ],
    "QA: LQA / RQA": [
        {"name": "LQA", "kind": "workstream", "fill_parent": True},
        {"name": "RQA", "kind": "workstream", "fill_parent": True},
    ],
}


def _eid() -> str:
    return f"ev-{secrets.token_hex(4)}"


def _fmt(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except ValueError:
        return None


def empty_event(name: str, role: str, kind: str, sort: int) -> dict[str, Any]:
    return {
        "id": _eid(),
        "name": name,
        "role": role,
        "kind": kind,
        "start": None,
        "end": None,
        "locked": False,
        "notes": "",
        "sort": sort,
        "spine": True,
        "placeholder": True,
        "edits": [],
        "workstreams": [],
    }


def empty_workstream(
    name: str,
    *,
    fill_parent: bool = True,
    offset_weeks_from_start: float = 0,
    duration_weeks: float | None = None,
    sort: int = 0,
) -> dict[str, Any]:
    return {
        "id": f"ws-{secrets.token_hex(4)}",
        "name": name,
        "kind": "workstream",
        "fill_parent": bool(fill_parent),
        # portion of parent: start = parent_start + offset weeks; run duration_weeks
        "offset_weeks_from_start": float(offset_weeks_from_start or 0),
        "duration_weeks": duration_weeks,  # None if fill_parent
        "start": None,
        "end": None,
        "sort": sort,
        "notes": "",
    }


def _offset_table(kind: str, complexity: str) -> dict[str, dict[str, Any]]:
    kind = (kind or "title").lower()
    cx = (complexity or "medium").lower()
    if kind == "rebrand":
        return _OFFSETS_REBRAND
    if cx in ("math_clone", "clone", "simple"):
        return _OFFSETS_CLONE
    if cx == "complex":
        return _OFFSETS_COMPLEX
    return _OFFSETS_FULL


def _phase_struts_from_table(
    rows: list[tuple[str, str, str]], table: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Phases only: duration + order. Gates omitted (separate system later)."""
    struts: list[dict[str, Any]] = []
    for n, r, k in rows:
        if r == "gate" or k == "point":
            continue
        off = table.get(n) or {}
        if "point" in off:
            continue
        start = int(off.get("start") or 0)
        end = int(off.get("end") or 0)
        dur = max(0, start - end)
        # sensible floor for short/weird residuals (e.g. Active Rollout 1d → 1w)
        if dur < 7 and n == "Active Rollout":
            dur = 7
        item: dict[str, Any] = {
            "name": n,
            "role": "phase",
            "kind": "range",
            "duration_days": dur,
            "duration_weeks": round(dur / 7, 4),
            "workstreams": [],
        }
        for j, ws in enumerate(_DEFAULT_WORKSTREAMS.get(n) or []):
            item["workstreams"].append(
                {
                    "name": ws.get("name") or f"Stream {j + 1}",
                    "kind": "workstream",
                    "fill_parent": ws.get("fill_parent", True),
                    "offset_weeks_from_start": ws.get("offset_weeks_from_start", 0),
                    "duration_weeks": ws.get("duration_weeks"),
                }
            )
        struts.append(item)
    return struts


def default_product_types() -> list[dict[str, Any]]:
    """
    Templates own structure (bins, workstreams, later gates).
    Variations clone a template and only override week numbers / stream windows.
    """
    medium_struts = _phase_struts_from_table(SPINE_FULL, _OFFSETS_FULL)
    return [
        {
            "id": "primary",
            "label": "PRIMARY",
            "model": "template",
            "kind": "title",
            "release_label": "Global Release",
            "description": "Primary production template — bins, workstreams, gates; variations tweak weeks",
            "struts": medium_struts,
            "gates": [],
        },
        {
            "id": "medium",
            "label": "MEDIUM",
            "model": "variation",
            "template_id": "primary",
            "kind": "title",
            "release_label": "Global Release",
            "description": "Standard week lengths · same bins as PRIMARY",
            "struts": list(medium_struts),  # same numbers as template seed
        },
        {
            "id": "complex",
            "label": "COMPLEX",
            "model": "variation",
            "template_id": "primary",
            "kind": "title",
            "release_label": "Global Release",
            "description": "Longer Dev · same bins as PRIMARY (numbers only)",
            "struts": _phase_struts_from_table(SPINE_FULL, _OFFSETS_COMPLEX),
        },
        {
            "id": "math_clone",
            "label": "MATH CLONE",
            "model": "variation",
            "template_id": "primary",
            "kind": "title",
            "release_label": "Global Release",
            "description": "Shorter pre-dev · same bins as PRIMARY (numbers only)",
            "struts": _phase_struts_from_table(SPINE_CLONE, _OFFSETS_CLONE),
        },
        {
            "id": "rebrand",
            "label": "REBRAND",
            "model": "template",
            "kind": "rebrand",
            "release_label": "Betsoft Release",
            "description": "Thin pipeline template (NG→BSG) — separate structure",
            "struts": _phase_struts_from_table(SPINE_REBRAND, _OFFSETS_REBRAND),
            "gates": [],
        },
    ]


def _raw_product_type(
    product_types: list[dict[str, Any]] | None, type_id: str | None
) -> dict[str, Any] | None:
    tid = (type_id or "").strip().lower()
    if not tid:
        return None
    for p in product_types or []:
        if (p.get("id") or "").lower() == tid:
            return p
    return None


def is_variation(pt: dict[str, Any] | None) -> bool:
    if not pt:
        return False
    if (pt.get("model") or "").lower() == "variation":
        return True
    return bool(pt.get("template_id"))


def is_template(pt: dict[str, Any] | None) -> bool:
    if not pt:
        return False
    if is_variation(pt):
        return False
    return (pt.get("model") or "template").lower() in ("template", "")


def _ws_numbers_from(var_ws: dict[str, Any] | None, base_ws: dict[str, Any]) -> dict[str, Any]:
    """Structure from template stream; only window numbers may come from variation."""
    out = {
        "name": base_ws.get("name") or "Stream",
        "kind": "workstream",
        "fill_parent": bool(base_ws.get("fill_parent", True)),
        "offset_weeks_from_start": base_ws.get("offset_weeks_from_start", 0),
        "duration_weeks": base_ws.get("duration_weeks"),
    }
    if not var_ws:
        return out
    # numbers only — fill_parent / name stay on the template
    try:
        if var_ws.get("offset_weeks_from_start") is not None:
            out["offset_weeks_from_start"] = float(var_ws.get("offset_weeks_from_start") or 0)
    except (TypeError, ValueError):
        pass
    raw_dur = var_ws.get("duration_weeks")
    if raw_dur is not None and raw_dur != "":
        try:
            out["duration_weeks"] = float(raw_dur)
        except (TypeError, ValueError):
            pass
    # if template is full-phase, variation cannot invent a portion via numbers alone
    # unless template is already portion (fill_parent false)
    if out["fill_parent"]:
        out["offset_weeks_from_start"] = 0
        out["duration_weeks"] = None
    return out


def materialize_product_type(
    product_types: list[dict[str, Any]] | None, pt: dict[str, Any]
) -> dict[str, Any]:
    """
    Variation → live template structure + this row's week numbers.
    Template → as stored.
    """
    if not is_variation(pt):
        out = dict(pt)
        out.setdefault("model", "template")
        return out

    pts = product_types or []
    base = _raw_product_type(pts, pt.get("template_id"))
    if not base:
        # orphan variation — use its own struts, still mark variation
        out = dict(pt)
        out["model"] = "variation"
        return out

    var_struts = [
        s
        for s in (pt.get("struts") or [])
        if (s.get("role") or "phase") != "gate" and (s.get("kind") or "") != "point"
    ]
    by_name = {
        (s.get("name") or "").strip(): s for s in var_struts if (s.get("name") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    for i, s in enumerate(base.get("struts") or []):
        if (s.get("role") or "phase") == "gate" or (s.get("kind") or "") == "point":
            continue
        name = (s.get("name") or "").strip()
        vs = by_name.get(name)
        if vs is None and i < len(var_struts):
            vs = var_struts[i]
        item: dict[str, Any] = {
            "name": name,
            "role": "phase",
            "kind": "range",
            "workstreams": [],
        }
        # duration numbers from variation when present
        if vs is not None and (
            vs.get("duration_weeks") is not None or vs.get("duration_days") is not None
        ):
            if vs.get("duration_weeks") is not None and vs.get("duration_weeks") != "":
                try:
                    w = float(vs["duration_weeks"])
                    item["duration_weeks"] = w
                    item["duration_days"] = int(round(w * 7))
                except (TypeError, ValueError):
                    item["duration_weeks"] = s.get("duration_weeks")
                    item["duration_days"] = s.get("duration_days")
            elif vs.get("duration_days") is not None:
                try:
                    d = int(vs["duration_days"])
                    item["duration_days"] = d
                    item["duration_weeks"] = round(d / 7, 4)
                except (TypeError, ValueError):
                    item["duration_weeks"] = s.get("duration_weeks")
                    item["duration_days"] = s.get("duration_days")
            else:
                item["duration_weeks"] = s.get("duration_weeks")
                item["duration_days"] = s.get("duration_days")
        else:
            item["duration_weeks"] = s.get("duration_weeks")
            item["duration_days"] = s.get("duration_days")

        base_ws = list(s.get("workstreams") or [])
        var_ws_list = list((vs or {}).get("workstreams") or [])
        var_ws_by_name = {
            (w.get("name") or "").strip(): w
            for w in var_ws_list
            if (w.get("name") or "").strip()
        }
        for j, bw in enumerate(base_ws):
            vw = var_ws_by_name.get((bw.get("name") or "").strip())
            if vw is None and j < len(var_ws_list):
                vw = var_ws_list[j]
            item["workstreams"].append(_ws_numbers_from(vw, bw))
        merged.append(item)

    out = {
        "id": pt.get("id"),
        "label": pt.get("label") or pt.get("id"),
        "model": "variation",
        "template_id": base.get("id") or pt.get("template_id"),
        "kind": base.get("kind") or pt.get("kind") or "title",
        # release label, gates, bins come from template (structure)
        "release_label": base.get("release_label") or pt.get("release_label"),
        "description": pt.get("description") or base.get("description") or "",
        "struts": merged,
        "gates": list(base.get("gates") or []),
    }
    return out


def find_product_type(
    product_types: list[dict[str, Any]] | None,
    type_id: str | None,
    *,
    kind: str | None = None,
    complexity: str | None = None,
) -> dict[str, Any]:
    """Resolve a product type by id, or legacy kind/complexity. Variations are materialized."""
    pts = product_types or default_product_types()
    tid = (type_id or "").strip().lower()
    raw: dict[str, Any] | None = None
    if tid:
        raw = _raw_product_type(pts, tid)
    if raw is None:
        # legacy
        k = (kind or "title").lower()
        if k == "rebrand":
            for p in pts:
                if (p.get("id") or "") == "rebrand" or (p.get("kind") or "") == "rebrand":
                    raw = p
                    break
            if raw is None:
                raw = default_product_types()[-1]
        else:
            cx = (complexity or "medium").lower()
            if cx in ("math_clone", "clone", "simple"):
                want = "math_clone"
            elif cx == "complex":
                want = "complex"
            else:
                want = "medium"
            raw = _raw_product_type(pts, want)
            if raw is None:
                raw = pts[0] if pts else default_product_types()[0]
    return materialize_product_type(pts, raw)


def ensure_product_type_models(pts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backfill model/template_id on older stores without wiping strut edits."""
    out: list[dict[str, Any]] = []
    ids = {(p.get("id") or "") for p in pts}
    for p in pts:
        q = dict(p)
        pid = q.get("id") or ""
        if (q.get("model") or "").lower() in ("template", "variation"):
            if (q.get("model") or "").lower() == "variation" and not q.get(
                "template_id"
            ):
                if "primary" in ids:
                    q["template_id"] = "primary"
                elif "medium" in ids:
                    q["template_id"] = "medium"
                else:
                    q["template_id"] = ""
            out.append(q)
            continue
        if pid in ("complex", "math_clone"):
            q["model"] = "variation"
            if not q.get("template_id"):
                if "primary" in ids:
                    q["template_id"] = "primary"
                elif "medium" in ids:
                    q["template_id"] = "medium"
                else:
                    q["template_id"] = ""
        else:
            # medium / rebrand / custom — house template until operator renames code
            q["model"] = "template"
            q.pop("template_id", None)
        out.append(q)
    return out


def _strut_duration_days(s: dict[str, Any]) -> int:
    """How long a phase runs (gates = 0)."""
    if (s.get("role") or "") == "gate" or (s.get("kind") or "") == "point":
        return 0
    if s.get("duration_days") is not None and s.get("duration_days") != "":
        try:
            return max(0, int(s["duration_days"]))
        except (TypeError, ValueError):
            pass
    if s.get("duration_weeks") is not None and s.get("duration_weeks") != "":
        try:
            return max(0, int(round(float(s["duration_weeks"]) * 7)))
        except (TypeError, ValueError):
            pass
    # legacy absolute pins → duration
    if s.get("start_days_before") is not None:
        try:
            return max(
                0,
                int(s["start_days_before"]) - int(s.get("end_days_before") or 0),
            )
        except (TypeError, ValueError):
            return 0
    return 0


def _is_gate_strut(s: dict[str, Any]) -> bool:
    return (s.get("role") or "") == "gate" or (s.get("kind") or "") == "point"


def _release_label(pt: dict[str, Any]) -> str:
    release_label = (pt.get("release_label") or "").strip()
    if release_label:
        return release_label
    return (
        "Betsoft Release"
        if (pt.get("kind") or "") == "rebrand"
        else "Global Release"
    )


def _weeks_to_days(w: Any) -> int:
    try:
        return int(round(float(w or 0) * 7))
    except (TypeError, ValueError):
        return 0


def gate_offset_days(rule: dict[str, Any]) -> int:
    """Gate offset as whole days. Prefer offset_days; fall back to offset_weeks."""
    if rule.get("offset_days") is not None and rule.get("offset_days") != "":
        try:
            return max(0, int(round(float(rule.get("offset_days") or 0))))
        except (TypeError, ValueError):
            pass
    unit = (rule.get("offset_unit") or "").strip().lower()
    try:
        raw = float(rule.get("offset") if rule.get("offset") is not None else 0)
    except (TypeError, ValueError):
        raw = 0.0
    if unit == "days":
        return max(0, int(round(raw)))
    if unit == "weeks":
        return max(0, int(round(raw * 7)))
    # legacy: only offset_weeks
    if rule.get("offset_weeks") is not None and rule.get("offset_weeks") != "":
        return max(0, _weeks_to_days(rule.get("offset_weeks")))
    return 0


def empty_gate_rule(
    name: str = "New gate",
    *,
    anchor: str = "phase",
    phase_name: str = "",
    workstream_name: str = "",
    relation: str = "at_end",
    offset_weeks: float = 0,
    offset_days: int | None = None,
    offset_unit: str = "weeks",
) -> dict[str, Any]:
    """Template gate rule — point deadline, not a phase stack row."""
    a = (anchor or "phase").strip().lower()
    if a not in ("phase", "release", "workstream"):
        a = "phase"
    unit = (offset_unit or "weeks").strip().lower()
    if unit not in ("weeks", "days"):
        unit = "weeks"
    days = (
        int(offset_days)
        if offset_days is not None
        else (int(round(offset_weeks * 7)) if unit == "weeks" else int(offset_weeks))
    )
    return {
        "id": f"gt-{secrets.token_hex(4)}",
        "name": name,
        "role": "gate",
        "kind": "point",
        # anchor: phase | workstream | release
        "anchor": a,
        "phase_name": phase_name or "",
        "workstream_name": workstream_name or "",
        # relation: where the point sits relative to anchor window
        # phase/stream: at_start | at_end | before_start | after_end | offset_from_start | offset_from_end
        # release: at_release | before_release | after_release
        "relation": relation or "at_end",
        "offset_unit": unit,
        "offset_days": max(0, days),
        # keep weeks for old UI / readability when unit is weeks
        "offset_weeks": round(days / 7, 4) if days else 0,
    }


def _window_point(
    win: dict[str, Any] | None,
    rel: str,
    days: int,
) -> date | None:
    if not win or "point" in win:
        return None
    start, end = win.get("start"), win.get("end")
    if rel == "at_start":
        return start
    if rel == "at_end":
        return end
    if rel == "before_start":
        return start - timedelta(days=days) if start else None
    if rel == "after_end":
        return end + timedelta(days=days) if end else None
    if rel == "offset_from_start":
        return start + timedelta(days=days) if start else None
    if rel == "offset_from_end":
        return end - timedelta(days=days) if end else None
    return end


def _workstream_window(
    phase_win: dict[str, Any],
    ws: dict[str, Any],
) -> dict[str, Any] | None:
    """Same portion math as apply_workstream_dates, for gate anchors."""
    p_start = phase_win.get("start")
    p_end = phase_win.get("end")
    if not isinstance(p_start, date):
        return None
    try:
        off_w = float(ws.get("offset_weeks_from_start") or 0)
    except (TypeError, ValueError):
        off_w = 0.0
    try:
        raw_dur = ws.get("duration_weeks")
        dur_w = (
            float(raw_dur) if raw_dur is not None and raw_dur != "" else None
        )
    except (TypeError, ValueError):
        dur_w = None
    fill = ws.get("fill_parent")
    if fill is None:
        fill = dur_w is None and off_w == 0
    else:
        fill = bool(fill)
    if dur_w is not None and dur_w > 0:
        fill = False
    if fill or p_end is None:
        return {"start": p_start, "end": p_end or p_start}
    start = p_start + timedelta(days=int(round(off_w * 7)))
    if dur_w is None or dur_w <= 0:
        end = p_end
    else:
        end = start + timedelta(days=int(round(dur_w * 7)))
    if p_end and end > p_end:
        end = p_end
    if p_end and start > p_end:
        start = p_end
    if start < p_start:
        start = p_start
    if end < start:
        end = start
    return {"start": start, "end": end}


def resolve_gate_point(
    rule: dict[str, Any],
    phase_windows: dict[str, dict[str, Any]],
    ship: date,
    stream_windows: dict[str, dict[str, Any]] | None = None,
) -> date | None:
    """Compute a single gate calendar day from rule + phase/stream windows + ship."""
    rel = (rule.get("relation") or "at_end").strip().lower()
    anchor = (rule.get("anchor") or "phase").strip().lower()
    days = gate_offset_days(rule)
    stream_windows = stream_windows or {}

    # release-relative (day precision: N days before/after ship)
    if anchor == "release" or rel in (
        "at_release",
        "before_release",
        "after_release",
    ):
        if rel == "at_release" or (
            anchor == "release" and rel in ("at_end", "at_start") and days == 0
        ):
            return ship
        if rel == "after_release":
            return ship + timedelta(days=days)
        # before_release (default for release + offset)
        return ship - timedelta(days=days)

    # workstream-relative (parent phase + stream name)
    if anchor == "workstream":
        pname = (rule.get("phase_name") or "").strip()
        wname = (rule.get("workstream_name") or "").strip()
        key = f"{pname}::{wname}"
        win = stream_windows.get(key)
        if not win and pname and wname:
            # fallback: phase window only if stream unknown
            win = phase_windows.get(pname)
        return _window_point(win, rel, days)

    # phase-relative
    pname = (rule.get("phase_name") or "").strip()
    win = phase_windows.get(pname) if pname else None
    return _window_point(win, rel, days)


def dates_from_product_type(pt: dict[str, Any], ship: date) -> dict[str, dict[str, Any]]:
    """
    Reverse-calc phase dates from a hard ship/release date, then gate points.

    Template = ordered phases (top = earliest) + release_label + gate rules.
    Cursor starts at ship; each phase (bottom→top) claims
    [cursor - duration, cursor], then cursor moves earlier.
    Gates are a second pass (phase, workstream, or release anchors).
    """
    struts = list(pt.get("struts") or [])
    out: dict[str, dict[str, Any]] = {}
    cursor = ship

    # Ship date is the title's core field (day 0) — not an auto-inserted gate row.
    # Release-relative gates use `ship` directly in resolve_gate_point.

    # phases only — ignore any residual gate rows in old strut lists
    phases = [s for s in struts if not _is_gate_strut(s)]
    phase_windows: dict[str, dict[str, Any]] = {}
    stream_windows: dict[str, dict[str, Any]] = {}
    for s in reversed(phases):
        name = (s.get("name") or "").strip()
        if not name:
            continue
        dur = _strut_duration_days(s)
        end = cursor
        start = cursor - timedelta(days=dur)
        out[name] = {"start": start, "end": end}
        phase_windows[name] = {"start": start, "end": end}
        for ws in s.get("workstreams") or []:
            if not isinstance(ws, dict):
                continue
            wname = (ws.get("name") or "").strip()
            if not wname:
                continue
            ww = _workstream_window(phase_windows[name], ws)
            if ww:
                stream_windows[f"{name}::{wname}"] = ww
        cursor = start

    # gate rules on the product type (template structure; variations inherit)
    for rule in pt.get("gates") or []:
        if not isinstance(rule, dict):
            continue
        gname = (rule.get("name") or "").strip()
        if not gname:
            continue
        pt_day = resolve_gate_point(
            rule, phase_windows, ship, stream_windows=stream_windows
        )
        if pt_day is not None:
            out[gname] = {"point": pt_day}

    return out


def offset_table_from_product_type(pt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Legacy helper: materialize absolute days-before from duration stack (ship=epoch)."""
    # Use a fake ship far in future only to get relative day counts
    ship = date(2099, 1, 1)
    dated = dates_from_product_type(pt, ship)
    table: dict[str, dict[str, Any]] = {}
    for name, d in dated.items():
        if "point" in d:
            ptv = d["point"]
            if ptv is None:
                table[name] = {"point": None}
            else:
                table[name] = {"point": (ship - ptv).days}
        else:
            table[name] = {
                "start": (ship - d["start"]).days,
                "end": (ship - d["end"]).days,
            }
    return table


def build_spine_from_product_type(pt: dict[str, Any]) -> list[dict[str, Any]]:
    """Empty events: phases (+ workstreams) + template gate rules only.

    Hard ship/release is the title's release_date field — not an auto gate row.
    """
    out: list[dict[str, Any]] = []
    i = 0
    for s in pt.get("struts") or []:
        if _is_gate_strut(s):
            continue  # gates live on pt["gates"], not in phase stack
        name = (s.get("name") or f"Phase {i + 1}").strip()
        ev = empty_event(name, "phase", "range", i)
        streams: list[dict[str, Any]] = []
        for j, ws in enumerate(s.get("workstreams") or []):
            wname = (ws.get("name") or f"Stream {j + 1}").strip()
            if not wname:
                continue
            try:
                off = float(ws.get("offset_weeks_from_start") or 0)
            except (TypeError, ValueError):
                off = 0.0
            raw_dur = ws.get("duration_weeks")
            try:
                dur = (
                    float(raw_dur)
                    if raw_dur is not None and raw_dur != ""
                    else None
                )
            except (TypeError, ValueError):
                dur = None
            fill = ws.get("fill_parent")
            if fill is None:
                fill = dur is None and off == 0
            else:
                fill = bool(fill)
            if dur is not None and dur > 0:
                fill = False
            streams.append(
                empty_workstream(
                    wname,
                    fill_parent=fill,
                    offset_weeks_from_start=off,
                    duration_weeks=None if fill else dur,
                    sort=j,
                )
            )
        ev["workstreams"] = streams
        out.append(ev)
        i += 1

    seen_gate_names: set[str] = set()
    for rule in pt.get("gates") or []:
        if not isinstance(rule, dict):
            continue
        gname = (rule.get("name") or "").strip()
        if not gname or gname in seen_gate_names:
            continue
        seen_gate_names.add(gname)
        gev = empty_event(gname, "gate", "point", i)
        # keep rule identity for recompute / UI
        gev["gate_rule_id"] = rule.get("id") or ""
        gev["gate_anchor"] = rule.get("anchor") or "phase"
        gev["gate_phase_name"] = rule.get("phase_name") or ""
        gev["gate_workstream_name"] = rule.get("workstream_name") or ""
        gev["gate_relation"] = rule.get("relation") or "at_end"
        gev["gate_offset_weeks"] = rule.get("offset_weeks") or 0
        gev["gate_offset_days"] = gate_offset_days(rule)
        gev["gate_offset_unit"] = rule.get("offset_unit") or "weeks"
        out.append(gev)
        i += 1

    return out


def apply_workstream_dates(phase: dict[str, Any]) -> None:
    """Fill workstream dates from parent phase window.

    fill_parent=True  → same start/end as parent (overlap full window).
    fill_parent=False → start = parent_start + offset_weeks_from_start,
                        end = start + duration_weeks (clamped to parent end).

    Also treats a stream as *portion* if duration_weeks is set even when
    fill_parent was left true by mistake (portion wins).
    """
    streams = phase.get("workstreams")
    if not isinstance(streams, list):
        phase["workstreams"] = []
        return
    p_start_s = phase.get("start")
    p_end_s = phase.get("end")
    p_start = _parse_date(p_start_s)
    p_end = _parse_date(p_end_s)
    for ws in streams:
        if not isinstance(ws, dict):
            continue
        if not ws.get("id"):
            ws["id"] = f"ws-{secrets.token_hex(4)}"
        # normalize flags from template / older titles
        try:
            off_w = float(ws.get("offset_weeks_from_start") or 0)
        except (TypeError, ValueError):
            off_w = 0.0
        try:
            raw_dur = ws.get("duration_weeks")
            dur_w = (
                float(raw_dur)
                if raw_dur is not None and raw_dur != ""
                else None
            )
        except (TypeError, ValueError):
            dur_w = None
        fill = ws.get("fill_parent")
        if fill is None:
            fill = dur_w is None and off_w == 0
        else:
            fill = bool(fill)
        # explicit portion fields override a stale fill_parent=true
        if dur_w is not None and dur_w > 0:
            fill = False
            ws["fill_parent"] = False
        ws["offset_weeks_from_start"] = off_w
        if dur_w is not None:
            ws["duration_weeks"] = dur_w

        # Manual sheet edits stick — do not recompute locked streams
        if ws.get("locked"):
            continue

        if fill or p_start is None:
            ws["start"] = p_start_s
            ws["end"] = p_end_s
            continue

        if dur_w is None or dur_w <= 0:
            # offset only → from that week through parent end
            start = p_start + timedelta(days=int(round(off_w * 7)))
            end = p_end or start
        else:
            start = p_start + timedelta(days=int(round(off_w * 7)))
            end = start + timedelta(days=int(round(dur_w * 7)))
        if p_end and end > p_end:
            end = p_end
        if p_end and start > p_end:
            start = p_end
        if start < p_start:
            start = p_start
        if end < start:
            end = start
        ws["start"] = _fmt(start)
        ws["end"] = _fmt(end)


def build_spine(kind: str = "title", complexity: str = "medium") -> list[dict[str, Any]]:
    """Empty dated spine for a new title (legacy entry)."""
    pt = find_product_type(None, None, kind=kind, complexity=complexity)
    return build_spine_from_product_type(pt)


def apply_ship_date(
    phases: list[dict[str, Any]],
    ship: date,
    *,
    kind: str = "title",
    complexity: str = "medium",
    product_type: dict[str, Any] | None = None,
    respect_locked: bool = True,
    reason: str = "auto from ship date",
) -> list[dict[str, Any]]:
    """
    Reverse-calc all spine dates from Global Release / Betsoft Release.
    Locked events keep their dates.

    With product_type: order + phase durations stack backward from ship.
    Without: legacy absolute offset tables.
    """
    if product_type:
        dated = dates_from_product_type(product_type, ship)
        table = None
        # ensure template gate rows exist on the title (by name)
        # do NOT auto-insert Global/Betsoft Release — ship lives on title.release_date
        phases = list(phases or [])
        have = {(p.get("name") or "").strip() for p in phases}
        sort_base = max((int(p.get("sort") or 0) for p in phases), default=0) + 1
        for rule in product_type.get("gates") or []:
            if not isinstance(rule, dict):
                continue
            gname = (rule.get("name") or "").strip()
            if not gname or gname in have:
                continue
            gev = empty_event(gname, "gate", "point", sort_base)
            gev["gate_rule_id"] = rule.get("id") or ""
            phases.append(gev)
            have.add(gname)
            sort_base += 1
        phases = phases
    else:
        dated = None
        table = _offset_table(kind, complexity)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(phases or []):
        q = dict(p)
        name = q.get("name") or ""
        if respect_locked and q.get("locked") and (q.get("start") or q.get("end")):
            q["placeholder"] = False
            if (q.get("role") or "phase") == "phase":
                apply_workstream_dates(q)
            out.append(q)
            continue

        before = {
            "name": q.get("name"),
            "start": q.get("start"),
            "end": q.get("end"),
            "role": q.get("role"),
        }

        if dated is not None:
            off = dated.get(name)
            if not off:
                out.append(q)
                continue
            if "point" in off:
                ptv = off["point"]
                if ptv is None:
                    q["start"] = None
                    q["end"] = None
                    q["placeholder"] = True
                else:
                    q["start"] = _fmt(ptv)
                    q["end"] = _fmt(ptv)
                    q["kind"] = "point"
                    q["placeholder"] = False
            else:
                s, e = off["start"], off["end"]
                if s > e:
                    s, e = e, s
                q["start"] = _fmt(s)
                q["end"] = _fmt(e)
                q["kind"] = "range"
                q["placeholder"] = False
        else:
            off = (table or {}).get(name)
            if not off:
                out.append(q)
                continue
            if "point" in off:
                pt = off["point"]
                if pt is None:
                    q["start"] = None
                    q["end"] = None
                    q["placeholder"] = True
                else:
                    d = ship - timedelta(days=int(pt))
                    q["start"] = _fmt(d)
                    q["end"] = _fmt(d)
                    q["kind"] = "point"
                    q["placeholder"] = False
            else:
                s = ship - timedelta(days=int(off["start"]))
                e = ship - timedelta(days=int(off["end"]))
                if s > e:
                    s, e = e, s
                q["start"] = _fmt(s)
                q["end"] = _fmt(e)
                q["kind"] = "range"
                q["placeholder"] = False

        after = {
            "name": q.get("name"),
            "start": q.get("start"),
            "end": q.get("end"),
            "role": q.get("role"),
        }
        if before != after and reason:
            if before.get("start") or before.get("end"):
                record_edit(q, reason=reason, before=before, after=after)

        q["sort"] = q.get("sort", i)
        # workstreams inherit parent window (overlapping teams)
        if (q.get("role") or "phase") == "phase":
            if "workstreams" not in q or q.get("workstreams") is None:
                q["workstreams"] = []
            apply_workstream_dates(q)
        out.append(q)
    return out


def build_spine_dated(
    ship: date | str | None,
    *,
    kind: str = "title",
    complexity: str = "medium",
    product_type: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Empty spine, then reverse-calc if ship date given."""
    pt = product_type or find_product_type(None, None, kind=kind, complexity=complexity)
    phases = build_spine_from_product_type(pt)
    d = ship if isinstance(ship, date) else _parse_date(ship)
    if not d:
        return phases
    return apply_ship_date(
        phases,
        d,
        kind=kind,
        complexity=complexity,
        product_type=pt,
        respect_locked=False,
        reason="",
    )


def spine_definition(kind: str = "title") -> list[dict[str, Any]]:
    rows = SPINE_REBRAND if kind == "rebrand" else SPINE_FULL
    defs = [
        {"name": n, "role": r, "kind": k, "order": i}
        for i, (n, r, k) in enumerate(rows)
    ]
    # release is always the terminal hard date for the phase pipeline
    rel = "Betsoft Release" if kind == "rebrand" else "Global Release"
    defs.append(
        {"name": rel, "role": "gate", "kind": "point", "order": len(defs)}
    )
    return defs


def record_edit(
    event: dict[str, Any],
    *,
    reason: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Append an edit-trail reason on one event (this title only)."""
    log = list(event.get("edits") or [])
    log.append(
        {
            "at": int(time.time()),
            "reason": (reason or "").strip() or "(no reason)",
            "before": {
                "name": before.get("name"),
                "start": before.get("start"),
                "end": before.get("end"),
                "role": before.get("role"),
            },
            "after": {
                "name": after.get("name"),
                "start": after.get("start"),
                "end": after.get("end"),
                "role": after.get("role"),
            },
        }
    )
    event["edits"] = log
    event["placeholder"] = not bool(after.get("start") or after.get("end"))
    # Manual Greg-style edit: pin the line so ship recompute / stream fill won't wipe it
    event["locked"] = True
