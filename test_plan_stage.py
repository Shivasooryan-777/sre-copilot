"""
Plan-stage test for Cycle 1, Session 2.

This script runs:
    Perceive -> Plan

against all synthetic incidents in data/incidents/.

It makes sequential LLM calls only. Do not parallelize these calls.
"""

import json
from pathlib import Path

from sre_copilot.perceive import perceive
from sre_copilot.plan import plan


INCIDENT_DIR = Path("data/incidents")


def main() -> None:
    incident_files = sorted(INCIDENT_DIR.glob("incident_*.txt"))

    if not incident_files:
        raise SystemExit(f"No incident files found in {INCIDENT_DIR}")

    print("Starting Plan-stage test for all incidents.")
    print("LLM calls will run sequentially.")

    for index, incident_path in enumerate(incident_files, start=1):
        print()
        print("=" * 80)
        print(f"[{index}/{len(incident_files)}] Incident file: {incident_path}")
        print("=" * 80)

        observation = perceive(incident_path)

        print("\nPerceive output:")
        print(
            json.dumps(
                {
                    "source": observation.source,
                    "service": observation.service,
                    "severity_hint": observation.severity_hint,
                    "symptoms": observation.symptoms,
                    "summary": observation.summary,
                },
                indent=2,
            )
        )

        decision = plan(observation)

        print("\nPlan output:")
        print(json.dumps(decision.model_dump(), indent=2))

    print()
    print("=" * 80)
    print("Plan-stage test complete.")


if __name__ == "__main__":
    main()