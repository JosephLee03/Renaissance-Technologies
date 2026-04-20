from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sa_cta.config import load_config
import sa_cta.gui.app as gui_app_module
from sa_cta.gui import create_app
from sa_cta.gui.app import UI_VERSION


def _find_listeners(port: int) -> list[int]:
    cmd = ["netstat", "-ano", "-p", "tcp"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        raw = line.strip()
        if ":" not in raw or "LISTENING" not in raw:
            continue
        if f":{port}" not in raw:
            continue
        parts = re.split(r"\s+", raw)
        if not parts:
            continue
        tail = parts[-1]
        if tail.isdigit():
            pids.add(int(tail))
    return sorted(pids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SA monitoring dashboard.")
    parser.add_argument("--config", "-config", default=str(PROJECT_ROOT / "config" / "default.yaml"))
    parser.add_argument("--host", "-host", default="127.0.0.1")
    parser.add_argument("--port", "-port", type=int, default=8050)
    args = parser.parse_args()

    listeners = _find_listeners(args.port)
    if listeners:
        pid_text = ", ".join(str(pid) for pid in listeners)
        print(f"[GUI] port {args.port} is already occupied by PID(s): {pid_text}")
        print("[GUI] Close stale GUI processes first, e.g. taskkill /PID <pid> /F")
        print("[GUI] Or start on another port, e.g. --port 8051")
        raise SystemExit(2)

    cfg = load_config(args.config)
    db_path = PROJECT_ROOT / cfg.database["path"]

    print(f"[GUI] module: {Path(__file__).resolve()}")
    print(f"[GUI] app_module: {Path(gui_app_module.__file__).resolve()}")
    print(f"[GUI] python: {sys.executable}")
    print(f"[GUI] ui_version: {UI_VERSION}")
    print(f"[GUI] db_path: {db_path}")
    print(f"[GUI] url: http://{args.host}:{args.port}")
    print(f"[GUI] verify: http://{args.host}:{args.port}/__rt_gui_info")

    app = create_app(db_path)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
