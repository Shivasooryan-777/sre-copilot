from __future__ import annotations

import argparse
import json
from typing import List, Optional

from sre_copilot.agent import run_agent_loop
from sre_copilot.tools import reset_restart_counter


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SentinelOps Cycle 1 SRE/DevOps Incident Copilot agent loop."
    )

    parser.add_argument(
        "incident_path",
        help="Path to an incident text file, e.g. data/incidents/incident_01_db_timeout.txt",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Hard stop for the Perceive-Plan-Act-Observe loop.",
    )

    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory where JSONL and JSON logs are written.",
    )

    parser.add_argument(
        "--reset-restart-counter",
        action="store_true",
        help="Reset the deliberate restart_service failure counter before running.",
    )

    args = parser.parse_args(argv)

    if args.reset_restart_counter:
        reset_restart_counter()

    summary = run_agent_loop(
        incident_path=args.incident_path,
        max_iterations=args.max_iterations,
        log_dir=args.log_dir,
    )

    result = summary.get("result", summary)

    print(json.dumps(result, indent=2, default=str))

    status = summary.get("status", "")

    if status == "failed_exception":
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())