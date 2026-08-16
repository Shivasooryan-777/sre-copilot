"""
Plan stage for SentinelOps Cycle 1.

This module takes an IncidentObservation and asks the local LLM, via
llm_client.generate(), to return a schema-validated PlanDecision.

All retry, JSON extraction, and safe fallback behavior is delegated to
llm_client.generate(), satisfying the Master Prompt requirement that the
agent recovers from invalid LLM output without crashing.
"""

import json
from typing import Any

from .interfaces import (
    IncidentObservation,
    PlanDecision,
    TOOL_SIGNATURES,
)
from .llm_client import generate


VALID_TOOL_NAMES = {
    "check_service_health",
    "restart_service",
    "check_disk_space",
    "none",
}


_FEW_SHOT_EXAMPLES = [
    {
        "incident": """summary: payments-api is timing out
service: payments-api
symptoms: timeout, latency
severity_hint: high""",
        "json": {
            "reasoning": "The incident reports timeouts for payments-api. The safest first action is to verify service health before restarting anything.",
            "tool_name": "check_service_health",
            "tool_args": {
                "service": "payments-api"
            },
            "resolved": False,
            "summary": "Check payments-api health.",
        },
    },
    {
        "incident": """summary: /var/log filesystem is almost full
service: node-filesystem
symptoms: disk
severity_hint: high""",
        "json": {
            "reasoning": "The incident mentions /var/log and disk pressure. The appropriate next tool is check_disk_space.",
            "tool_name": "check_disk_space",
            "tool_args": {
                "mount": "/var/log"
            },
            "resolved": False,
            "summary": "Check disk space on /var/log.",
        },
    },
]


def _tool_signature_block() -> str:
    preferred_order = [
        "check_service_health",
        "restart_service",
        "check_disk_space",
        "none",
    ]

    lines = []

    for name in preferred_order:
        if name == "none":
            lines.append("- none: no tool; use only when resolved or when there is insufficient data")
        elif name in TOOL_SIGNATURES:
            lines.append(f"- {name}: {TOOL_SIGNATURES[name]}")

    return "\n".join(lines)


def _few_shot_examples() -> str:
    blocks = []

    for example in _FEW_SHOT_EXAMPLES:
        incident_text = example["incident"]
        json_text = json.dumps(example["json"], indent=2)

        blocks.append(
            f"""Incident:
{incident_text}

JSON:
{json_text}"""
        )

    return "\n\n".join(blocks)


def _observation_block(observation: IncidentObservation, max_raw_chars: int = 900) -> str:
    raw = observation.raw_text.strip()

    if len(raw) > max_raw_chars:
        raw = raw[:max_raw_chars].rstrip() + "\n...[truncated]"

    symptoms = ", ".join(observation.symptoms) if observation.symptoms else "none"

    return f"""source: {observation.source}
service: {observation.service}
severity_hint: {observation.severity_hint}
symptoms: {symptoms}
summary: {observation.summary}

raw_incident:
{raw}"""


def build_plan_prompt(observation: IncidentObservation) -> str:
    return f"""You are an SRE incident triage agent.
Return ONLY valid JSON.
Do not use markdown.
Do not add comments.
Do not add extra fields.

Choose exactly one next action.

Rules:
- Prefer check_service_health before restart_service for timeouts, crashes, memory issues, or connectivity issues.
- Use check_disk_space when disk, filesystem, storage, inode, or /var/log usage is mentioned.
- Use none only when the incident is already resolved or when there is insufficient data.
- Keep reasoning short.
- resolved must be false unless the incident is already clearly resolved.

JSON schema:
{{
  "reasoning": "string",
  "tool_name": "check_service_health" | "restart_service" | "check_disk_space" | "none",
  "tool_args": {{}},
  "resolved": false,
  "summary": "string"
}}

Tool signatures:
{_tool_signature_block()}

Examples:
{_few_shot_examples()}

Current incident:
{_observation_block(observation)}

Return ONLY valid JSON matching the schema."""


def _normalize_plan(raw: Any, observation: IncidentObservation) -> PlanDecision:
    """
    Normalize the LLM output into a safe PlanDecision.

    This does not replace llm_client's validation. It only makes the final
    decision safer before it is used by later stages.
    """
    if not isinstance(raw, PlanDecision):
        return PlanDecision()

    tool_name = str(raw.tool_name).strip().lower()

    if tool_name not in VALID_TOOL_NAMES:
        tool_name = "none"

    tool_args = raw.tool_args if isinstance(raw.tool_args, dict) else {}
    tool_args = dict(tool_args)

    resolved = bool(raw.resolved)

    # If the model believes the incident is resolved, no further tool is needed.
    if resolved:
        tool_name = "none"
        tool_args = {}

    if tool_name == "none":
        tool_args = {}

    elif tool_name in ("check_service_health", "restart_service"):
        service = str(tool_args.get("service", "")).strip()

        if not service:
            if observation.service and observation.service != "unknown":
                service = observation.service
            else:
                service = "payments-api"

        tool_args = {
            "service": service,
        }

    elif tool_name == "check_disk_space":
        mount = str(tool_args.get("mount", "")).strip()

        if not mount:
            mount = "/var/log"

        tool_args = {
            "mount": mount,
        }

    reasoning = str(raw.reasoning or "").strip() or "No reasoning provided."
    summary = str(raw.summary or "").strip() or "No summary provided."

    return PlanDecision(
        reasoning=reasoning,
        tool_name=tool_name,
        tool_args=tool_args,
        resolved=resolved,
        summary=summary,
    )


def plan(observation: IncidentObservation) -> PlanDecision:
    """
    Plan the next action for one incident observation.

    This always returns a PlanDecision. If the LLM fails repeatedly,
    llm_client.generate() supplies the safe fallback.
    """
    prompt = build_plan_prompt(observation)
    raw_decision = generate(prompt, schema=PlanDecision)
    return _normalize_plan(raw_decision, observation)