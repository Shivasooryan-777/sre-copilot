"""Single source of truth for shared data shapes in sre-copilot.

All Pydantic schemas and tool contracts live here so two sessions never
invent two different shapes for the same thing.
"""
from __future__ import annotations


from typing import List

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field

TOOL_NAMES = Literal[
    "check_service_health",
    "restart_service",
    "check_disk_space",
    "none",
]


class PlanDecision(BaseModel):
    """Structured output expected from the LLM in the Plan stage."""

    reasoning: str = Field(
        default="LLM output could not be parsed; escalating.",
        description="Short explanation of why this action was chosen.",
    )
    tool_name: TOOL_NAMES = Field(
        default="none",
        description="Which tool to run next, or 'none' if no action is needed.",
    )
    tool_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the chosen tool.",
    )
    resolved: bool = Field(
        default=False,
        description="True if the incident is considered resolved after this step.",
    )
    summary: str = Field(
        default="insufficient data - escalate to human",
        description="Human-readable status summary.",
    )


class ToolResult(BaseModel):
    """Uniform result envelope returned by every tool."""

    tool_name: str
    success: bool
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)

class IncidentObservation(BaseModel):
    """
    Structured output of the Perceive stage.

    This is the agent's deterministic view of the incident file before
    asking the LLM for a plan.
    """

    source: str = ""
    raw_text: str = ""
    service: str = "unknown"
    symptoms: List[str] = []
    severity_hint: str = "unknown"
    summary: str = ""

    @classmethod
    def safe_default(cls, source: str = "", raw_text: str = "") -> "IncidentObservation":
        return cls(
            source=source,
            raw_text=raw_text[:1000],
            service="unknown",
            symptoms=[],
            severity_hint="unknown",
            summary="Perception unavailable or insufficient data.",
        )

TOOL_SIGNATURES: Dict[str, str] = {
    "check_service_health": (
        "check_service_health(service: str = 'payments-api') -> ToolResult; "
        "returns current health status (ok / degraded / down)."
    ),
    "restart_service": (
        "restart_service(service: str) -> ToolResult; restarts a service. "
        "Simulated to fail on the FIRST call for failure-recovery testing."
    ),
    "check_disk_space": (
        "check_disk_space(mount: str = '/var/log') -> ToolResult; "
        "returns disk usage percentage for a mount point."
    ),
}