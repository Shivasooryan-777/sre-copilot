from __future__ import annotations

import json

from sre_copilot.agent import run_agent_loop
from sre_copilot.interfaces import IncidentObservation, PlanDecision
from sre_copilot.tools import reset_restart_counter


def forced_restart_plan(
    observation: IncidentObservation,
    iteration: int,
) -> PlanDecision:
    """
    Deterministic plan override for Session 3 failure drill.

    This forces restart_service so that we deliberately trigger the known
    first-call failure in tools.restart_service and verify graceful recovery.
    """
    return PlanDecision(
        reasoning=(
            "Deliberate Session 3 failure drill: force restart_service "
            "to trigger known first-call failure and verify graceful recovery."
        ),
        tool_name="restart_service",
        tool_args={"service": observation.service or "payments-api"},
        resolved=False,
        summary="Forced restart_service to validate graceful recovery.",
    )


def main() -> int:
    # Ensure the mock restart_service is in its known failing state.
    reset_restart_counter()

    summary = run_agent_loop(
        incident_path="data/incidents/incident_01_db_timeout.txt",
        max_iterations=2,
        log_dir="logs",
        plan_override=forced_restart_plan,
    )

    result = summary.get("result", {})

    print(json.dumps(result, indent=2, default=str))

    status = summary.get("status", "")

    if status != "resolved_success_condition":
        print("FAILURE: restart_service failure drill did not resolve gracefully.")
        return 1

    print("SUCCESS: deliberate restart_service failure recovered without crashing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())