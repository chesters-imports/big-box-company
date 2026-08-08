"""Release-date reverse scheduling — house complexity rule sets.

Source clay: Q1 2027 Confluence schedule PDF (Scheduling-Q1 2027).
Difficulty = MEDIUM | COMPLEX | MATH_CLONE (NG math clone path).
Set Global Release → backfill phases from week offsets; lock individual
phases to preserve holiday / exclusivity tweaks.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


# --- Phase vs Gate vocabulary (shared labels across all titles) ---
# Rename is ALWAYS global: change the label everywhere, not on one title.
# Per-title commentary = title.notes (or optional event notes), not a private rename.

# Substrings / exact-ish patterns → canonical display name
_NAME_RULES: list[tuple[str, str]] = [
    (r"design\s*phase", "Design Phase"),
    (r"static\s*art", "Static Art Phase"),
    (r"^fx\s*phase|fx\s*phase", "FX Phase"),
    (r"deliver\s*math|math\s*and\s*specs", "Deliver Math to Devs"),
    (r"deliver\s*assets|all\s*assets\s*to\s*devs", "Deliver Assets to Devs"),
    (r"^dev\s*phase", "Dev Phase"),
    (r"deliver\s*audio|audio\s*team\s*deadline|audio\s*deadline", "Deliver Audio to Devs"),
    (r"qa:\s*localization|localization\s*phase", "QA: Localization Phase"),
    (r"qa:\s*lqa|^lqa\s*phase|lqa\s*testing", "QA: LQA Phase"),
    (r"qa:\s*rqa|rqa\s*all|rqa\s*localization|rqa\s*testing", "QA: RQA Localization Phase"),
    (r"active\s*rollout", "Active Rollout"),
    (r"exclusivity|test\s*live", "Exclusivity / Test Live"),
    (r"global\s*release", "Global Release"),
    (r"betsoft\s*release", "Betsoft Release"),
]

_GATE_NAMES = frozenset(
    {
        "Deliver Math to Devs",
        "Deliver Assets to Devs",
        "Deliver Audio to Devs",
        "Math & Specs → Devs",
        "All Assets → Devs",
        "Audio Deadline",
        "Exclusivity / Test Live",
        "Global Release",
        "Betsoft Release",
        "Ready for Rollout",
        "Request RQA (EN)",
        "Product Sheets → AM",
        "Marketing + Demo",
    }
)

_PHASE_NAMES = frozenset(
    {
        "Design Phase",
        "Static Art Phase",
        "FX Phase",
        "Dev Phase",
        "Active Rollout",  # multi-day go-live window (not a one-shot gate)
        "QA: Localization Phase",
        "QA: LQA Phase",
        "QA: RQA Localization Phase",
        "Localization Phase",
        "LQA Phase",
        "RQA All Locales",
        "QA Phase",
        "Beta QA",
        "Product QA",
    }
)

_NAME_RULES_EXTRA: list[tuple[str, str]] = []


def normalize_event_name(name: str | None) -> str:
    """Canonical shared label — same string used on every title."""
    import re

    raw = (name or "").strip()
    if not raw:
        return "Untitled event"
    # strip parentheticals / arrows / week counts
    s = re.sub(r"\s*←.*$", "", raw)
    s = re.sub(r"\s*\([^)]*\bweeks?\b[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\+\s*\d+\s*weeks?\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s*\+\s*\d+\s*week\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s*\(Tuesday[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(Thursday[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(Monday[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(Friday[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\(Wednesday[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"^\(Monday\):\s*", "", s, flags=re.I)
    s = re.sub(r":\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    low = s.lower()
    # Prefer QA Phase collapse over separate Beta/Product labels
    for pat, canon in _NAME_RULES_EXTRA + _NAME_RULES:
        if re.search(pat, low, re.I):
            return canon
    # title-case soft cleanup if no rule
    if len(s) > 60:
        s = s[:57] + "…"
    return s


def event_role(name: str | None, kind: str | None = None) -> str:
    """
    phase = multi-day work container owned by a craft group
    gate  = one-time delivery / deadline / handoff
    """
    n = normalize_event_name(name)
    if n in _GATE_NAMES:
        return "gate"
    if n in _PHASE_NAMES:
        return "phase"
    # fallback: point dates are gates, ranges are phases
    if (kind or "").lower() == "point":
        return "gate"
    return "phase"


def normalize_phases_list(phases: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Apply canonical names + role tags to a title's events."""
    out: list[dict[str, Any]] = []
    for i, p in enumerate(phases or []):
        q = dict(p)
        q["name"] = normalize_event_name(q.get("name"))
        q["role"] = event_role(q["name"], q.get("kind"))
        # keep kind range/point; gates often point
        if q["role"] == "gate" and q.get("kind") != "point":
            # short ranges (rollout 2 days) stay range but role=gate
            pass
        q["sort"] = q.get("sort", i)
        out.append(q)
    return out


def rename_label_everywhere(
    titles: list[dict[str, Any]], old: str, new: str
) -> int:
    """
    Global rename: every event named `old` becomes `new` on every title.
    Returns number of events changed.
    """
    old_n = normalize_event_name(old)
    new_n = (new or "").strip() or old_n
    # user may rename already-canonical or dirty names
    old_raw = (old or "").strip()
    changed = 0
    for t in titles:
        for p in t.get("phases") or []:
            nm = (p.get("name") or "").strip()
            if nm == old_raw or normalize_event_name(nm) == old_n or nm == old_n:
                p["name"] = new_n
                p["role"] = event_role(new_n, p.get("kind"))
                changed += 1
    return changed


def cleanup_all_labels(titles: list[dict[str, Any]]) -> int:
    """Normalize every event name across the board. Returns number of events renamed."""
    n = 0
    for t in titles:
        old_phases = t.get("phases") or []
        new_phases = normalize_phases_list(old_phases)
        for a, b in zip(old_phases, new_phases):
            if (a.get("name") or "") != (b.get("name") or "") or a.get("role") != b.get(
                "role"
            ):
                n += 1
        t["phases"] = new_phases
    return n


# ---------------------------------------------------------------------------
# House standard spine — shared bins for primary production.
# Every full title maps onto these slots; extras stay as off-spine.
# ---------------------------------------------------------------------------

# DOS Castaway labels (hands office import) — the house strut
STANDARD_SPINE: list[tuple[str, str, str]] = [
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
    ("Betsoft Release", "gate", "point"),
]

# Map any leftover / alias names → DOS spine
_SPINE_ALIASES: dict[str, str] = {
    "Design Phase": "Design Phase",
    "Static Art Phase": "Static Art Phase",
    "FX Phase": "FX Phase",
    "Deliver Math to Devs": "Deliver Math to Devs",
    "Math & Specs → Devs": "Deliver Math to Devs",
    "Deliver Assets to Devs": "Deliver Assets to Devs",
    "All Assets → Devs": "Deliver Assets to Devs",
    "Dev Phase": "Dev Phase",
    "Deliver Audio to Devs": "Deliver Audio to Devs",
    "Audio Deadline": "Deliver Audio to Devs",
    "QA: Localization Phase": "QA: Localization Phase",
    "Localization Phase": "QA: Localization Phase",
    "QA: LQA Phase": "QA: LQA Phase",
    "LQA Phase": "QA: LQA Phase",
    "QA: RQA Localization Phase": "QA: RQA Localization Phase",
    "RQA All Locales": "QA: RQA Localization Phase",
    "Active Rollout": "Active Rollout",
    "Exclusivity / Test Live": "Exclusivity / Test Live",
    "Global Release": "Global Release",
    "Betsoft Release": "Betsoft Release",
    "QA Phase": "QA: Localization Phase",
    "Beta QA": "QA: Localization Phase",
    "Product QA": "QA: Localization Phase",
}

SPINE_FULL = [s[0] for s in STANDARD_SPINE if s[0] != "Betsoft Release"]
SPINE_CLONE = list(SPINE_FULL)
SPINE_REBRAND = [
    "QA: LQA Phase",
    "QA: RQA Localization Phase",
    "Active Rollout",
    "Betsoft Release",
]


def spine_slot(name: str | None) -> str | None:
    """Which standard spine slot does this label belong to? None = off-spine."""
    n = normalize_event_name(name)
    return _SPINE_ALIASES.get(n)


def expected_spine_for_title(t: dict[str, Any]) -> list[str]:
    kind = (t.get("kind") or "title").lower()
    cx = normalize_complexity(t.get("complexity"))
    if kind == "rebrand":
        return list(SPINE_REBRAND)
    if cx == "math_clone":
        return list(SPINE_CLONE)
    return list(SPINE_FULL)


def _event_priority(p: dict[str, Any]) -> tuple:
    """Prefer dated, locked, longer-named when merging into one spine slot."""
    has_date = 1 if (p.get("start") or p.get("end")) else 0
    locked = 1 if p.get("locked") else 0
    return (has_date, locked, len(p.get("name") or ""))


def align_title_to_spine(
    t: dict[str, Any],
    *,
    fill_missing: bool = True,
) -> dict[str, Any]:
    """
    Map a title's events onto the house spine.
    - Known labels merge into one slot (e.g. Beta QA + Product QA → QA Phase)
    - Off-spine leftovers kept at the end (spine=False)
    - Missing expected slots optionally added with empty dates (placeholders)
    """
    t["phases"] = normalize_phases_list(t.get("phases"))
    kind = (t.get("kind") or "title").lower()
    by_slot: dict[str, dict[str, Any]] = {}
    off: list[dict[str, Any]] = []

    for p in t.get("phases") or []:
        slot = spine_slot(p.get("name"))
        # Betsoft Release belongs on rebrand twin only — strip from nucleus/full titles
        if slot == "Betsoft Release" and kind != "rebrand":
            continue
        # Global Release is nucleus ship day — rebrands use Betsoft Release
        if slot == "Global Release" and kind == "rebrand":
            continue
        if not slot:
            q = dict(p)
            q["spine"] = False
            q["role"] = event_role(q.get("name"), q.get("kind"))
            off.append(q)
            continue
        cand = dict(p)
        cand["name"] = slot
        cand["role"] = event_role(slot, cand.get("kind"))
        cand["spine"] = True
        prev = by_slot.get(slot)
        if prev is None or _event_priority(cand) >= _event_priority(prev):
            if prev and prev.get("notes") and prev.get("notes") != cand.get("notes"):
                extra = prev.get("notes") or ""
                if extra and extra not in (cand.get("notes") or ""):
                    cand["notes"] = ((cand.get("notes") or "") + " · " + extra).strip(
                        " ·"
                    )
            by_slot[slot] = cand

    expected = expected_spine_for_title(t)
    ordered: list[dict[str, Any]] = []
    sort_i = 0
    for name, role, kind in STANDARD_SPINE:
        if name not in expected and name not in by_slot:
            continue
        if name in by_slot:
            ev = by_slot[name]
            ev["sort"] = sort_i
            ev["spine"] = True
            ev["role"] = role
            ordered.append(ev)
            sort_i += 1
        elif fill_missing and name in expected:
            ordered.append(
                {
                    "id": f"ph-spine-{sort_i:02d}",
                    "name": name,
                    "kind": kind,
                    "role": role,
                    "start": None,
                    "end": None,
                    "locked": False,
                    "notes": "",
                    "sort": sort_i,
                    "spine": True,
                    "placeholder": True,
                }
            )
            sort_i += 1

    for p in off:
        p["sort"] = sort_i
        p["spine"] = False
        ordered.append(p)
        sort_i += 1

    t["phases"] = ordered
    return t


def align_all_to_spine(
    titles: list[dict[str, Any]], *, fill_missing: bool = True
) -> dict[str, int]:
    """Align every title. Returns stats."""
    n_titles = 0
    n_off = 0
    n_ph = 0
    for t in titles:
        align_title_to_spine(t, fill_missing=fill_missing)
        n_titles += 1
        for p in t.get("phases") or []:
            n_ph += 1
            if p.get("spine") is False:
                n_off += 1
    return {
        "titles": n_titles,
        "events": n_ph,
        "off_spine": n_off,
    }


def spine_definition() -> list[dict[str, Any]]:
    return [
        {"name": n, "role": r, "kind": k, "order": i}
        for i, (n, r, k) in enumerate(STANDARD_SPINE)
    ]


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def fmt_date(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _week(n: float) -> int:
    return int(round(n * 7))


# Week offsets BEFORE global release (end of phase / point date).
# Measured from typical MEDIUM full pipeline (Castaway / Love Potion pattern).
# order matters for board display.
#
# Pipeline spine (full product, not math-clone):
#   Design+MathStart 4w → Static 4w → FX 4w
#   Math&Specs point (2–4w before All Assets)
#   All Assets point → Dev 12w (medium) / 14w (complex)
#   Audio = 3w before Product/Beta QA start
#   Beta QA 3w (medium) | Product QA 2w (clone)
#   Request RQA (point) → Loc 2w → LQA 2w ∥ RQA Loc 2w
#   Product sheets + marketing (points at LQA start)
#   Active Rollout 2d → Exclusivity ~2w before release → Global Release


def _medium_rules() -> list[dict[str, Any]]:
    """DIFFICULTY = MEDIUM · full design + math path · ~12w dev."""
    # From Global Release, working backwards in weeks:
    # Release = 0
    # Exclusivity ~ 2w before
    # Active Rollout ends ~ day before exclusivity (~2w + a few days)
    # LQA/RQA end ~ 2w before exclusivity window ≈ 4w before release
    # Loc ends when LQA starts ≈ 6w before release
    # Beta QA ends at Request RQA ≈ 6w before; Beta is 3w → starts ~9w
    # Dev ends at Beta start ≈ 9w; Dev 12w → starts ~21w
    # All Assets = Dev start ≈ 21w
    # Math specs ~ 2–3w before All Assets ≈ 23–24w
    # FX ends All Assets ≈ 21w; FX 4w → starts 25w
    # Static 4w → starts 29w
    # Design 4w → starts 33w
    return [
        {
            "name": "Design Phase & Math Start",
            "kind": "range",
            "start_days_before": _week(33),
            "end_days_before": _week(29),
            "weeks_label": 4,
        },
        {
            "name": "Static Art Phase",
            "kind": "range",
            "start_days_before": _week(29),
            "end_days_before": _week(25),
            "weeks_label": 4,
        },
        {
            "name": "FX Phase",
            "kind": "range",
            "start_days_before": _week(25),
            "end_days_before": _week(21),
            "weeks_label": 4,
        },
        {
            "name": "Math and Specs to Devs",
            "kind": "point",
            "days_before": _week(23),  # ~2w before All Assets (adjustable)
            "note": "Incomplete maths OK; 2–4w before All Assets by title",
        },
        {
            "name": "All Assets to Devs",
            "kind": "point",
            "days_before": _week(21),
        },
        {
            "name": "Dev Phase",
            "kind": "range",
            "start_days_before": _week(21),
            "end_days_before": _week(9),
            "weeks_label": 12,
        },
        {
            "name": "Audio Team Deadline",
            "kind": "point",
            "days_before": _week(12),  # 3w before Beta QA start (~9w)
            "note": "3 weeks before Product/Beta QA",
        },
        {
            "name": "Beta QA (Product + Math QA)",
            "kind": "range",
            "start_days_before": _week(9),
            "end_days_before": _week(6),
            "weeks_label": 3,
        },
        {
            "name": "Request RQA Testing (English)",
            "kind": "point",
            "days_before": _week(6),
        },
        {
            "name": "Localization Phase",
            "kind": "range",
            "start_days_before": _week(6),
            "end_days_before": _week(4),
            "weeks_label": 2,
        },
        {
            "name": "LQA Phase",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "RQA All Localizations",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "Product Sheets to AM (sim stats)",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Marketing Materials + Website Demo",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Active Rollout",
            "kind": "range",
            "start_days_before": _week(2) + 2,
            "end_days_before": _week(2) + 1,
            "weeks_label": 0,
            "note": "Usually Tue–Wed; shift for holidays",
        },
        {
            "name": "Exclusivity / Test Live (MM On)",
            "kind": "point",
            "days_before": _week(2),
            "note": "Often 2w before Global; sometimes shortened/removed",
        },
        {
            "name": "Global Release",
            "kind": "point",
            "days_before": 0,
        },
    ]


def _complex_rules() -> list[dict[str, Any]]:
    """DIFFICULTY = COMPLEX · longer Dev (14w) · longer Math lead sometimes."""
    # Dev 14w → starts ~23w before release if Beta still ends ~9w... 
    # Actually: Beta 3w ending at Loc start ~6w → Beta starts 9w
    # Dev ends Beta start = 9w; Dev 14w → start 23w
    # Design chain: 4+4+4 before assets = starts 35w
    return [
        {
            "name": "Design Phase & Math Start",
            "kind": "range",
            "start_days_before": _week(35),
            "end_days_before": _week(31),
            "weeks_label": 4,
        },
        {
            "name": "Static Art Phase",
            "kind": "range",
            "start_days_before": _week(31),
            "end_days_before": _week(27),
            "weeks_label": 4,
        },
        {
            "name": "FX Phase",
            "kind": "range",
            "start_days_before": _week(27),
            "end_days_before": _week(23),
            "weeks_label": 4,
        },
        {
            "name": "Math and Specs to Devs",
            "kind": "point",
            "days_before": _week(26),  # ~3–4w before assets
            "note": "Complex: more math lead time",
        },
        {
            "name": "All Assets to Devs",
            "kind": "point",
            "days_before": _week(23),
        },
        {
            "name": "Dev Phase",
            "kind": "range",
            "start_days_before": _week(23),
            "end_days_before": _week(9),
            "weeks_label": 14,
        },
        {
            "name": "Audio Team Deadline",
            "kind": "point",
            "days_before": _week(12),
        },
        {
            "name": "Beta QA (Product + Math QA)",
            "kind": "range",
            "start_days_before": _week(9),
            "end_days_before": _week(6),
            "weeks_label": 3,
        },
        {
            "name": "Request RQA Testing (English)",
            "kind": "point",
            "days_before": _week(6),
        },
        {
            "name": "Localization Phase",
            "kind": "range",
            "start_days_before": _week(6),
            "end_days_before": _week(4),
            "weeks_label": 2,
        },
        {
            "name": "LQA Phase",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "RQA All Localizations",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "Product Sheets to AM (sim stats)",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Marketing Materials + Website Demo",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Active Rollout",
            "kind": "range",
            "start_days_before": _week(2) + 2,
            "end_days_before": _week(2) + 1,
        },
        {
            "name": "Exclusivity / Test Live (MM On)",
            "kind": "point",
            "days_before": _week(2),
        },
        {
            "name": "Global Release",
            "kind": "point",
            "days_before": 0,
        },
    ]


def _math_clone_rules() -> list[dict[str, Any]]:
    """NG math clone · shorter Dev · Math/Specs often N/A · Product QA not full Beta+Math."""
    # e.g. 3 Pot Buffalo: Dev 10w, Product QA 2w, Math specs marked not required
    return [
        {
            "name": "Design Phase",
            "kind": "range",
            "start_days_before": _week(30),
            "end_days_before": _week(26),
            "weeks_label": 4,
        },
        {
            "name": "Static Art Phase",
            "kind": "range",
            "start_days_before": _week(26),
            "end_days_before": _week(22),
            "weeks_label": 4,
        },
        {
            "name": "FX Phase",
            "kind": "range",
            "start_days_before": _week(22),
            "end_days_before": _week(18),
            "weeks_label": 4,
        },
        {
            "name": "All Assets to Devs",
            "kind": "point",
            "days_before": _week(18),
            "note": "Math clone: Math and Specs to Devs often not required",
        },
        {
            "name": "Dev Phase",
            "kind": "range",
            "start_days_before": _week(18),
            "end_days_before": _week(8),
            "weeks_label": 10,
        },
        {
            "name": "Audio Team Deadline",
            "kind": "point",
            "days_before": _week(11),
        },
        {
            "name": "Product QA",
            "kind": "range",
            "start_days_before": _week(8),
            "end_days_before": _week(6),
            "weeks_label": 2,
        },
        {
            "name": "Request RQA Testing (English)",
            "kind": "point",
            "days_before": _week(6),
        },
        {
            "name": "Localization Phase",
            "kind": "range",
            "start_days_before": _week(6),
            "end_days_before": _week(4),
            "weeks_label": 2,
        },
        {
            "name": "LQA Phase",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "RQA All Localizations",
            "kind": "range",
            "start_days_before": _week(4),
            "end_days_before": _week(2),
            "weeks_label": 2,
        },
        {
            "name": "Product Sheets to AM (sim stats)",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Marketing Materials + Website Demo",
            "kind": "point",
            "days_before": _week(4),
        },
        {
            "name": "Active Rollout",
            "kind": "range",
            "start_days_before": _week(2) + 2,
            "end_days_before": _week(2) + 1,
        },
        {
            "name": "Exclusivity / Test Live (MM On)",
            "kind": "point",
            "days_before": _week(2),
        },
        {
            "name": "Global Release",
            "kind": "point",
            "days_before": 0,
        },
    ]


def default_templates() -> dict[str, list[dict[str, Any]]]:
    return {
        "medium": _medium_rules(),
        "complex": _complex_rules(),
        "math_clone": _math_clone_rules(),
        # aliases used in UI
        "standard": _medium_rules(),
        "simple": _math_clone_rules(),
    }


def normalize_complexity(cx: str | None) -> str:
    c = (cx or "medium").strip().lower().replace(" ", "_")
    aliases = {
        "med": "medium",
        "standard": "medium",
        "std": "medium",
        "hard": "complex",
        "clone": "math_clone",
        "math-clone": "math_clone",
        "mathclone": "math_clone",
        "simple": "math_clone",
    }
    c = aliases.get(c, c)
    if c not in ("medium", "complex", "math_clone"):
        return "medium"
    return c


def apply_release(
    release: date,
    rules: list[dict[str, Any]],
    existing_phases: list[dict[str, Any]] | None = None,
    *,
    respect_locks: bool = True,
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    if existing_phases:
        for p in existing_phases:
            nm = (p.get("name") or "").strip()
            if nm:
                by_name[nm] = p

    out: list[dict[str, Any]] = []
    for i, rule in enumerate(rules):
        name = (rule.get("name") or f"Phase {i + 1}").strip()
        kind = rule.get("kind") or "range"
        prev = by_name.get(name) or {}
        locked = bool(prev.get("locked")) if respect_locks else False

        if locked and prev:
            out.append(
                {
                    "id": prev.get("id") or _phase_id(name, i),
                    "name": name,
                    "kind": prev.get("kind") or kind,
                    "start": prev.get("start"),
                    "end": prev.get("end"),
                    "locked": True,
                    "notes": prev.get("notes") or rule.get("note") or "",
                    "sort": i,
                }
            )
            continue

        if kind == "point":
            d = release - timedelta(days=int(rule.get("days_before") or 0))
            start = end = fmt_date(d)
        else:
            start_d = release - timedelta(
                days=int(rule.get("start_days_before") or 0)
            )
            end_d = release - timedelta(days=int(rule.get("end_days_before") or 0))
            if start_d > end_d:
                start_d, end_d = end_d, start_d
            start, end = fmt_date(start_d), fmt_date(end_d)

        out.append(
            {
                "id": prev.get("id") or _phase_id(name, i),
                "name": name,
                "kind": kind,
                "start": start,
                "end": end,
                "locked": False,
                "notes": prev.get("notes") or rule.get("note") or "",
                "sort": i,
            }
        )
    return out


def _phase_id(name: str, i: int) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower())[:28]
    return f"ph-{i:02d}-{slug}"


def current_phase_name(phases: list[dict[str, Any]], today: date | None = None) -> str:
    today = today or date.today()
    upcoming: list[tuple[date, str]] = []
    past: list[tuple[date, str]] = []

    for p in sorted(phases, key=lambda x: int(x.get("sort") or 0)):
        name = p.get("name") or "—"
        kind = p.get("kind") or "range"
        s = parse_date(p.get("start"))
        e = parse_date(p.get("end")) or s
        if not s and not e:
            continue
        if kind == "point":
            d = s or e
            if not d:
                continue
            if d == today:
                return name
            if d > today:
                upcoming.append((d, name))
            else:
                past.append((d, name))
            continue
        start = s or e
        end = e or s
        if start and end and start <= today <= end:
            return name
        if start and start > today:
            upcoming.append((start, name))
        elif end and end < today:
            past.append((end, name))

    if upcoming:
        upcoming.sort(key=lambda t: t[0])
        return f"→ {upcoming[0][1]}"
    if past:
        past.sort(key=lambda t: t[0])
        return past[-1][1]
    return "Unscheduled"


# Operator lifecycle (not pipeline lane) — set on the title card.
# "Active" = live work (not "In production" — avoids clashing with schedule/Art Production).
# No "done": finishing milestones is calendar/lane, not this switch.
LIFECYCLE_STATUSES: list[tuple[str, str]] = [
    ("planning", "Planning"),
    ("active", "Active"),
    ("scope_change", "Scope change"),
    ("shelved", "Shelved"),
    ("cancelled", "Cancelled"),
]


def normalize_lifecycle(status: str | None) -> str:
    """Map title.status → lifecycle key. Legacy planned/production/done still accepted."""
    s = (status or "planning").strip().lower().replace(" ", "_").replace("-", "_")
    if s in ("planned", "plan", "planning"):
        return "planning"
    if s in ("active", "production", "in_production", "prod"):
        return "active"
    if s in ("scope_change", "scope", "scopechange", "change"):
        return "scope_change"
    if s in ("shelved", "shelf", "on_hold", "hold"):
        return "shelved"
    if s in ("cancelled", "canceled", "kill"):
        return "cancelled"
    # old "done" → active (ship/milestones are schedule, not lifecycle)
    if s in ("done", "shipped", "complete", "released"):
        return "active"
    return "planning"


def lifecycle_label(key: str | None) -> str:
    k = normalize_lifecycle(key)
    for code, lab in LIFECYCLE_STATUSES:
        if code == k:
            return lab
    return "Planning"


def phase_status(phases: list[dict[str, Any]], today: date | None = None) -> str:
    today = today or date.today()
    if not phases:
        return "planned"
    rel = None
    for p in phases:
        if "global release" in (p.get("name") or "").lower():
            rel = parse_date(p.get("start") or p.get("end"))
            break
        if "betsoft release" in (p.get("name") or "").lower():
            rel = parse_date(p.get("start") or p.get("end"))
    if rel and today > rel:
        return "done"
    for p in phases:
        s = parse_date(p.get("start"))
        e = parse_date(p.get("end")) or s
        if s and e and s <= today <= e:
            return "active"
        if s and s == today:
            return "active"
    for p in phases:
        s = parse_date(p.get("start"))
        if s and s > today:
            return "planned"
    return "active"


def earliest_start(phases: list[dict[str, Any]]) -> date | None:
    best: date | None = None
    for p in phases or []:
        s = parse_date(p.get("start")) or parse_date(p.get("end"))
        if s and (best is None or s < best):
            best = s
    return best


def release_date_of(phases: list[dict[str, Any]], fallback: str | None = None) -> date | None:
    for p in phases or []:
        n = (p.get("name") or "").lower()
        if "global release" in n or "betsoft release" in n:
            d = parse_date(p.get("start") or p.get("end"))
            if d:
                return d
    return parse_date(fallback)


def quarter_key(release: date | None = None, quarter_label: str | None = None) -> str:
    """Stable key like 2027-Q1 for filters and multi-quarter boards."""
    if quarter_label:
        m = __import__("re").search(
            r"Q\s*([1-4])\s*[,/]?\s*(\d{4})", quarter_label, __import__("re").I
        )
        if m:
            return f"{m.group(2)}-Q{m.group(1)}"
        m2 = __import__("re").search(
            r"(\d{4})\s*[-/]?\s*Q\s*([1-4])", quarter_label, __import__("re").I
        )
        if m2:
            return f"{m2.group(1)}-Q{m2.group(2)}"
    if release:
        q = (release.month - 1) // 3 + 1
        return f"{release.year}-Q{q}"
    return "unassigned"


def quarter_label(key: str) -> str:
    if key == "unassigned" or not key:
        return "Unassigned"
    # 2027-Q1 → Q1 2027
    parts = key.split("-Q")
    if len(parts) == 2:
        return f"Q{parts[1]} {parts[0]}"
    return key


# Board columns = craft lanes + distinct late gates (NOT one mushy "Release window").
# Board / craft-lane column order. Base template bins (Pre-Production→Design,
# Production, Development→Dev) live here; classic DOS craft labels still map in.
PIPELINE_BUCKETS: list[str] = [
    "Not started",
    "Design",
    "Static Art",
    "Production",
    "FX",
    "Deliver Math",
    "Deliver Assets",
    "Dev",
    "Deliver Audio",
    "QA Loc",
    "QA LQA",
    "QA RQA",
    "Marketing / Sheets",
    "Ready for Rollout",
    "Active Rollout",
    "Exclusivity",
    "→ Global Release",
    "→ Betsoft Release",
    "Released",
    "Unscheduled",
    "No schedule",
    "In progress",
]


def events_for_board(
    phases: list[dict[str, Any]] | None,
    *,
    kind: str | None = None,
    product_line_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Which events count for board placement.
    - Nucleus / full title: ignore Betsoft Release (that's the rebrand twin's job).
    - Rebrand: ignore Global Release (nucleus already shipped under NG).
    """
    kind = (kind or "title").lower()
    out: list[dict[str, Any]] = []
    for p in phases or []:
        n = (p.get("name") or "").lower()
        if kind != "rebrand" and "betsoft release" in n:
            continue
        if kind == "rebrand" and "global release" in n:
            continue
        out.append(p)
    return out


def _lane_from_phase_name(low: str) -> str | None:
    """Map a phase/gate title to its craft lane. Order matters (more specific first)."""
    if not low or "unscheduled" in low:
        return "Unscheduled"
    # Base Template / Hands bins (Pre-Production · Production · Development · …)
    if "pre-production" in low or "preproduction" in low or "pre production" in low:
        return "Design"
    if "art production" in low or ("art" in low and "production" in low):
        return "Static Art"
    # Bare "Production" (not pre-, not art-only) — main Base Template mid bin.
    # Must run before generic "design"/dev so we don't drop titles off the board.
    if low.strip() == "production" or (
        "production" in low
        and "pre" not in low
        and "art" not in low
        and "post" not in low
    ):
        return "Production"
    if "polish" in low or ("localize" in low and "rqa" not in low and "lqa" not in low):
        return "QA Loc"
    if "development" in low and "pre" not in low:
        return "Dev"
    # Classic DOS / Greg labels
    if "design" in low:
        return "Design"
    if "static" in low:
        return "Static Art"
    if low.startswith("fx") or "fx phase" in low or low == "fx" or "fx/animation" in low:
        return "FX"
    if "deliver math" in low or "math/spec" in low or "math + specs" in low:
        return "Deliver Math"
    if "deliver assets" in low or "all assets" in low:
        return "Deliver Assets"
    if "dev phase" in low or low.strip() == "dev":
        return "Dev"
    if "deliver audio" in low or ("audio" in low and "dev" in low):
        return "Deliver Audio"
    if "localization" in low and "rqa" not in low:
        return "QA Loc"
    if "lqa" in low:
        return "QA LQA"
    if "rqa" in low:
        return "QA RQA"
    if any(
        x in low
        for x in ("product sheets", "marketing", "website demo", "sim stats", "demo")
    ):
        return "Marketing / Sheets"
    if "ready" in low and "rollout" in low:
        return "Ready for Rollout"
    if "active rollout" in low or low == "rollout":
        return "Active Rollout"
    if "exclusivity" in low or "test live" in low:
        return "Exclusivity"
    if "betsoft release" in low:
        return "→ Betsoft Release"
    if (
        "global release" in low
        or "official release" in low
        or "go-live" in low
        or "go live" in low
    ):
        return "→ Global Release"
    return None


def release_anchor(
    phases: list[dict[str, Any]],
    *,
    kind: str | None = None,
    fallback: str | None = None,
) -> date | None:
    """Ship date that means 'done' for this title kind."""
    kind = (kind or "title").lower()
    want = "betsoft release" if kind == "rebrand" else "global release"
    for p in phases or []:
        if want in (p.get("name") or "").lower():
            d = parse_date(p.get("start") or p.get("end"))
            if d:
                return d
    return parse_date(fallback)


def pipeline_bucket(
    phases: list[dict[str, Any]],
    *,
    today: date | None = None,
    release_fallback: str | None = None,
    kind: str | None = None,
    product_line_id: str | None = None,
) -> str:
    """
    Craft-lane for multi-quarter boards.
    Late pipeline is split: Rollout / Exclusivity / → Global / → Betsoft / Released.
    """
    today = today or date.today()
    board_ph = events_for_board(phases, kind=kind, product_line_id=product_line_id)
    if not board_ph and not phases:
        return "No schedule"

    rel = release_anchor(board_ph, kind=kind, fallback=release_fallback)
    if rel and today > rel:
        return "Released"

    start0 = earliest_start(board_ph)
    if start0 and start0 > today:
        return "Not started"

    name = current_phase_name(board_ph, today)
    raw = name[2:].strip() if name.startswith("→") else name
    low = raw.lower()

    if name.startswith("→") and start0 and start0 > today:
        return "Not started"

    # Upcoming arrow to a late gate → named hold lane (not one mushy window)
    if name.startswith("→"):
        if "betsoft" in low:
            return "→ Betsoft Release"
        if "global" in low:
            return "→ Global Release"
        if "exclusivity" in low or "test live" in low:
            return "Exclusivity"
        if "rollout" in low:
            return "Active Rollout"
        if "ready" in low:
            return "Ready for Rollout"

    lane = _lane_from_phase_name(low)
    if lane:
        # point-in-time global release day still "→ Global" until after
        if lane == "→ Global Release" and rel and today == rel:
            return "→ Global Release"
        if lane == "→ Betsoft Release" and rel and today == rel:
            return "→ Betsoft Release"
        return lane

    # Dated schedule with an unknown phase name → use that name.
    # "No schedule" = no useful dates. "Not started" = ship/dates exist but before first phase.
    if name and raw and raw not in ("—", "?", "none"):
        return raw[:48]
    if start0:
        return "Not started" if start0 > today else "In progress"
    if rel:
        return "Not started" if today < rel else "Released"
    return "No schedule"


# --- Mid-schedule edits: release is immovable; make room only by going earlier ---


def _event_anchor_date(ev: dict[str, Any]) -> date | None:
    """Sort / compare key for cascade — prefer start, then end."""
    return parse_date(ev.get("start")) or parse_date(ev.get("end"))


def _event_sort_tuple(ev: dict[str, Any]) -> tuple:
    d = _event_anchor_date(ev) or date.min
    return (int(ev.get("sort") or 0), d.isoformat(), str(ev.get("id") or ""))


def _shift_iso(s: str | None, delta: timedelta) -> str | None:
    d = parse_date(s)
    if not d:
        return s
    return fmt_date(d + delta)


def _is_release_named(name: str | None) -> bool:
    low = (name or "").lower()
    return (
        "global release" in low
        or "betsoft release" in low
        or "official release" in low
    )


def shift_event_dates(
    ev: dict[str, Any],
    delta: timedelta,
    *,
    reason: str,
    record: bool = True,
) -> bool:
    """
    Move one event's start/end (and nested workstreams) by delta.
    Returns True if any date changed. Locks the line when recording.
    """
    if delta.days == 0:
        return False
    from spine import record_edit

    old_s, old_e = ev.get("start"), ev.get("end")
    new_s = _shift_iso(old_s, delta)
    new_e = _shift_iso(old_e, delta)
    if new_s == old_s and new_e == old_e:
        # still may need workstreams
        changed = False
    else:
        before = {
            "name": ev.get("name"),
            "start": old_s,
            "end": old_e,
            "role": ev.get("role"),
        }
        after = {
            "name": ev.get("name"),
            "start": new_s,
            "end": new_e,
            "role": ev.get("role"),
        }
        ev["start"] = new_s
        ev["end"] = new_e
        ev["placeholder"] = not bool(new_s or new_e)
        if record:
            record_edit(ev, reason=reason, before=before, after=after)
            ev["notes"] = reason
        changed = True

    for ws in ev.get("workstreams") or []:
        if not isinstance(ws, dict):
            continue
        ws_old_s, ws_old_e = ws.get("start"), ws.get("end")
        ws_new_s = _shift_iso(ws_old_s, delta)
        ws_new_e = _shift_iso(ws_old_e, delta)
        if ws_new_s == ws_old_s and ws_new_e == ws_old_e:
            continue
        ws_before = {
            "name": ws.get("name"),
            "start": ws_old_s,
            "end": ws_old_e,
            "role": "workstream",
        }
        ws_after = {
            "name": ws.get("name"),
            "start": ws_new_s,
            "end": ws_new_e,
            "role": "workstream",
        }
        ws["start"] = ws_new_s
        ws["end"] = ws_new_e
        ws["fill_parent"] = False
        if record:
            record_edit(ws, reason=reason, before=ws_before, after=ws_after)
            ws["notes"] = reason
        changed = True
    return changed


def plan_backward_make_room(
    old_start: str | None,
    old_end: str | None,
    new_start: str | None,
    new_end: str | None,
) -> dict[str, Any]:
    """
    Release is immovable. Extra time mid-spine is made by going earlier only.

    Returns:
      pivot_start, pivot_end — dates to apply on the edited line
      cascade_days — negative = shift earlier phases earlier; 0 = no cascade
      note — short operator message
    """
    os = parse_date(old_start)
    oe = parse_date(old_end) or os
    ns = parse_date(new_start)
    ne = parse_date(new_end) or ns

    out: dict[str, Any] = {
        "pivot_start": new_start,
        "pivot_end": new_end or new_start,
        "cascade_days": 0,
        "note": "",
    }
    if not os or not ns:
        # no old/new start → just accept typed dates, no cascade
        return out

    start_delta = (ns - os).days

    # Primary: operator moved Start earlier → cascade that many days back.
    if start_delta < 0:
        out["cascade_days"] = start_delta
        out["note"] = (
            f"start {start_delta}d (earlier) · earlier lines shift with it · ship stays"
        )
        return out

    # Start moved later = unusual under reverse-from-ship; no auto-push of later work.
    if start_delta > 0:
        out["note"] = (
            "start moved later · no cascade (we only auto-shift earlier; ship immovable)"
        )
        return out

    # Start unchanged: if End moved later, that would steal time toward ship.
    # Convert to grow-backward: keep End at old handoff, pull Start earlier by growth.
    if oe and ne and ne > oe:
        growth = (ne - oe).days
        new_s = os - timedelta(days=growth)
        out["pivot_start"] = fmt_date(new_s)
        out["pivot_end"] = fmt_date(oe)  # handoff / toward-release end stays
        out["cascade_days"] = -growth
        out["note"] = (
            f"end was +{growth}d toward ship → converted to start −{growth}d "
            f"(handoff end held) · earlier lines −{growth}d · ship stays"
        )
        return out

    # Start unchanged, end earlier (shrink): no cascade forward into freed space.
    if oe and ne and ne < oe:
        out["note"] = "window shortened · earlier lines left alone (no forward fill)"
        return out

    out["note"] = "dates saved · no cascade needed"
    return out


def cascade_earlier_phases(
    phases: list[dict[str, Any]],
    pivot_id: str,
    cascade_days: int,
    *,
    reason: str,
    pivot_sort: int | None = None,
) -> int:
    """
    Shift every event strictly before the pivot by cascade_days (usually negative).
    Never moves the pivot itself, never moves release-named events, never later lines.
    "Before" = lower spine sort than the pivot (release-from-ship order).
    Returns count of top-level events shifted.
    """
    if not cascade_days:
        return 0
    pivot = next((p for p in phases if (p.get("id") or "") == pivot_id), None)
    if not pivot:
        return 0

    piv_sort = (
        int(pivot_sort)
        if pivot_sort is not None
        else int(pivot.get("sort") or 0)
    )
    delta = timedelta(days=cascade_days)
    tag = (
        f"cascade earlier {cascade_days}d from “{pivot.get('name') or pivot_id}”: "
        f"{reason}"
    )
    n = 0
    for p in phases:
        if (p.get("id") or "") == pivot_id:
            continue
        if _is_release_named(p.get("name")):
            continue
        if int(p.get("sort") or 0) >= piv_sort:
            continue
        if shift_event_dates(p, delta, reason=tag, record=True):
            n += 1
    return n
