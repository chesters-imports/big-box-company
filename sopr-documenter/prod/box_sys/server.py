#!/usr/bin/env python3
"""
sopr Documenter — Big Box Company
Boring documentation industrial ROM.

House files: ../safe_box/*.sopr
Part codes (SPR-####) are stable; section membership is separate.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

BOX_SYS = Path(__file__).resolve().parent
PROD = BOX_SYS.parent
SAFE_BOX = PROD / "safe_box"
MEDIA_BOX = SAFE_BOX / "_media"
HOST = "127.0.0.1"
PORT = 42950  # BBC · sopr — not DATBOX toys

DOC_EXT = ".sopr"
PART_PREFIX = "SPR"
BLOCK_TYPES = frozenset({"text", "image", "table"})
IMAGE_MAX_BYTES = 12 * 1024 * 1024  # 12 MiB local ROM


def ensure_dirs() -> None:
    SAFE_BOX.mkdir(parents=True, exist_ok=True)
    MEDIA_BOX.mkdir(parents=True, exist_ok=True)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", (name or "").strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "document"


def sanitize_folder(name: str) -> str:
    """Physical dir under safe_box. Empty = vault root."""
    s = (name or "").strip().strip("/\\")
    if not s:
        return ""
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s or s.startswith("_"):
        raise ValueError("invalid folder name")
    if s.lower().endswith(".sopr"):
        raise ValueError("invalid folder name")
    return s


def safe_stem(slug: str) -> str:
    safe = re.sub(r"[^\w.\-]+", "_", slug or "document")
    if not safe:
        raise ValueError("empty slug")
    return safe


def doc_path(slug: str, folder: str = "") -> Path:
    """Canonical path for a new write (folder optional). Prefer resolve for reads."""
    stem = safe_stem(slug)
    name = f"{stem}{DOC_EXT}"
    folder = sanitize_folder(folder) if folder else ""
    if folder:
        return SAFE_BOX / folder / name
    return SAFE_BOX / name


def iter_doc_files() -> list[Path]:
    """All .sopr under safe_box root + one folder level (vault, not whole disk)."""
    ensure_dirs()
    found: list[Path] = []
    seen: set[str] = set()
    for p in sorted(SAFE_BOX.iterdir()):
        if p.is_file() and p.suffix == DOC_EXT:
            if p.stem not in seen:
                seen.add(p.stem)
                found.append(p)
        elif p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_"):
            try:
                sanitize_folder(p.name)
            except ValueError:
                continue
            for child in sorted(p.iterdir()):
                if child.is_file() and child.suffix == DOC_EXT and child.stem not in seen:
                    seen.add(child.stem)
                    found.append(child)
    return found


def folder_of_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(SAFE_BOX.resolve())
    except ValueError:
        return ""
    if len(rel.parts) == 1:
        return ""
    return rel.parts[0]


def resolve_doc_path(slug: str) -> Path | None:
    stem = safe_stem(slug)
    for p in iter_doc_files():
        if p.stem == stem:
            return p
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def normalize_part(part: dict[str, Any]) -> dict[str, Any]:
    """Ensure block type + payloads on every part (old files default to text)."""
    if not isinstance(part, dict):
        return part
    block = str(part.get("block") or "text").strip().lower()
    if block not in BLOCK_TYPES:
        block = "text"
    part["block"] = block
    if block == "text":
        part.setdefault("leaf", "")
        part["as_pre"] = bool(part.get("as_pre"))
    elif block == "image":
        part.setdefault("leaf", "")  # caption
        part.setdefault("image_id", "")
        part.setdefault("image_name", "")
        part["as_pre"] = False
    elif block == "table":
        part.setdefault("leaf", "")  # optional title / note
        tbl = part.get("table")
        if not isinstance(tbl, dict):
            tbl = {}
        rows = tbl.get("rows")
        if not isinstance(rows, list) or not rows:
            rows = [["", ""], ["", ""]]
        clean: list[list[str]] = []
        for row in rows:
            if isinstance(row, list):
                clean.append([str(c if c is not None else "") for c in row])
            else:
                clean.append([str(row)])
        # rectangularize
        width = max((len(r) for r in clean), default=2)
        width = max(1, width)
        for r in clean:
            while len(r) < width:
                r.append("")
            del r[width:]
        part["table"] = {
            "rows": clean,
            "header": bool(tbl.get("header", True)),
        }
        part["as_pre"] = False
    return part


def ensure_doc_shape(doc: dict[str, Any]) -> dict[str, Any]:
    """Migrate older .sopr files that predate tps_chips / block types."""
    if "tps_chips" not in doc or not isinstance(doc.get("tps_chips"), list):
        doc["tps_chips"] = []
    parts = doc.get("parts")
    if isinstance(parts, dict):
        for code, part in list(parts.items()):
            if isinstance(part, dict):
                parts[code] = normalize_part(part)
    return doc


def empty_table(rows: int = 3, cols: int = 3) -> dict[str, Any]:
    return {
        "header": True,
        "rows": [["" for _ in range(cols)] for _ in range(rows)],
    }


def mint_media_id() -> str:
    return "m." + secrets.token_hex(8)


def media_paths(media_id: str) -> tuple[Path, Path]:
    safe = re.sub(r"[^\w.\-]+", "", media_id or "")
    if not safe.startswith("m."):
        raise ValueError("invalid media id")
    return MEDIA_BOX / f"{safe}.bin", MEDIA_BOX / f"{safe}.json"


def save_media_bytes(
    raw: bytes,
    *,
    content_type: str,
    filename: str = "",
) -> dict[str, Any]:
    if not raw:
        raise ValueError("empty image")
    if len(raw) > IMAGE_MAX_BYTES:
        raise ValueError(f"image too large (max {IMAGE_MAX_BYTES // (1024 * 1024)} MiB)")
    mid = mint_media_id()
    bin_p, meta_p = media_paths(mid)
    bin_p.write_bytes(raw)
    meta = {
        "media_id": mid,
        "content_type": (content_type or "application/octet-stream").split(";")[0].strip(),
        "filename": (filename or "").strip()[:200],
        "bytes": len(raw),
        "created_at": time.time(),
    }
    save_json(meta_p, meta)
    return meta


def load_media_meta(media_id: str) -> dict[str, Any] | None:
    try:
        bin_p, meta_p = media_paths(media_id)
    except ValueError:
        return None
    if not meta_p.is_file() or not bin_p.is_file():
        return None
    try:
        return load_json(meta_p)
    except (OSError, json.JSONDecodeError):
        return None


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
    """Flat list for strip / compat — includes folder place."""
    out: list[dict[str, Any]] = []
    for p in iter_doc_files():
        folder = folder_of_path(p)
        try:
            d = load_json(p)
        except (OSError, json.JSONDecodeError):
            out.append(
                {
                    "slug": p.stem,
                    "doc_name": p.stem,
                    "folder": folder,
                    "path": str(p.relative_to(SAFE_BOX)).replace("\\", "/"),
                    "error": "unreadable",
                }
            )
            continue
        parts = d.get("parts") or {}
        sections = d.get("sections") or {}
        out.append(
            {
                "slug": d.get("slug") or p.stem,
                "doc_name": d.get("doc_name") or p.stem,
                "folder": folder,
                "path": str(p.relative_to(SAFE_BOX)).replace("\\", "/"),
                "part_count": len(parts),
                "section_count": len(sections),
                "updated_at": d.get("updated_at"),
            }
        )
    return out


def list_vault(folder: str = "") -> dict[str, Any]:
    """
    Contents of one vault place (root or folder).
    folders: subdirs at root when folder=='' ; empty when inside a folder (one level).
    files: .sopr in this place.
    """
    ensure_dirs()
    try:
        folder = sanitize_folder(folder) if folder else ""
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    folders_out: list[dict[str, Any]] = []
    files_out: list[dict[str, Any]] = []

    if not folder:
        for p in sorted(SAFE_BOX.iterdir()):
            if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_"):
                try:
                    fid = sanitize_folder(p.name)
                except ValueError:
                    continue
                n = sum(1 for c in p.iterdir() if c.is_file() and c.suffix == DOC_EXT)
                folders_out.append({"id": fid, "name": fid, "file_count": n})
            elif p.is_file() and p.suffix == DOC_EXT:
                files_out.append(_file_meta(p, ""))
    else:
        base = SAFE_BOX / folder
        if not base.is_dir():
            return {"ok": False, "error": "folder not found", "folder": folder}
        for p in sorted(base.iterdir()):
            if p.is_file() and p.suffix == DOC_EXT:
                files_out.append(_file_meta(p, folder))

    return {
        "ok": True,
        "folder": folder,
        "folders": folders_out,
        "files": files_out,
        "vault": "safe_box",
    }


def _file_meta(p: Path, folder: str) -> dict[str, Any]:
    try:
        d = load_json(p)
        return {
            "slug": d.get("slug") or p.stem,
            "doc_name": d.get("doc_name") or p.stem,
            "folder": folder,
            "path": str(p.relative_to(SAFE_BOX)).replace("\\", "/"),
            "part_count": len(d.get("parts") or {}),
            "section_count": len(d.get("sections") or {}),
            "updated_at": d.get("updated_at"),
            "kind": "file",
        }
    except (OSError, json.JSONDecodeError):
        return {
            "slug": p.stem,
            "doc_name": p.stem,
            "folder": folder,
            "path": str(p.relative_to(SAFE_BOX)).replace("\\", "/"),
            "error": "unreadable",
            "kind": "file",
        }


def load_doc(slug: str) -> dict[str, Any] | None:
    path = resolve_doc_path(slug)
    if path is None or not path.is_file():
        return None
    return ensure_doc_shape(load_json(path))


def save_doc(doc: dict[str, Any]) -> None:
    doc["updated_at"] = time.time()
    slug = doc.get("slug") or "document"
    path = resolve_doc_path(slug)
    if path is None:
        path = doc_path(slug, "")
    save_json(path, doc)


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
                    "vault": True,
                    "safe_box": str(SAFE_BOX),
                },
            )

        if path == "/api/docs":
            return self._json(200, {"docs": list_docs()})

        # vault browser (folders under safe_box) — must not fall through to static 404
        if path in ("/api/vault", "/api/vault/"):
            qs = parse_qs(urlparse(self.path).query)
            folder = (qs.get("folder") or [""])[0]
            return self._json(200, list_vault(folder))

        m = re.fullmatch(r"/api/docs/([^/]+)", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            p = resolve_doc_path(m.group(1))
            folder = folder_of_path(p) if p else ""
            return self._json(
                200,
                {
                    "ok": True,
                    "doc": doc,
                    "folder": folder,
                    "path": (
                        str(p.relative_to(SAFE_BOX)).replace("\\", "/") if p else ""
                    ),
                },
            )

        m = re.fullmatch(r"/api/media/([^/]+)", path)
        if m:
            mid = m.group(1)
            try:
                bin_p, meta_p = media_paths(mid)
            except ValueError:
                return self._json(400, {"ok": False, "error": "invalid media id"})
            if not bin_p.is_file():
                return self._json(404, {"ok": False, "error": "not found"})
            meta = load_media_meta(mid) or {}
            raw = bin_p.read_bytes()
            ctype = meta.get("content_type") or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()
            self.wfile.write(raw)
            return

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
            if resolve_doc_path(slug) is not None:
                return self._json(409, {"ok": False, "error": "document exists", "slug": slug})
            try:
                folder = sanitize_folder(body.get("folder") or "") if body.get("folder") else ""
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            doc = empty_doc(name, slug)
            find_or_create_section(doc, "Loose / unbinned")
            path_f = doc_path(slug, folder)
            save_json(path_f, doc)
            return self._json(
                201,
                {
                    "ok": True,
                    "doc": doc,
                    "folder": folder,
                    "path": str(path_f.relative_to(SAFE_BOX)).replace("\\", "/"),
                },
            )

        if path == "/api/vault/folders":
            name = (body.get("name") or body.get("folder") or "").strip()
            try:
                fid = sanitize_folder(name)
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            if not fid:
                return self._json(400, {"ok": False, "error": "folder name required"})
            dest = SAFE_BOX / fid
            if dest.exists():
                return self._json(409, {"ok": False, "error": "folder exists", "id": fid})
            dest.mkdir(parents=True, exist_ok=False)
            return self._json(201, {"ok": True, "folder": {"id": fid, "name": fid}})

        if path == "/api/vault/move":
            slug = slugify(body.get("slug") or "")
            try:
                folder = sanitize_folder(body.get("folder") or "") if body.get("folder") else ""
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            src = resolve_doc_path(slug)
            if src is None:
                return self._json(404, {"ok": False, "error": "not found"})
            dest = doc_path(slug, folder)
            if src.resolve() == dest.resolve():
                return self._json(200, {"ok": True, "slug": slug, "folder": folder})
            if dest.exists():
                return self._json(409, {"ok": False, "error": "target exists"})
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
            return self._json(
                200,
                {
                    "ok": True,
                    "slug": slug,
                    "folder": folder,
                    "path": str(dest.relative_to(SAFE_BOX)).replace("\\", "/"),
                },
            )

        if path == "/api/vault/rename-folder":
            try:
                old = sanitize_folder(body.get("id") or body.get("folder") or "")
                new = sanitize_folder(body.get("name") or body.get("new_name") or "")
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            if not old or not new:
                return self._json(400, {"ok": False, "error": "id and name required"})
            src = SAFE_BOX / old
            if not src.is_dir():
                return self._json(404, {"ok": False, "error": "folder not found"})
            dest = SAFE_BOX / new
            if new != old and dest.exists():
                return self._json(409, {"ok": False, "error": "folder exists"})
            if new != old:
                src.rename(dest)
            return self._json(200, {"ok": True, "folder": {"id": new, "name": new, "old_id": old}})

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

        if path == "/api/media":
            # Base64 image upload → safe_box/_media (local ROM vault)
            b64 = body.get("data_base64") or body.get("data") or ""
            if isinstance(b64, str) and "," in b64 and b64.strip().startswith("data:"):
                b64 = b64.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64, validate=False)
            except (binascii.Error, ValueError):
                return self._json(400, {"ok": False, "error": "invalid base64"})
            try:
                meta = save_media_bytes(
                    raw,
                    content_type=str(body.get("content_type") or "image/png"),
                    filename=str(body.get("filename") or ""),
                )
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            return self._json(
                201,
                {
                    "ok": True,
                    "media": meta,
                    "url": "/api/media/" + meta["media_id"],
                },
            )

        m = re.fullmatch(r"/api/docs/([^/]+)/parts", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            block = str(body.get("block") or "text").strip().lower()
            if block not in BLOCK_TYPES:
                return self._json(400, {"ok": False, "error": "invalid block type"})
            leaf = str(body.get("leaf") or "").strip()
            sid = body.get("section_id") or ""
            label = body.get("section_label") or body.get("label")
            if sid and sid in (doc.get("sections") or {}):
                pass
            else:
                sid = find_or_create_section(doc, label or "Loose / unbinned")
            code = mint_part_code(doc)
            as_pre = bool(
                body.get("as_pre") or body.get("pre") or body.get("as_code")
            )
            part: dict[str, Any] = {
                "part_code": code,
                "block": block,
                "leaf": leaf,
                "section_id": sid,
                "created_at": time.time(),
                "as_pre": as_pre if block == "text" else False,
            }
            if block == "text":
                if not leaf:
                    return self._json(400, {"ok": False, "error": "leaf required"})
            elif block == "image":
                image_id = str(body.get("image_id") or "").strip()
                if not image_id or load_media_meta(image_id) is None:
                    return self._json(
                        400, {"ok": False, "error": "valid image_id required"}
                    )
                part["image_id"] = image_id
                part["image_name"] = str(body.get("image_name") or "").strip()[:200]
            elif block == "table":
                tbl = body.get("table")
                if not isinstance(tbl, dict):
                    tbl = empty_table()
                part["table"] = tbl
                part = normalize_part(part)
                # reject completely empty tables (all blank cells)
                rows = (part.get("table") or {}).get("rows") or []
                if not any(str(c).strip() for r in rows for c in r):
                    return self._json(
                        400, {"ok": False, "error": "table has no cell content"}
                    )
            part = normalize_part(part)
            doc.setdefault("parts", {})[code] = part
            sec = doc["sections"][sid]
            pids = sec.setdefault("part_ids", [])
            pids.insert(0, code)
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
        # DELETE fragment (SPR-####) — part code never recycled; next_part keeps climbing
        m = re.fullmatch(r"/api/docs/([^/]+)/parts/([^/]+)", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            code = m.group(2)
            parts = doc.setdefault("parts", {})
            if code not in parts:
                return self._json(404, {"ok": False, "error": "part not found"})
            del parts[code]
            for sec in (doc.get("sections") or {}).values():
                pids = sec.get("part_ids") or []
                sec["part_ids"] = [p for p in pids if p != code]
            save_doc(doc)
            return self._json(200, {"ok": True, "deleted": code, "doc": doc})

        m = re.fullmatch(r"/api/vault/folders/([^/]+)", path)
        if m:
            try:
                fid = sanitize_folder(m.group(1))
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            base = SAFE_BOX / fid
            if not base.is_dir():
                return self._json(404, {"ok": False, "error": "folder not found"})
            # refuse if any files remain
            leftovers = [x.name for x in base.iterdir()]
            if leftovers:
                return self._json(
                    400,
                    {
                        "ok": False,
                        "error": "folder not empty — move or delete documents first",
                        "items": leftovers[:10],
                    },
                )
            base.rmdir()
            return self._json(200, {"ok": True, "deleted": fid})

        m = re.fullmatch(r"/api/docs/([^/]+)", path)
        if m:
            p = resolve_doc_path(m.group(1))
            if p is not None and p.is_file():
                p.unlink()
                return self._json(200, {"ok": True})
            return self._json(404, {"ok": False, "error": "not found"})
        return self._json(404, {"ok": False, "error": "no route"})

    def do_PUT(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        body = self._read_json()
        # Rename document display name and/or file slug (keeps folder place)
        m = re.fullmatch(r"/api/docs/([^/]+)", path)
        if m:
            old_slug = m.group(1)
            src = resolve_doc_path(old_slug)
            if src is None:
                return self._json(404, {"ok": False, "error": "not found"})
            doc = ensure_doc_shape(load_json(src))
            folder = folder_of_path(src)
            name = body.get("doc_name") or body.get("name")
            if name is not None:
                name = str(name).strip()
                if not name:
                    return self._json(400, {"ok": False, "error": "doc_name required"})
                doc["doc_name"] = name
            new_slug = body.get("slug")
            if new_slug is not None:
                ns = slugify(str(new_slug).strip())
                if ns != old_slug:
                    if resolve_doc_path(ns) is not None:
                        return self._json(
                            409, {"ok": False, "error": "slug exists", "slug": ns}
                        )
                    doc["slug"] = ns
                    dest = doc_path(ns, folder)
                    save_json(dest, doc)
                    if src.resolve() != dest.resolve():
                        src.unlink()
                    return self._json(
                        200,
                        {
                            "ok": True,
                            "doc": doc,
                            "folder": folder,
                            "path": str(dest.relative_to(SAFE_BOX)).replace("\\", "/"),
                        },
                    )
            save_json(src, doc)
            return self._json(
                200,
                {
                    "ok": True,
                    "doc": doc,
                    "folder": folder,
                    "path": str(src.relative_to(SAFE_BOX)).replace("\\", "/"),
                },
            )

        m = re.fullmatch(r"/api/docs/([^/]+)/parts/([^/]+)", path)
        if m:
            doc = load_doc(m.group(1))
            if not doc:
                return self._json(404, {"ok": False, "error": "not found"})
            code = m.group(2)
            parts = doc.get("parts") or {}
            if code not in parts:
                return self._json(404, {"ok": False, "error": "part not found"})
            part = normalize_part(parts[code])
            leaf = body.get("leaf")
            if leaf is not None:
                part["leaf"] = str(leaf)
            if "as_pre" in body or "pre" in body or "as_code" in body:
                if part.get("block") == "text":
                    part["as_pre"] = bool(
                        body.get("as_pre")
                        if "as_pre" in body
                        else body.get("pre")
                        if "pre" in body
                        else body.get("as_code")
                    )
            if "table" in body and isinstance(body.get("table"), dict):
                part["table"] = body["table"]
                part["block"] = "table"
            if "image_id" in body:
                iid = str(body.get("image_id") or "").strip()
                if iid and load_media_meta(iid) is None:
                    return self._json(400, {"ok": False, "error": "invalid image_id"})
                if iid:
                    part["image_id"] = iid
                    part["block"] = "image"
            if "image_name" in body:
                part["image_name"] = str(body.get("image_name") or "").strip()[:200]
            parts[code] = normalize_part(part)
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
