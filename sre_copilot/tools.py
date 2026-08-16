"""Stub tools for Cycle 1 Session 1.

Realistic mock returns so the agent loop (Session 2+) can be built before
wiring real infrastructure. restart_service deliberately fails on its FIRST
call per process to demonstrate recovery from tool failure without crashing.
"""

from __future__ import annotations

from .interfaces import ToolResult

_restart_attempts = 0


def check_service_health(service: str = "payments-api") -> ToolResult:
    return ToolResult(
        tool_name="check_service_health",
        success=True,
        message=f"{service} is degraded: db unreachable, latency spikes.",
        data={"service": service, "status": "degraded", "latency_ms": 4200, "db": "unreachable"},
    )


def check_disk_space(mount: str = "/var/log") -> ToolResult:
    return ToolResult(
        tool_name="check_disk_space",
        success=True,
        message=f"disk on {mount} is at 98% - critical.",
        data={"mount": mount, "used_pct": 98},
    )


def restart_service(service: str = "payments-api") -> ToolResult:
    global _restart_attempts
    _restart_attempts += 1
    if _restart_attempts == 1:
        return ToolResult(
            tool_name="restart_service",
            success=False,
            message=(
                f"restart of {service} failed: connection refused by supervisor "
                "(simulated transient failure - retry once)."
            ),
            data={"service": service, "attempt": _restart_attempts},
        )
    return ToolResult(
        tool_name="restart_service",
        success=True,
        message=f"{service} restarted successfully on attempt {_restart_attempts}.",
        data={"service": service, "attempt": _restart_attempts, "status": "running"},
    )


def reset_restart_counter() -> None:
    """Test helper: make the next restart_service call fail again."""
    global _restart_attempts
    _restart_attempts = 0


TOOL_MAP = {
    "check_service_health": check_service_health,
    "restart_service": restart_service,
    "check_disk_space": check_disk_space,
}