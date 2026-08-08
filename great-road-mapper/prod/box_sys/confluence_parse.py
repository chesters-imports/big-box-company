"""Parse Confluence scheduling PDF text dumps into GRM titles + phases."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)
# Date forms: May 18, 2026 | May 18 2026 | May 18 | Oct 26 (Monday) | July 16, 2026
DATE_CORE = rf"{MONTH}\.?\s+\d{{1,2}}(?:,?\s+\d{{4}})?"
DATE_TOKEN = rf"{DATE_CORE}(?:\s*\([^)]*\))?"

TITLE_RE = re.compile(
    r"^(?P<code>(?:BSG|NG)\s*Q\dG\d[_\s]*\d{4}|NG\s*Q\dG\d[_\s]*\d{4})"
    r"\s*(?P<rest>.+)$",
    re.I,
)
# Compact codes already like BSG Q4G1_2026
TITLE_RE2 = re.compile(
    r"^(?P<code>(?:BSG|NG)\s*Q\dG\d_\d{4})\s+(?P<rest>.+)$",
    re.I,
)
TITLE_RE3 = re.compile(
    r"^(?P<code>NGQ\dG\d_\d{4}|BSG\s*Q\dG\d_\d{4})\s*:?\s*(?P<rest>.+)$",
    re.I,
)

DIFF_RE = re.compile(
    r"(?:DIFFICULTY|\.\s*-\s*6)\s*=\s*(?P<d>COMPLEX\+?|MEDIUM|SIMPLE)",
    re.I,
)

# Line with date(s) and label after colon
PHASE_RE = re.compile(
    rf"^(?P<a>{DATE_TOKEN})\s*[-–—]\s*(?P<b>{DATE_TOKEN})\s*:\s*(?P<label>.+)$",
    re.I,
)
PHASE_POINT_RE = re.compile(
    rf"^(?P<a>{DATE_TOKEN})\s*:\s*(?P<label>.+)$",
    re.I,
)
# Short ranges without year on second: March 1 - 15, 2027
PHASE_SHORT_RE = re.compile(
    rf"^(?P<a>{DATE_TOKEN})\s*[-–—]\s*(?P<b>\d{{1,2}}(?:,?\s+\d{{4}})?)\s*:\s*(?P<label>.+)$",
    re.I,
)

BSG_VER_RE = re.compile(
    r"^BSG\s+Version(?:\s+Specific)?\s*:\s*(?P<name>.+)$",
    re.I,
)

BETSOFT_REL_RE = re.compile(
    r"Betsoft\s+Release",
    re.I,
)

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _parse_one_date(s: str, default_year: int | None = None) -> date | None:
    s = (s or "").strip()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    m = re.match(
        rf"^{MONTH}\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?$",
        s,
        re.I,
    )
    if not m:
        return None
    mon_s = re.match(rf"^({MONTH})", s, re.I)
    if not mon_s:
        return None
    mon = MONTH_MAP.get(mon_s.group(1).lower().rstrip("."))
    day = int(m.group(1))
    year = int(m.group(2)) if m.group(2) else default_year
    if not mon or not year:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def _fmt(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _clean_label(label: str) -> str:
    label = label.strip()
    label = re.sub(r"\s*←.*$", "", label)
    label = re.sub(r"\s*\([^)]*\bweeks?\b[^)]*\)", "", label, flags=re.I)
    label = re.sub(r"\s+", " ", label).strip(" .")
    # shorten very long
    if len(label) > 80:
        label = label[:77] + "…"
    return label or "Phase"


def _norm_code(raw: str) -> str:
    s = re.sub(r"\s+", "", raw.upper())
    s = s.replace("NGQ", "NG-Q").replace("BSGQ", "BSG-Q")
    if s.startswith("NGQ"):
        s = "NG-" + s[2:]
    # NGQ3G1_2026 already handled
    if re.match(r"^NGQ\d", s):
        s = "NG-" + s[2:]
    s = s.replace("_", "-")
    # BSG-Q3G1-2026
    m = re.match(r"^(BSG|NG)-?Q(\d)G(\d)-?(\d{4})$", s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}G{m.group(3)}-{m.group(4)}"
    m = re.match(r"^(BSG|NG)Q(\d)G(\d)-?(\d{4})$", s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}G{m.group(3)}-{m.group(4)}"
    return s


def _complexity(diff: str) -> str:
    d = (diff or "MEDIUM").upper()
    if "CLONE" in d:
        return "math_clone"
    if "COMPLEX" in d:
        return "complex"
    return "medium"


def _split_name_math(rest: str) -> tuple[str, str]:
    rest = rest.strip()
    rest = re.sub(r"\(GAME\s*ID\s*:\s*#+\)", "", rest, flags=re.I).strip()
    m = re.search(r"\[([^\]]+)\]", rest)
    math = m.group(1).strip() if m else ""
    name = re.sub(r"\[[^\]]*\]", "", rest).strip(" -:")
    name = re.sub(r"\s+", " ", name)
    return name or "Untitled", math


def _slice_for_code(text: str, code_raw: str) -> str:
    """Text from this title header until the next BSG/NG title header."""
    # normalize search patterns for this code
    variants = {
        code_raw,
        code_raw.replace("-", " "),
        code_raw.replace("-", "_"),
        code_raw.replace("BSG-", "BSG ").replace("NG-", "NG"),
        code_raw.replace("BSG-", "BSG ").replace("NG-", "NGQ").replace("Q", "Q")
        if code_raw.startswith("NG")
        else code_raw,
    }
    # NG-Q3G1-2026 → NGQ3G1_2026
    m = re.match(r"^(BSG|NG)-Q(\d)G(\d)-(\d{4})$", code_raw)
    if m:
        variants.add(f"{m.group(1)} Q{m.group(2)}G{m.group(3)}_{m.group(4)}")
        variants.add(f"{m.group(1)}Q{m.group(2)}G{m.group(3)}_{m.group(4)}")
        if m.group(1) == "NG":
            variants.add(f"NGQ{m.group(2)}G{m.group(3)}_{m.group(4)}")
    idx = -1
    used = ""
    for v in variants:
        j = text.find(v)
        if j >= 0 and (idx < 0 or j < idx):
            idx = j
            used = v
    if idx < 0:
        return ""
    rest = text[idx + len(used) :]
    # next title
    nxt = re.search(
        r"\n(?:BSG|NG)\s*Q\dG\d[_\s]*\d{4}|\nNGQ\dG\d_\d{4}",
        rest,
    )
    if nxt:
        rest = rest[: nxt.start()]
    return rest


def _phases_from_block(
    block: str, ctx_year: int | None
) -> tuple[list[dict[str, Any]], str, str]:
    phases: list[dict[str, Any]] = []
    release = ""
    bsg_rel = ""
    for raw in block.split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        pln = re.sub(r":\s*-\s*", " - ", ln)
        pm = PHASE_RE.match(pln) or PHASE_SHORT_RE.match(pln) or PHASE_POINT_RE.match(pln)
        if not pm:
            continue
        gd = pm.groupdict()
        a = _parse_one_date(gd["a"], ctx_year)
        b = None
        if gd.get("b"):
            b_raw = gd["b"]
            if re.match(r"^\d{1,2}", b_raw.strip()) and a:
                dm2 = re.match(r"^(\d{1,2})(?:,?\s+(\d{4}))?", b_raw.strip())
                if dm2:
                    yr = int(dm2.group(2)) if dm2.group(2) else a.year
                    try:
                        b = date(yr, a.month, int(dm2.group(1)))
                    except ValueError:
                        b = None
            else:
                b = _parse_one_date(b_raw, a.year if a else ctx_year)
        label = _clean_label(gd["label"])
        if label.lower().startswith("note"):
            continue
        kind = "point" if b is None or (a and b and a == b) else "range"
        if kind == "range" and a and b and a > b:
            a, b = b, a
        start = _fmt(a)
        end = _fmt(b if kind == "range" else a)
        if not start:
            continue
        phases.append(
            {
                "id": f"ph-{len(phases):02d}",
                "name": label,
                "kind": kind,
                "start": start,
                "end": end or start,
                "locked": True,
                "notes": "",
                "sort": len(phases),
            }
        )
        if re.search(r"global\s+release", label, re.I):
            release = start or ""
        if BETSOFT_REL_RE.search(label):
            bsg_rel = start or ""
    return phases, release, bsg_rel


def parse_schedule_text(text: str, default_quarter: str) -> list[dict[str, Any]]:
    """
    Return list of title dicts with phases from a full PDF text dump.
    Uses per-code text slices so PDF reading order (phases before title) still works.
    """
    text = text.replace("\r", "")
    default_year = None
    m_q = re.search(r"Q([1-4])\s+(\d{4})", default_quarter)
    if m_q:
        default_year = int(m_q.group(2))

    # find all title headers
    header_re = re.compile(
        r"(?P<code>(?:BSG|NG)\s*Q\dG\d[_\s]*\d{4}|NGQ\dG\d_\d{4})\s*:?\s*(?P<rest>[^\n]+)",
        re.I,
    )
    headers: list[tuple[str, str, str]] = []  # code, rest, raw_code
    for m in header_re.finditer(text):
        raw_c = m.group("code")
        if "VERSION" in m.group(0).upper():
            continue
        code = _norm_code(raw_c)
        rest = m.group("rest")
        if "CONFLUENCE" in rest.upper() and len(rest) < 20:
            continue
        headers.append((code, rest, raw_c))

    # dedupe codes keep first
    seen: set[str] = set()
    titles: list[dict[str, Any]] = []
    for code, rest, raw_c in headers:
        if code in seen:
            continue
        seen.add(code)
        name, math = _split_name_math(rest)
        name = re.sub(r"\(GAME\s*ID.*?\)", "", name, flags=re.I).strip(" -")
        block = _slice_for_code(text, code)
        # also try with raw form
        if len(block) < 40:
            block = _slice_for_code(text, raw_c.replace(" ", ""))
        phases, release, bsg_rel = _phases_from_block(block, default_year)
        # DIFFICULTY in block
        cx = "medium"
        dm = DIFF_RE.search(block)
        if dm:
            cx = _complexity(dm.group("d"))
        elif re.search(r"COMPLEX\+", block[:800], re.I):
            cx = "complex"
        elif re.search(r"COMPLEX", block[:800], re.I):
            cx = "complex"
        elif re.search(r"MEDIUM", block[:800], re.I):
            cx = "medium"
        if re.search(r"Math Clone|Math and Specs to Devs\s*Not Required", block, re.I):
            cx = "math_clone"
        bsg_twin = ""
        bm = BSG_VER_RE.search(block)
        if bm:
            bsg_twin = bm.group("name").strip()
            bsg_twin = re.sub(r"\(GAME.*", "", bsg_twin, flags=re.I).strip()
        # Betsoft release date lines
        for mbr in re.finditer(
            rf"({DATE_TOKEN})\s*:\s*[^\n]*Betsoft\s+Release",
            block,
            re.I,
        ):
            d = _parse_one_date(mbr.group(1), default_year)
            if d:
                bsg_rel = d.isoformat()
        if not release:
            # last Global Release in block
            for p in phases:
                if "global release" in p["name"].lower():
                    release = p["start"]
        line_id = "line-ng" if code.startswith("NG") else "line-bsg"
        t: dict[str, Any] = {
            "code": code,
            "name": name or code,
            "math_model": math,
            "product_line_id": line_id,
            "quarter": default_quarter,
            "complexity": cx,
            "kind": "title",
            "status": "active",
            "theme": "",
            "notes": f"Imported from Confluence {default_quarter}",
            "phases": phases,
            "twin_code": "",
            "rebrand_of": "",
            "nucleus_code": "",
            "release_date": release or "",
            "bsg_twin": bsg_twin,
            "bsg_release_date": bsg_rel or "",
        }
        titles.append(t)

    extras: list[dict[str, Any]] = []
    for t in titles:
        bname = (t.get("bsg_twin") or "").strip()
        brel = (t.get("bsg_release_date") or "").strip()
        if not bname or not t["code"].startswith("NG"):
            continue
        if "to be decided" in bname.lower() or bname.lower() in ("name tbd", "tbd"):
            bname = f"BSG rebrand of {t['code']}"
        if not brel:
            continue
        re_code = f"BSG-RE-{t['code']}"
        t["twin_code"] = re_code
        extras.append(
            {
                "code": re_code,
                "name": re.sub(r"\(GAME.*", "", bname, flags=re.I).strip(),
                "math_model": t.get("math_model") or "",
                "product_line_id": "line-bsg",
                "quarter": t.get("quarter"),
                "complexity": "medium",
                "kind": "rebrand",
                "status": "active",
                "theme": f"Rebrand of {t['code']}",
                "notes": f"BSG rebrand of {t['code']} · logo swap",
                "phases": [
                    {
                        "id": "ph-00",
                        "name": "Betsoft Release",
                        "kind": "point",
                        "start": brel,
                        "end": brel,
                        "locked": True,
                        "notes": "Same game, new logo",
                        "sort": 0,
                    }
                ],
                "twin_code": t["code"],
                "rebrand_of": t["code"],
                "nucleus_code": t["code"],
                "release_date": brel,
            }
        )

    out = []
    for t in titles + extras:
        if not t.get("phases") and not t.get("release_date"):
            continue
        # clean name
        t["name"] = re.sub(r"\s+", " ", t.get("name") or "").strip()
        out.append(t)
    return out
