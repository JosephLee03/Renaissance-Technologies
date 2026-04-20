from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sa_cta.config import load_config
from sa_cta.data import list_trading_days, load_min1_days, load_ticks_days
from sa_cta.quality import audit_min1, audit_ticks


def _filter(days: list[str], start: str | None, end: str | None) -> list[str]:
    out = []
    for d in days:
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(d)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run data quality audit for SA dataset.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "default.yaml"))
    parser.add_argument("--start-day", default=None)
    parser.add_argument("--end-day", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_root = PROJECT_ROOT / cfg.data["root"]

    min1_days = list_trading_days(data_root, cfg.data["min1_subdir"])
    tick_days = list_trading_days(data_root, cfg.data["tick_subdir"])
    days = _filter(sorted(set(min1_days).intersection(set(tick_days))), args.start_day, args.end_day)

    min1_df = load_min1_days(data_root, cfg.data["min1_subdir"], days)
    ticks_df = load_ticks_days(data_root, cfg.data["tick_subdir"], days)

    report = {
        "days": len(days),
        "min1": audit_min1(min1_df),
        "ticks": audit_ticks(ticks_df),
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
