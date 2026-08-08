#!/usr/bin/env python3
"""ReqRep → The Deck Host"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROD = Path(__file__).resolve().parent
BOX_SYS = PROD / "box_sys"
DECK_SHELL = PROD.parents[2] / "the-deck-host" / "shell"
DECK_HOST_PY = DECK_SHELL / "deck_host.py"

URL = os.environ.get("REQREP_URL", "http://127.0.0.1:42962/")
HEALTH = os.environ.get("REQREP_HEALTH", "http://127.0.0.1:42962/api/health")


def main() -> int:
    if not BOX_SYS.is_dir():
        print(f"box_sys missing: {BOX_SYS}", file=sys.stderr)
        return 1
    if not DECK_HOST_PY.is_file():
        print(f"The Deck Host not found: {DECK_HOST_PY}", file=sys.stderr)
        return 1

    server_cmd = f"{sys.executable} server.py"
    profile = os.environ.get("DECK_HOST_PROFILE", "office").strip() or "office"
    cmd = [
        sys.executable,
        str(DECK_HOST_PY),
        "--title",
        "ReqRep",
        "--url",
        URL,
        "--health",
        HEALTH,
        "--profile",
        profile,
        "--spawn",
        server_cmd,
        "--spawn-cwd",
        str(BOX_SYS),
    ]
    print("ReqRep · Big Box Company · The Deck Host")
    print(f"  url: {URL}  profile: {profile}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
