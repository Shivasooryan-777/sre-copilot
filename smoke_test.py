"""Session 1 smoke tests for sre-copilot.

Run: python smoke_test.py
Verifies: tool stubs, schema-validated Plan call with few-shot prompt,
and prints raw model output automatically if the fallback triggers.
"""

from sre_copilot import tools
from sre_copilot.llm_client import generate
from sre_copilot.interfaces import PlanDecision


def test_tools():
    tools.reset_restart_counter()
    a = tools.restart_service()
    b = tools.restart_service()
    print("restart 1st/2nd call success:", a.success, b.success)
    print("health status:", tools.check_service_health().data["status"])
    print("disk used pct:", tools.check_disk_space().data["used_pct"])


FEW_SHOT_PROMPT = (
    "You are an SRE triage agent. Choose exactly one tool from: "
    "check_service_health, restart_service, check_disk_space, none.\n"
    "Example 1 log: No space left on device, used_pct=99.\n"
    'Example 1 answer: {"reasoning": "Disk full", "tool_name": "check_disk_space", '
    '"tool_args": {"mount": "/var/log"}, "resolved": false, "summary": "disk critical"}\n'
    "Example 2 log: service exited code=1 three times in 60s.\n"
    'Example 2 answer: {"reasoning": "Crash loop", "tool_name": "restart_service", '
    '"tool_args": {"service": "notify-worker"}, "resolved": false, "summary": "restarting service"}\n'
    "Now answer for this log: db connection timeout, connection pool exhausted, "
    "health check degraded."
)


def test_plan():
    d = generate(FEW_SHOT_PROMPT, schema=PlanDecision)
    print("TOOL:", d.tool_name)
    print("REASON:", d.reasoning)
    if d.tool_name == "none":
        print("--- fallback triggered; raw model output for diagnostics: ---")
        print(generate(
            "Return ONLY JSON with keys reasoning, tool_name, tool_args, "
            "resolved, summary. Log: db connection timeout, connection pool "
            "exhausted, health check degraded."
        ))


if __name__ == "__main__":
    test_tools()
    print()
    test_plan()