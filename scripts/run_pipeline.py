from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sa_cta.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SA intraday CTA pipeline.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "default.yaml"))
    parser.add_argument("--start-day", default=None)
    parser.add_argument("--end-day", default=None)
    args = parser.parse_args()

    result = run_pipeline(
        config_path=args.config,
        start_day=args.start_day,
        end_day=args.end_day,
    )

    print("Run ID:", result["run_id"])
    print("Artifacts:", result["artifacts_dir"])
    if result.get("log_file_path"):
        print("Log File:", result["log_file_path"])
    print("Lifecycle Event Count:", len(result.get("lifecycle_events", [])))
    print("Metrics:")
    print(json.dumps(result["metrics"], indent=2, ensure_ascii=True))
    print("Strategy Summary:")
    print(json.dumps(result["strategy_summary"], indent=2, ensure_ascii=True))
    print("Execution Summary:")
    print(json.dumps(result["execution_summary"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

