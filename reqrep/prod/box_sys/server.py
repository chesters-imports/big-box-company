#!/usr/bin/env python3
"""ReqRep — Big Box request bay · CO.BBC-002-RR · port 42962"""

from __future__ import annotations

import json
import re
import secrets
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BOX_SYS = Path(__file__).resolve().parent
PROD = BOX_SYS.parent
SAFE_BOX = PROD / "safe_box"
STORE = SAFE_BOX / "cases.json"
AGENT_INBOX = SAFE_BOX / "agent_inbox.json"
HOST = "127.0.0.1"
PORT = 42962


def ensure_dirs() -> None:
    SAFE_BOX.mkdir(parents=True, exist_ok=True)


def now() -> int:
    return int(time.time())


def new_id(prefix: str = "c") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def empty_store() -> dict[str, Any]:
    return {
        "version": 1,
        "product": "reqrep",
        "chip": "CO.BBC-002-RR",
        "seq": 0,
        "cases": [],
        "updated": now(),
    }


# Filing kinds — not free text (add more when house needs them)
REQ_TYPES = (
    "REQ",  # new product / new SKU ask
    "MOD",  # modification to an existing SKU
    "ADDENDUM",  # addendum on an existing ticket/SKU
    "BUG",  # Frog King taxes / bug report (not bubble wrap)
)

# Work-order lane on a block (ticket inside a case) · B08
WORK_LANES = (
    "discussion",  # talk / design (active this cycle) — agent should reply
    "paused",  # held / not debating now — no agent implement or reply
    "run",  # agent may implement / ship
    "test",  # waiting Hands QA — not agent freestyle
    "closed",  # work done for agent (IDA28; was IN) — not implement
)
# Legacy chip → migrate on normalize
_LANE_ALIASES = {
    "run_test": "run",
    "run/test": "run",
    "in": "closed",  # IDA28: IN → CLOSED
}

# Ticket kind inside a case · B10
TICKET_KINDS = (
    "IDA",  # ideas, discussions, additions
    "BUG",  # bugs
    "CHG",  # major change, not a bug
)


def normalize_chunk(ch: dict[str, Any]) -> None:
    lane = (ch.get("work_lane") or "discussion").strip().lower().replace(" ", "_")
    lane = _LANE_ALIASES.get(lane, lane)
    if lane not in WORK_LANES:
        lane = "discussion"
    ch["work_lane"] = lane
    kind = (ch.get("ticket_kind") or "").strip().upper()
    body_u = (ch.get("body") or "").upper()
    if kind not in TICKET_KINDS:
        # legacy / unset: guess once from body, then stick
        if body_u.lstrip().startswith("BUG") or body_u.startswith("BUG:") or "\nBUG:" in body_u[:30]:
            kind = "BUG"
        elif (
            "DISCUSS CHANGE" in body_u[:80]
            or body_u.lstrip().startswith("REQUEST:")
            or body_u.lstrip().startswith("CHANGE")
            or "MAJOR CHANGE" in body_u[:80]
        ):
            kind = "CHG"
        else:
            kind = "IDA"
        ch["ticket_kind"] = kind
    else:
        ch["ticket_kind"] = kind
    # If still default IDA but body clearly marks BUG/CHG (Hands typed BUG: first)
    if ch["ticket_kind"] == "IDA":
        if body_u.lstrip().startswith("BUG"):
            ch["ticket_kind"] = "BUG"
        elif body_u.lstrip().startswith("REQUEST:") or "DISCUSS CHANGE" in body_u[:80]:
            ch["ticket_kind"] = "CHG"


def compose_title(case: dict[str, Any]) -> str:
    """Display line only — derived from type + SKU + product name (Hands' shape)."""
    kind = (case.get("req_type") or "REQ").strip().upper() or "REQ"
    sku = (case.get("sku") or "").strip()
    name = (case.get("product_name") or "").strip()
    if sku and name:
        return f'{kind}: ROM SKU {sku} "{name}"'
    if sku:
        return f"{kind}: ROM SKU {sku}"
    if name:
        return f'{kind}: "{name}"'
    return kind


def parse_title_into_parts(title: str) -> dict[str, str]:
    """Best-effort migrate freeform titles like: REQ: ROM SKU CO.BBC-002-RR \"ReqRep\""""
    t = (title or "").strip()
    out: dict[str, str] = {}
    m = re.match(
        r'^(REQ|MOD|ADDENDUM|BUG)\s*:\s*(?:ROM\s+SKU\s+)?([^\s"]+)?\s*(?:"([^"]*)")?\s*$',
        t,
        re.I,
    )
    if m:
        out["req_type"] = m.group(1).upper()
        if m.group(2):
            out["sku"] = m.group(2).strip()
        if m.group(3):
            out["product_name"] = m.group(3).strip()
        return out
    m2 = re.match(r'^(REQ|MOD|ADDENDUM|BUG)\s*:\s*"([^"]+)"\s*$', t, re.I)
    if m2:
        out["req_type"] = m2.group(1).upper()
        out["product_name"] = m2.group(2).strip()
    return out


def normalize_case(case: dict[str, Any]) -> None:
    """Intake: type · sku · product_name · producer · hands · priority. Title is composed."""
    if not (case.get("hands") or "").strip():
        case["hands"] = (case.get("employee") or "").strip()
    case.pop("employee", None)
    case.pop("client", None)
    if "producer" not in case:
        case["producer"] = ""
    if "hands" not in case:
        case["hands"] = ""
    if "priority" not in case:
        case["priority"] = "Normal"

    # Migrate old free title → parts when parts empty
    has_parts = any(
        (case.get(k) or "").strip() for k in ("req_type", "sku", "product_name")
    )
    if not has_parts and (case.get("title") or "").strip():
        parts = parse_title_into_parts(str(case.get("title") or ""))
        for k, v in parts.items():
            if v and not (case.get(k) or "").strip():
                case[k] = v
        # leftover free title as product name only if still empty
        if not (case.get("product_name") or "").strip() and not parts:
            case["product_name"] = str(case.get("title") or "").strip()

    kind = (case.get("req_type") or "REQ").strip().upper() or "REQ"
    if kind not in REQ_TYPES:
        kind = "REQ"
    case["req_type"] = kind
    if "sku" not in case:
        case["sku"] = ""
    if "product_name" not in case:
        case["product_name"] = ""
    case["title"] = compose_title(case)


def seed_demo(store: dict[str, Any]) -> None:
    """One sample case so the desk isn't empty on first open — in-world product request."""
    if store.get("cases"):
        return
    store["seq"] = 1
    t = now()
    store["cases"].append(
        {
            "id": "case_demo01",
            "req_code": "REQ-001",
            "req_type": "REQ",
            "sku": "CO.BBC-002-RR",
            "product_name": "ReqRep",
            "title": 'REQ: ROM SKU CO.BBC-002-RR "ReqRep"',
            "producer": "Big Box Company",
            "hands": "Daniel Wake",
            "priority": "High",
            "status": "discussing",
            "created": t,
            "updated": t,
            "chunks": [
                {
                    "id": "chk_a1",
                    "ref": "B01",
                    "body": "Big Box needs a desk where product requests are discussed in numbered blocks, with Hands sealing each block when agreed.",
                    "closed": False,
                    "closed_at": None,
                    "closed_by": None,
                    "close_note": "",
                    "comments": [
                        {
                            "id": "cm_1",
                            "author": "agent",
                            "text": "Recommend: open threads on each block, AGREED seal, then a separate Product prep sheet for build.",
                            "created": t,
                        },
                        {
                            "id": "cm_2",
                            "author": "hands",
                            "text": "Yes. Match the loreBOX planner rhythm — close the fight, then freeze.",
                            "created": t + 1,
                        },
                    ],
                },
                {
                    "id": "chk_a2",
                    "ref": "B02",
                    "body": "Intake shows which producer house filed the work and which Hands face is wearing the request — not a second copy of the same person under two labels.",
                    "closed": True,
                    "closed_at": t + 10,
                    "closed_by": "hands",
                    "close_note": "AGREED",
                    "comments": [
                        {
                            "id": "cm_3",
                            "author": "hands",
                            "text": "Producer = ROM house. Hands = face on the filing. Priority as usual.",
                            "created": t + 2,
                        }
                    ],
                },
                {
                    "id": "chk_a3",
                    "ref": "B03",
                    "body": "After scope is locked, wire rewrites a clean Product prep for the agent. Hands signs before any first slice starts.",
                    "closed": False,
                    "closed_at": None,
                    "closed_by": None,
                    "close_note": "",
                    "comments": [],
                },
            ],
            "scope": {
                "body": "Ship a request list and case desk: discussion blocks with refs, Hands AGREED seals, scope lock, Product prep generate and Hands sign-off. Big Box look, local store, Deck Host launch.",
                "locked": False,
                "locked_at": None,
            },
            "prep": {
                "body": "",
                "signed": False,
                "signed_at": None,
                "signed_by": None,
            },
        }
    )


def load_store() -> dict[str, Any]:
    ensure_dirs()
    if not STORE.is_file():
        store = empty_store()
        seed_demo(store)
        save_store(store)
        return store
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = empty_store()
        seed_demo(data)
        save_store(data)
    if not data.get("cases"):
        seed_demo(data)
        save_store(data)
    return data


def build_agent_inbox(store: dict[str, Any]) -> dict[str, Any]:
    """Agent desk bag: open tickets by lane. File + /api/agent-inbox.
    action_now = RUN + IN. awaiting_qa = TEST. later = DISCUSSION + PAUSED.
    """
    lanes = {L: [] for L in WORK_LANES}
    counts = {L: 0 for L in WORK_LANES}
    sealed_n = 0  # HAND STAMP completed (for home CLOSED satisfaction · IDA28)
    for case in store.get("cases") or []:
        normalize_case(case)
        ensure_chunk_refs(case)
        for ch in case.get("chunks") or []:
            normalize_chunk(ch)
            if ch.get("closed"):
                sealed_n += 1
                continue
            lane = ch.get("work_lane") or "discussion"
            if lane not in lanes:
                lane = "discussion"
            body = (ch.get("body") or "").strip().replace("\r\n", "\n")
            peek = body.split("\n", 1)[0][:140]
            row = {
                "ref": ch.get("ref"),
                "chunk_id": ch.get("id"),
                "case_id": case.get("id"),
                "req_code": case.get("req_code"),
                "case_title": case.get("title") or compose_title(case),
                "sku": case.get("sku"),
                "product_name": case.get("product_name"),
                "priority": case.get("priority") or "Normal",
                "ticket_kind": ch.get("ticket_kind") or "IDA",
                "work_lane": lane,
                "peek": peek,
                "comment_count": len(ch.get("comments") or []),
                "case_updated": case.get("updated"),
            }
            lanes[lane].append(row)
            counts[lane] = counts.get(lane, 0) + 1
    pri_rank = {"Urgent": 0, "High": 1, "Normal": 2, "Low": 3}

    def sort_key(r: dict[str, Any]) -> tuple:
        return (
            pri_rank.get(str(r.get("priority") or "Normal"), 9),
            -(int(r.get("case_updated") or 0)),
            str(r.get("ref") or ""),
        )

    for L in lanes:
        lanes[L].sort(key=sort_key)
    action_now = list(lanes.get("run") or [])
    action_now.sort(key=sort_key)
    awaiting_qa = list(lanes.get("test") or [])
    awaiting_qa.sort(key=sort_key)
    # DISCUSSION = actively discussing — agent should reply (not implement)
    # PAUSED = hold — no implement, no discussion reply required
    later = list(lanes.get("paused") or []) + list(lanes.get("closed") or [])
    later.sort(key=sort_key)
    discussing = list(lanes.get("discussion") or [])
    discussing.sort(key=sort_key)
    return {
        "schema": "reqrep.agent_inbox.v1",
        "product": "reqrep",
        "chip": "CO.BBC-002-RR",
        "updated": now(),
        "store_updated": store.get("updated"),
        "counts": counts,
        "open_total": sum(counts.values()),
        "sealed_total": sealed_n,
        "closed_display": sealed_n + counts.get("closed", 0),  # home pot: stamped + open CLOSED
        "action_now": action_now,
        "awaiting_qa": awaiting_qa,
        "discussing": discussing,
        "later": later,
        "by_lane": lanes,
        "law": {
            "implement": ["run"],
            "hands_qa": ["test"],
            "discuss_reply": ["discussion"],
            "hold": ["paused", "closed"],
            "note": (
                "RUN = agent implement. DISCUSSION = actively discuss (agent reply). "
                "PAUSED = no reply required. TEST = Hands QA. CLOSED = done for agent (was IN). "
                "After ship, agent moves RUN → TEST."
            ),
            "ownership": {
                "agent": ["run"],
                "hands_qa": ["test"],
                "shared_discuss": ["discussion"],
                "hold": ["paused", "closed"],
            },
        },
    }


def write_agent_inbox(store: dict[str, Any]) -> dict[str, Any]:
    inbox = build_agent_inbox(store)
    ensure_dirs()
    tmp = AGENT_INBOX.with_suffix(".tmp")
    tmp.write_text(json.dumps(inbox, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(AGENT_INBOX)
    return inbox


def save_store(store: dict[str, Any]) -> None:
    ensure_dirs()
    store["updated"] = now()
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STORE)
    try:
        write_agent_inbox(store)
    except OSError:
        pass


def find_case(store: dict[str, Any], case_id: str) -> dict[str, Any] | None:
    for c in store.get("cases") or []:
        if c.get("id") == case_id:
            normalize_case(c)
            return c
    return None


def next_req_code(store: dict[str, Any]) -> str:
    store["seq"] = int(store.get("seq") or 0) + 1
    return f"REQ-{store['seq']:03d}"


def next_ticket_seq(case: dict[str, Any]) -> int:
    """Monotonic ticket number within the case (01, 02…)."""
    best = 0
    for ch in case.get("chunks") or []:
        try:
            best = max(best, int(ch.get("ticket_seq") or 0))
        except (TypeError, ValueError):
            pass
        # legacy B12
        r = (ch.get("ref") or "").strip().upper()
        m = re.match(r"^B(\d+)$", r)
        if m:
            best = max(best, int(m.group(1)))
        m2 = re.search(r"-(?:IDA|BUG|CHG)(\d+)$", r, re.I)
        if m2:
            best = max(best, int(m2.group(1)))
    return best + 1


def format_ticket_ref(case: dict[str, Any], kind: str, seq: int) -> str:
    """REQ-001-BUG06 shape (Hands B10)."""
    code = (case.get("req_code") or "REQ-000").strip()
    k = (kind or "IDA").upper()
    if k not in TICKET_KINDS:
        k = "IDA"
    return f"{code}-{k}{int(seq):02d}"


def next_block_ref(case: dict[str, Any], kind: str = "IDA") -> str:
    seq = next_ticket_seq(case)
    return format_ticket_ref(case, kind, seq)


def ensure_chunk_refs(case: dict[str, Any]) -> None:
    """Normalize kinds/lanes; refs = REQ-###-KIND## by list order (unique)."""
    for i, ch in enumerate(case.get("chunks") or [], start=1):
        normalize_chunk(ch)
        ch["ticket_seq"] = i
        ch["ref"] = format_ticket_ref(case, ch.get("ticket_kind") or "IDA", i)


def json_bytes(obj: Any, code: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return code, body, "application/json; charset=utf-8"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BOX_SYS), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[reqrep] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            code, body, ctype = json_bytes(
                {"ok": True, "product": "reqrep", "chip": "CO.BBC-002-RR", "port": PORT}
            )
            self._send(code, body, ctype)
            return
        if path == "/api/agent-inbox":
            store = load_store()
            inbox = write_agent_inbox(store)
            code, body, ctype = json_bytes(inbox)
            self._send(code, body, ctype)
            return
        if path == "/api/cases":
            store = load_store()
            slim = []
            for c in store.get("cases") or []:
                normalize_case(c)
                slim.append(
                    {
                        "id": c.get("id"),
                        "req_code": c.get("req_code"),
                        "req_type": c.get("req_type"),
                        "sku": c.get("sku"),
                        "product_name": c.get("product_name"),
                        "title": c.get("title"),
                        "producer": c.get("producer"),
                        "hands": c.get("hands"),
                        "priority": c.get("priority"),
                        "status": c.get("status"),
                        "updated": c.get("updated"),
                        "created": c.get("created"),
                        "chunk_count": len(c.get("chunks") or []),
                        "open_chunks": sum(
                            1 for ch in (c.get("chunks") or []) if not ch.get("closed")
                        ),
                        "open_active": sum(
                            1
                            for ch in (c.get("chunks") or [])
                            if not ch.get("closed")
                            and (ch.get("work_lane") or "discussion")
                            not in ("paused", "closed", "in")
                        ),
                        "open_paused": sum(
                            1
                            for ch in (c.get("chunks") or [])
                            if not ch.get("closed")
                            and (ch.get("work_lane") or "")
                            in ("paused", "closed", "in")
                        ),
                        "scope_locked": bool((c.get("scope") or {}).get("locked")),
                        "prep_signed": bool((c.get("prep") or {}).get("signed")),
                    }
                )
            inbox = build_agent_inbox(store)
            code, body, ctype = json_bytes(
                {
                    "cases": slim,
                    "inbox": {
                        "counts": inbox.get("counts"),
                        "open_total": inbox.get("open_total"),
                        "sealed_total": inbox.get("sealed_total"),
                        "closed_display": inbox.get("closed_display"),
                        "action_now_n": len(inbox.get("action_now") or []),
                        "awaiting_qa_n": len(inbox.get("awaiting_qa") or []),
                        "later_n": len(inbox.get("later") or []),
                    },
                }
            )
            self._send(code, body, ctype)
            return
        m = re.fullmatch(r"/api/cases/([^/]+)", path)
        if m:
            store = load_store()
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            before = json.dumps([(ch.get("id"), ch.get("ref")) for ch in (case.get("chunks") or [])])
            ensure_chunk_refs(case)
            after = json.dumps([(ch.get("id"), ch.get("ref")) for ch in (case.get("chunks") or [])])
            if before != after:
                save_store(store)
            code, body, ctype = json_bytes({"case": case})
            self._send(code, body, ctype)
            return
        if path == "/" or path == "":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        data = self._read_json()
        store = load_store()

        if path == "/api/cases":
            t = now()
            case = {
                "id": new_id("case"),
                "req_code": next_req_code(store),
                "req_type": (data.get("req_type") or "REQ").strip().upper(),
                "sku": (data.get("sku") or "").strip(),
                "product_name": (data.get("product_name") or data.get("title") or "").strip(),
                "producer": (data.get("producer") or "").strip(),
                "hands": (data.get("hands") or data.get("employee") or "").strip(),
                "priority": (data.get("priority") or "Normal").strip(),
                "status": "discussing",
                "created": t,
                "updated": t,
                "chunks": [],
                "scope": {"body": "", "locked": False, "locked_at": None},
                "prep": {
                    "body": "",
                    "signed": False,
                    "signed_at": None,
                    "signed_by": None,
                },
            }
            normalize_case(case)
            seed = (data.get("seed") or "").strip()
            if seed:
                for para in re.split(r"\n\s*\n+", seed):
                    para = para.strip()
                    if not para:
                        continue
                    seq = next_ticket_seq(case)
                    case["chunks"].append(
                        {
                            "id": new_id("chk"),
                            "ticket_kind": "IDA",
                            "ticket_seq": seq,
                            "ref": format_ticket_ref(case, "IDA", seq),
                            "body": para,
                            "work_lane": "discussion",
                            "closed": False,
                            "closed_at": None,
                            "closed_by": None,
                            "close_note": "",
                            "comments": [],
                        }
                    )
            store.setdefault("cases", []).insert(0, case)
            save_store(store)
            code, body, ctype = json_bytes({"case": case}, 201)
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/chunks", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            body_text = (data.get("body") or "").strip()
            if not body_text:
                code, body, ctype = json_bytes({"error": "body required"}, 400)
                self._send(code, body, ctype)
                return
            tkind = (data.get("ticket_kind") or data.get("kind") or "IDA").strip().upper()
            if tkind not in TICKET_KINDS:
                tkind = "IDA"
            seq = next_ticket_seq(case)
            chunk = {
                "id": new_id("chk"),
                "ticket_kind": tkind,
                "ticket_seq": seq,
                "ref": format_ticket_ref(case, tkind, seq),
                "body": body_text,
                "work_lane": "discussion",
                "closed": False,
                "closed_at": None,
                "closed_by": None,
                "close_note": "",
                "comments": [],
            }
            case.setdefault("chunks", []).append(chunk)
            case["updated"] = now()
            if case.get("status") == "signed":
                pass
            elif case.get("status") not in ("scope_locked", "prep_draft", "building"):
                case["status"] = "discussing"
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "chunk": chunk}, 201)
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/chunks/([^/]+)/comments", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            if chunk.get("closed"):
                code, body, ctype = json_bytes(
                    {"error": "block closed — reopen to comment"}, 400
                )
                self._send(code, body, ctype)
                return
            author = (data.get("author") or "hands").strip().lower()
            if author not in ("hands", "agent"):
                author = "hands"
            text = (data.get("text") or "").strip()
            if not text:
                code, body, ctype = json_bytes({"error": "text required"}, 400)
                self._send(code, body, ctype)
                return
            comment = {
                "id": new_id("cm"),
                "author": author,
                "text": text,
                "created": now(),
            }
            chunk.setdefault("comments", []).append(comment)
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "comment": comment}, 201)
            self._send(code, body, ctype)
            return

        m = re.fullmatch(
            r"/api/cases/([^/]+)/chunks/([^/]+)/comments/([^/]+)", path
        )
        if m:
            # CHG20 — edit existing thread comment
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            comment = next(
                (
                    cm
                    for cm in (chunk.get("comments") or [])
                    if cm.get("id") == m.group(3)
                ),
                None,
            )
            if not comment:
                code, body, ctype = json_bytes({"error": "comment not found"}, 404)
                self._send(code, body, ctype)
                return
            if "text" in data:
                text = str(data.get("text") or "").strip()
                if not text:
                    code, body, ctype = json_bytes({"error": "text required"}, 400)
                    self._send(code, body, ctype)
                    return
                comment["text"] = text
                comment["edited"] = now()
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "comment": comment})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/chunks/([^/]+)/close", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk["closed"] = True
            chunk["closed_at"] = now()
            chunk["closed_by"] = "hands"
            chunk["close_note"] = (data.get("note") or "AGREED").strip() or "AGREED"
            # IDA28: seal → CLOSED lane (unless Hands picks another lane in stamp)
            if data.get("work_lane"):
                lane = str(data.get("work_lane") or "").strip().lower()
                if lane in WORK_LANES:
                    chunk["work_lane"] = lane
                else:
                    chunk["work_lane"] = "closed"
            else:
                chunk["work_lane"] = "closed"
            normalize_chunk(chunk)
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "chunk": chunk})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/chunks/([^/]+)/lane", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            lane = str(data.get("work_lane") or data.get("lane") or "").strip().lower()
            if lane not in WORK_LANES:
                code, body, ctype = json_bytes(
                    {"error": "work_lane must be discussion|paused|run|test|closed"}, 400
                )
                self._send(code, body, ctype)
                return
            chunk["work_lane"] = lane
            normalize_chunk(chunk)
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "chunk": chunk})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/chunks/([^/]+)/reopen", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            if (case.get("scope") or {}).get("locked"):
                code, body, ctype = json_bytes(
                    {"error": "scope locked — unlock scope first"}, 400
                )
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            chunk["closed"] = False
            chunk["closed_at"] = None
            chunk["closed_by"] = None
            case["updated"] = now()
            case["status"] = "discussing"
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "chunk": chunk})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/scope", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            scope = case.setdefault(
                "scope", {"body": "", "locked": False, "locked_at": None}
            )
            if scope.get("locked") and "body" in data:
                code, body, ctype = json_bytes(
                    {"error": "scope locked — unlock to edit"}, 400
                )
                self._send(code, body, ctype)
                return
            if "body" in data:
                scope["body"] = str(data.get("body") or "")
            if data.get("lock") is True:
                scope["locked"] = True
                scope["locked_at"] = now()
                case["status"] = "scope_locked"
            if data.get("unlock") is True:
                if (case.get("prep") or {}).get("signed"):
                    code, body, ctype = json_bytes(
                        {"error": "prep already signed — cannot unlock scope"}, 400
                    )
                    self._send(code, body, ctype)
                    return
                scope["locked"] = False
                scope["locked_at"] = None
                case["status"] = "discussing"
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/prep", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            prep = case.setdefault(
                "prep",
                {"body": "", "signed": False, "signed_at": None, "signed_by": None},
            )
            if prep.get("signed") and ("body" in data or data.get("generate")):
                code, body, ctype = json_bytes(
                    {"error": "prep signed — read only"}, 400
                )
                self._send(code, body, ctype)
                return
            if data.get("generate"):
                # Local rewrite from closed chunks + scope (no external model).
                prep["body"] = build_prep(case)
                case["status"] = "prep_draft"
            elif "body" in data:
                prep["body"] = str(data.get("body") or "")
                if not prep.get("signed"):
                    case["status"] = "prep_draft"
            if data.get("sign") is True:
                if not (case.get("scope") or {}).get("locked"):
                    code, body, ctype = json_bytes(
                        {"error": "lock scope before signing prep"}, 400
                    )
                    self._send(code, body, ctype)
                    return
                if not (prep.get("body") or "").strip():
                    code, body, ctype = json_bytes(
                        {"error": "prep body empty"}, 400
                    )
                    self._send(code, body, ctype)
                    return
                prep["signed"] = True
                prep["signed_at"] = now()
                prep["signed_by"] = "hands"
                case["status"] = "signed"
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case})
            self._send(code, body, ctype)
            return

        m = re.fullmatch(r"/api/cases/([^/]+)/meta", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            if "req_type" in data:
                case["req_type"] = str(data.get("req_type") or "REQ").strip().upper()
            if "sku" in data:
                case["sku"] = str(data.get("sku") or "").strip()
            if "product_name" in data:
                case["product_name"] = str(data.get("product_name") or "").strip()
            if "producer" in data:
                case["producer"] = str(data.get("producer") or "").strip()
            if "hands" in data or "employee" in data:
                case["hands"] = str(
                    data.get("hands") if "hands" in data else data.get("employee") or ""
                ).strip()
            if "priority" in data:
                case["priority"] = str(data.get("priority") or "").strip()
            normalize_case(case)
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case})
            self._send(code, body, ctype)
            return

        code, body, ctype = json_bytes({"error": "not found"}, 404)
        self._send(code, body, ctype)

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        data = self._read_json()
        store = load_store()
        m = re.fullmatch(r"/api/cases/([^/]+)/chunks/([^/]+)", path)
        if m:
            case = find_case(store, m.group(1))
            if not case:
                code, body, ctype = json_bytes({"error": "not found"}, 404)
                self._send(code, body, ctype)
                return
            if (case.get("scope") or {}).get("locked"):
                code, body, ctype = json_bytes(
                    {"error": "scope locked — unlock to edit chunks"}, 400
                )
                self._send(code, body, ctype)
                return
            chunk = next(
                (ch for ch in case.get("chunks") or [] if ch.get("id") == m.group(2)),
                None,
            )
            if not chunk:
                code, body, ctype = json_bytes({"error": "chunk not found"}, 404)
                self._send(code, body, ctype)
                return
            if chunk.get("closed"):
                code, body, ctype = json_bytes(
                    {"error": "block closed — reopen to edit"}, 400
                )
                self._send(code, body, ctype)
                return
            if "body" in data:
                chunk["body"] = str(data.get("body") or "")
            case["updated"] = now()
            save_store(store)
            code, body, ctype = json_bytes({"case": case, "chunk": chunk})
            self._send(code, body, ctype)
            return
        code, body, ctype = json_bytes({"error": "not found"}, 404)
        self._send(code, body, ctype)


def build_prep(case: dict[str, Any]) -> str:
    """Agent-side local rewrite: Product prep for an agent (template, not LLM)."""
    lines = [
        f"# Product prep for an agent",
        f"",
        f"**Bay file:** {case.get('req_code') or '—'}  ",
        f"**Type:** {case.get('req_type') or 'REQ'}  ",
        f"**SKU:** {case.get('sku') or '—'}  ",
        f"**Product:** {case.get('product_name') or '—'}  ",
        f"**Title line:** {case.get('title') or compose_title(case)}  ",
        f"**Producer:** {case.get('producer') or '—'}  ",
        f"**Hands:** {case.get('hands') or '—'}  ",
        f"**Priority:** {case.get('priority') or '—'}  ",
        f"",
        f"---",
        f"",
        f"## Job",
        f"",
        f"{case.get('title') or compose_title(case)}",
        f"",
        f"## Agreed discussion (closed blocks only)",
        f"",
    ]
    closed = [ch for ch in (case.get("chunks") or []) if ch.get("closed")]
    open_n = sum(1 for ch in (case.get("chunks") or []) if not ch.get("closed"))
    if not closed:
        lines.append("_No blocks closed yet. Close what is agreed before treating this as law._")
        lines.append("")
    else:
        for ch in closed:
            ref = ch.get("ref") or "?"
            note = ch.get("close_note") or "AGREED"
            lines.append(f"### {ref} · [{note}]")
            lines.append("")
            lines.append(ch.get("body") or "")
            lines.append("")
            cms = ch.get("comments") or []
            if cms:
                lines.append("_Thread (archive):_")
                for cm in cms:
                    who = (cm.get("author") or "?").upper()
                    lines.append(f"- **{who}:** {cm.get('text') or ''}")
                lines.append("")
    if open_n:
        lines.append(f"_Note: {open_n} block(s) still open — not in scope until closed._")
        lines.append("")
    scope_body = ((case.get("scope") or {}).get("body") or "").strip()
    lines.extend(
        [
            f"## Scope",
            f"",
            scope_body or "_Scope not written._",
            f"",
            f"## First slice",
            f"",
            f"_Hands: edit this section after generate — what ships first._",
            f"",
            f"## Out of scope / non-goals",
            f"",
            f"_Hands: cut anything that must not be built from open talk._",
            f"",
            f"## Sign-off",
            f"",
            f"Hands must **Sign prep** in ReqRep. Until signed, this is draft only.",
            f"",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    load_store()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ReqRep · CO.BBC-002-RR · http://{HOST}:{PORT}/")
    print(f"  store: {STORE}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
