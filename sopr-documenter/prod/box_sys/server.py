#!/usr/bin/env python3
"""
sopr Documenter — Big Box Company
Boring documentation industrial ROM.

House files: ../safe_box/*.sopr
Part codes (SPR-####) are stable; section membership is separate.
"""

from __future__ import annotations

import json
import re
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

BOX_SYS = Path(__file__).resolve().parent
PROD = BOX_SYS.parent
SAFE_BOX = PROD / "safe_box"
HOST = "127.0.0.1"
PORT = 42950  # BBC · sopr — not DATBOX toys

DOC_EXT = ".sopr"
PART_PREFIX = "SPR"


def ensure_dirs() -> None:
    SAFE_BOX.mkdir(parents=True, exist_ok=True)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", (name or "").strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "document"


def doc_path(slug: str) -> Path:
    safe = re.sub(r"[^\w.\-]+", "_", slug or "document")
    return SAFE_BOX / f"{safe}{DOC_EXT}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def empty_doc(doc_name: str, slug: str) -> dict[str, Any]:
    return {
        "house": "BIGBOX",
        "product": "sopr-documenter",
        "version": 1,
        "doc_name": doc_name,
        "slug": slug,
        "next_part": 1,
        "next_section": 1,
        "section_order": [],  # section_id list
        "sections": {},  # id -> {section_id, label, part_ids: []}
        "parts": {},  # part_code -> {part_code, leaf, section_id, created_at}
        # Document-level glass chips used in production (not per-frag). Dedup by chip_id.
        "tps_chips": [],
        "updated_at": time.time(),
    }


def ensure_doc_shape(doc: dict[str, Any]) -> dict[str, Any]:
    """Migrate older .sopr files that predate tps_chips."""
    if "tps_chips" not in doc or not isinstance(doc.get("tps_chips"), list):
        doc["tps_chips"] = []
    return doc


def record_tps_chip(
    doc: dict[str, Any],
    chip_id: str,
    export_id: str = "",
) -> dict[str, Any] | None:
    """
    Append or touch a chip on the document bin. No vencodes. Dedup by chip_id.
    Returns the chip entry, or None if chip_id empty.
    """
    chip_id = (chip_id or "").strip()
    if not chip_id:
        return None
    export_id = (export_id or "").strip()
    now = time.time()
    ensure_doc_shape(doc)
    chips: list[dict[str, Any]] = doc["tps_chips"]
    for row in chips:
        if str(row.get("chip_id") or "") == chip_id:
            row["last_seen_at"] = now
            if export_id and not row.get("export_id"):
                row["export_id"] = export_id
            return row
    entry = {
        "chip_id": chip_id,
        "export_id": export_id,
        "first_seen_at": now,
        "last_seen_at": now,
    }
    chips.append(entry)
    return entry


def list_docs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(SAFE_BOX.glob(f"*{DOC_EXT}")):
        try:
            d = load_json(p)
        except (OSError, json.JSONDecodeError):
            out.append({"slug": p.stem, "doc_name": p.stem, "error": "unreadable"})
            continue
        parts = d.get("parts") or {}
        sections = d.get("sections") or {}
        out.append(
            {
                "slug": d.get("slug") or p.stem,
                "doc_name": d.get("doc_name") or p.stem,
                "part_count": len(parts),
                "section_count": len(sections),
                "updated_at": d.get("updated_at"),
            }
        )
    return out


def load_doc(slug: str) -> dict[str, Any] | None:
    path = doc_path(slug)
    if not path.is_file():
        return None
    return ensure_doc_shape(load_json(path))


def save_doc(doc: dict[str, Any]) -> None:
    doc["updated_at"] = time.time()
    slug = doc.get("slug") or "document"
    save_json(doc_path(slug), doc)


def mint_part_code(doc: dict[str, Any]) -> str:
    n = int(doc.get("next_part") or 1)
    code = f"{PART_PREFIX}-{n:04d}"
    doc["next_part"] = n + 1
    return code


def mint_section_id(doc: dict[str, Any]) -> str:
    n = int(doc.get("next_section") or 1)
    sid = f"sec-{n:04d}"
    doc["next_section"] = n + 1
    return sid


def find_or_create_section(doc: dict[str, Any], label: str) -> str:
    label = (label or "").strip() or "Loose / unbinned"
    sections = doc.setdefault("sections", {})
    for sid, sec in sections.items():
        if (sec.get("label") or "").strip().lower() == label.lower():
            return sid
    sid = mint_section_id(doc)
    sections[sid] = {"section_id": sid, "label": label, "part_ids": []}
    order = doc.setdefault("section_order", [])
    if sid not in order:
        order.append(sid)
    return sid


def ensure_section(doc: dict[str, Any], section_id: str, label: str | None = None) -> str:
    sections = doc.setdefault("sections", {})
    if section_id and section_id in sections:
        if label and label.strip():
            sections[section_id]["label"] = label.strip()
        return section_id
    return find_or_create_section(doc, label or "Loose / unbinned")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BOX_SYS), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys_stderr = __import__("sys").stderr
        print(f"[sopr] {args[0] if args else fmt}", file=sys_stderr)

    def end_headers(self) -> None:
        # Local ROM cords (Machina / other ports may POST stamp)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def _json(self, code: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> Any:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)

        if path == "/api/health":
            return self._json(
                200,
                {
                    "ok": True,
                    "product": "sopr-documenter",
                    "house": "BIGBOX",
                    "port": PORT,
                },
            )

        if path == "/api/docs":
            return self._json(200, {"docs": list_docs()})

        m = re.fullmatch(r"/api/docs/([^/]+)", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            return self._json(200, {"ok": True, "doc": doc})

        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        body = self._read_json()

        if path == "/api/docs":
            name = (body.get("doc_name") or body.get("name") or "").strip()
            if not name:
                return self._json(400, {"ok": False, "error": "doc_name required"})
            slug = slugify(body.get("slug") or name)
            path_f = doc_path(slug)
            if path_f.is_file():
                return self._json(409, {"ok": False, "error": "document exists", "slug": slug})
            doc = empty_doc(name, slug)
            # starter loose section
            find_or_create_section(doc, "Loose / unbinned")
            save_doc(doc)
            return self._json(201, {"ok": True, "doc": doc})

        m = re.fullmatch(r"/api/docs/([^/]+)/sections", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            label = (body.get("label") or "").strip()
            if not label:
                return self._json(400, {"ok": False, "error": "label required"})
            sid = find_or_create_section(doc, label)
            save_doc(doc)
            return self._json(200, {"ok": True, "section_id": sid, "doc": doc})

        m = re.fullmatch(r"/api/docs/([^/]+)/parts", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            leaf = (body.get("leaf") or "").strip()
            if not leaf:
                return self._json(400, {"ok": False, "error": "leaf required"})
            sid = body.get("section_id") or ""
            label = body.get("section_label") or body.get("label")
            if sid and sid in (doc.get("sections") or {}):
                pass
            else:
                sid = find_or_create_section(doc, label or "Loose / unbinned")
            code = mint_part_code(doc)
            part = {
                "part_code": code,
                "leaf": leaf,
                "section_id": sid,
                "created_at": time.time(),
            }
            doc.setdefault("parts", {})[code] = part
            sec = doc["sections"][sid]
            # newest under composer: insert at front of part_ids
            pids = sec.setdefault("part_ids", [])
            pids.insert(0, code)
            # Optional: client peeked Machina cord — record chip on doc only (no per-frag)
            chip_id = str(body.get("chip_id") or body.get("tps_chip") or "").strip()
            export_id = str(body.get("export_id") or body.get("tps_export") or "").strip()
            chip_row = None
            if chip_id:
                chip_row = record_tps_chip(doc, chip_id, export_id)
            save_doc(doc)
            return self._json(
                201,
                {"ok": True, "part": part, "doc": doc, "tps_chip": chip_row},
            )

        m = re.fullmatch(r"/api/docs/([^/]+)/tps-chips", path)
        if m:
            # Stamp current (or any) chip onto the document bin — About / whisper
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            chip_id = str(body.get("chip_id") or body.get("tps_chip") or "").strip()
            export_id = str(body.get("export_id") or body.get("tps_export") or "").strip()
            if not chip_id:
                return self._json(400, {"ok": False, "error": "chip_id required"})
            row = record_tps_chip(doc, chip_id, export_id)
            save_doc(doc)
            return self._json(200, {"ok": True, "tps_chip": row, "doc": doc})

        m = re.fullmatch(r"/api/docs/([^/]+)/layout", path)
        if m:
            # kanban / section reorder:
            # - columns: [{section_id, label?, part_ids}] frag membership + order
            # - section_order: outline order of sections (polymath intake ≠ final outline)
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            section_order = body.get("section_order")
            columns = body.get("columns")  # optional if only reordering sections
            parts = doc.setdefault("parts", {})
            sections = doc.setdefault("sections", {})

            if isinstance(columns, list):
                new_order: list[str] = []
                seen_parts: set[str] = set()
                for col in columns:
                    if not isinstance(col, dict):
                        continue
                    sid = col.get("section_id") or ""
                    label = (col.get("label") or "").strip()
                    if not sid or sid not in sections:
                        if label:
                            sid = find_or_create_section(doc, label)
                        else:
                            continue
                    if label:
                        sections[sid]["label"] = label
                    pids = []
                    for pid in col.get("part_ids") or []:
                        pid = str(pid)
                        if pid not in parts:
                            continue
                        if pid in seen_parts:
                            continue
                        seen_parts.add(pid)
                        parts[pid]["section_id"] = sid  # membership only
                        pids.append(pid)
                    sections[sid]["part_ids"] = pids
                    if sid not in new_order:
                        new_order.append(sid)
                if isinstance(section_order, list) and section_order:
                    ordered = [s for s in section_order if s in sections]
                    for s in new_order:
                        if s not in ordered:
                            ordered.append(s)
                    doc["section_order"] = ordered
                else:
                    doc["section_order"] = new_order or list(sections.keys())
                loose = find_or_create_section(doc, "Loose / unbinned")
                for code, part in parts.items():
                    if code not in seen_parts:
                        part["section_id"] = loose
                        if code not in sections[loose]["part_ids"]:
                            sections[loose]["part_ids"].append(code)
            elif isinstance(section_order, list) and section_order:
                # section outline only — frags stay put
                ordered = [s for s in section_order if s in sections]
                for s in sections:
                    if s not in ordered:
                        ordered.append(s)
                doc["section_order"] = ordered
            else:
                return self._json(
                    400,
                    {"ok": False, "error": "columns or section_order required"},
                )
            save_doc(doc)
            return self._json(200, {"ok": True, "doc": doc})

        return self._json(404, {"ok": False, "error": "no route"})

    def do_DELETE(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        m = re.fullmatch(r"/api/docs/([^/]+)", path)
        if m:
            p = doc_path(m.group(1))
            if p.is_file():
                p.unlink()
                return self._json(200, {"ok": True})
            return self._json(404, {"ok": False, "error": "not found"})
        return self._json(404, {"ok": False, "error": "no route"})

    def do_PUT(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        body = self._read_json()
        m = re.fullmatch(r"/api/docs/([^/]+)/parts/([^/]+)", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            code = m.group(2)
            parts = doc.get("parts") or {}
            if code not in parts:
                return self._json(404, {"ok": False, "error": "part not found"})
            leaf = body.get("leaf")
            if leaf is not None:
                parts[code]["leaf"] = str(leaf)
            # never rename part_code
            save_doc(doc)
            return self._json(200, {"ok": True, "part": parts[code], "doc": doc})
        return self._json(404, {"ok": False, "error": "no route"})


def main() -> int:
    ensure_dirs()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"sopr Documenter · Big Box Company")
    print(f"  http://{HOST}:{PORT}/")
    print(f"  safe_box: {SAFE_BOX}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
