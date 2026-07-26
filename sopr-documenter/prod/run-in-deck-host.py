#!/usr/bin/env python3
"""
sopr Documenter ROM → The Deck Host

Starts this ROM's server, opens The Deck Host, stops server when window closes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROD = Path(__file__).resolve().parent
BOX_SYS = PROD / "box_sys"
# big-box-company/sopr-documenter/prod → ../../../the-deck-host/shell
DECK_SHELL = PROD.parents[2] / "the-deck-host" / "shell"
DECK_HOST_PY = DECK_SHELL / "deck_host.py"

URL = os.environ.get("SOPR_URL", "http://127.0.0.1:42950/")
HEALTH = os.environ.get("SOPR_HEALTH", "http://127.0.0.1:42950/api/health")


def main() -> int:
    if not BOX_SYS.is_dir():
        print(f"box_sys missing: {BOX_SYS}", file=sys.stderr)
        return 1
    if not DECK_HOST_PY.is_file():
        print(f"The Deck Host not found: {DECK_HOST_PY}", file=sys.stderr)
        return 1

    server_cmd = f"{sys.executable} server.py"
    # office profile — wide desk for rail + bucket / kanban (not datbox short)
    profile = os.environ.get("DECK_HOST_PROFILE", "office").strip() or "office"
    cmd = [
        sys.executable,
        str(DECK_HOST_PY),
        "--title",
        "sopr Documenter",
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
    print("sopr Documenter · Big Box Company · The Deck Host")
    print(f"  ROM server: {BOX_SYS}")
    print(f"  host:       {DECK_HOST_PY}")
    print(f"  url:        {URL}")
    print(f"  profile:    {profile}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
