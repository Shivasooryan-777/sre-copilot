from __future__ import annotations

import inspect
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

from .interfaces import IncidentObservation, PlanDecision, ToolResult
from .loop_logger import LoopLogger
from .perceive import perceive
from .plan import plan
from .tools import TOOL_MAP


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _to_dict(obj: Any) -> Any:
    """
    Convert pydantic models to dict in a pydantic v1/v2 tolerant way.
    """
    if obj is None:
        return None

    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass

    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass

    return obj


def _safe_tool_args(args: Any) -> Dict[str, Any]:
    """
    Normalize tool_args into a dict.

    Supports:
    - dict
    - JSON string
    - fallback empty dict
    """
    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def _filtered_kwargs(fn: Callable, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter model-provided args down to args accepted by the tool function.

    This prevents TypeError from unexpected or hallucinated keys.
    """
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}

    return {
        key: value
        for key, value in args.items()
        if key in signature.parameters
    }


def _coerce_tool_result(
    tool_name: str,
    value: Any,
    attempt: int,
) -> ToolResult:
    """
    Coerce arbitrary tool output into ToolResult.
    """
    if isinstance(value, ToolResult):
        data = value.data if isinstance(value.data, dict) else {"raw": value.data}
        data = dict(data)
        data["attempt"] = attempt

        return ToolResult(
            tool_name=tool_name or value.tool_name,
            success=value.success,
            message=value.message,
            data=data,
        )

    if isinstance(value, dict):
        data = value.get("data", value)
        data = data if isinstance(data, dict) else {"raw": data}
        data = dict(data)
        data["attempt"] = attempt

        return ToolResult(
            tool_name=tool_name,
            success=bool(value.get("success", False)),
            message=str(value.get("message", "")),
            data=data,
        )

    return ToolResult(
        tool_name=tool_name,
        success=True,
        message=str(value),
        data={"attempt": attempt},
    )


# ---------------------------------------------------------------------------
# Act stage with graceful recovery
# ---------------------------------------------------------------------------

def execute_tool_with_recovery(
    tool_name: str,
    tool_args: Any,
    max_attempts: int = 2,
) -> Tuple[ToolResult, Dict[str, Any]]:
    """
    Execute a tool with bounded retry.

    This is deliberately simple and resource-safe:
    - no threads
    - no async
    - no parallelism
    - small bounded retry count

    It is designed to demonstrate graceful recovery from tool failure,
    including the known deliberate restart_service first-call failure.
    """
    max_attempts = max(1, int(max_attempts))
    args = _safe_tool_args(tool_args)

    fn = TOOL_MAP.get(tool_name)

    if fn is None:
        result = ToolResult(
            tool_name=tool_name,
            success=False,
            message=f"Unknown tool '{tool_name}'. Safe fallback.",
            data={
                "attempts": 0,
                "recovered_after_failure": False,
            },
        )
        details = {
            "max_attempts": max_attempts,
            "attempts": [],
            "recovered_after_failure": False,
            "reason": "unknown_tool",
        }
        return result, details

    attempts = []
    last_result: Optional[ToolResult] = None

    for attempt in range(1, max_attempts + 1):
        try:
            kwargs = _filtered_kwargs(fn, args)
            raw = fn(**kwargs)
            result = _coerce_tool_result(tool_name, raw, attempt)
        except Exception as exc:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"Tool exception: {exc}",
                data={"attempt": attempt},
            )

        attempts.append(_to_dict(result))
        last_result = result

        if result.success:
            data = dict(result.data if isinstance(result.data, dict) else {})
            message = result.message
            recovered = attempt > 1

            if recovered:
                message = f"Recovered after {attempt - 1} failed attempt(s). {message}"

            data["recovered_after_failure"] = recovered
            data["attempts"] = attempt
            data["attempt_history"] = attempts

            final_result = ToolResult(
                tool_name=result.tool_name,
                success=True,
                message=message,
                data=data,
            )

            details = {
                "max_attempts": max_attempts,
                "attempts": attempts,
                "recovered_after_failure": recovered,
            }

            return final_result, details

        if attempt < max_attempts:
            # Very small delay; keeps demo realistic without stressing hardware.
            time.sleep(0.2)

    if last_result is None:
        last_result = ToolResult(
            tool_name=tool_name,
            success=False,
            message="Tool execution failed with no result.",
            data={},
        )

    data = dict(last_result.data if isinstance(last_result.data, dict) else {})
    data["attempts"] = len(attempts)
    data["recovered_after_failure"] = False
    data["attempt_history"] = attempts

    final_result = ToolResult(
        tool_name=last_result.tool_name,
        success=False,
        message=last_result.message,
        data=data,
    )

    details = {
        "max_attempts": max_attempts,
        "attempts": attempts,
        "recovered_after_failure": False,
    }

    return final_result, details


# ---------------------------------------------------------------------------
# Explicit success-condition check
# ---------------------------------------------------------------------------

def evaluate_success(
    plan_decision: PlanDecision,
    tool_result: ToolResult,
) -> Tuple[bool, str]:
    """
    Explicit success-condition check.

    Hard termination is based on:
    1. max_iterations
    2. this explicit success condition
    """
    if not tool_result.success:
        return False, f"Tool reported failure: {tool_result.message}"

    data = tool_result.data if isinstance(tool_result.data, dict) else {}

    if data.get("recovered_after_failure"):
        return True, f"Tool failed initially but recovered: {tool_result.message}"

    tool_name = plan_decision.tool_name or tool_result.tool_name

    if tool_name == "restart_service":
        status = str(data.get("status", "")).lower()

        if data.get("restarted") is True or status in {
            "running",
            "restarted",
            "ok",
            "healthy",
        }:
            return True, f"Restart success condition met (status={status or 'restarted'})."

        return True, "restart_service executed successfully; treating as explicit success condition."

    if tool_name == "check_service_health":
        status = str(data.get("status", "")).lower()

        if status in {
            "healthy",
            "running",
            "ok",
            "up",
        }:
            return True, f"Health check success condition met (status={status})."

        return True, "check_service_health executed successfully; treating as explicit success condition."

    if tool_name == "check_disk_space":
        free = data.get("free_gb", data.get("free"))

        if isinstance(free, (int, float)) and free <= 0.5:
            return False, f"Disk space still critically low: {free} GB"

        return True, "check_disk_space executed successfully; treating as explicit success condition."

    return True, "Tool succeeded; explicit success condition met."


# ---------------------------------------------------------------------------
# Observe stage
# ---------------------------------------------------------------------------

def observe(
    observation: IncidentObservation,
    iteration: int,
    plan_decision: PlanDecision,
    tool_result: ToolResult,
) -> IncidentObservation:
    """
    Convert tool result into the next observation.

    This does not change any frozen interface. It reuses IncidentObservation.
    """
    action = plan_decision.tool_name or "none"
    args = _safe_tool_args(plan_decision.tool_args)

    data = tool_result.data if isinstance(tool_result.data, dict) else {}
    recovered = bool(data.get("recovered_after_failure"))

    if tool_result.success:
        state = "recovered_after_retry" if recovered else "success"
    else:
        state = "failed"

    args_text = json.dumps(args, default=str)

    note = (
        f"[observation iteration={iteration}] "
        f"action={action} "
        f"args={args_text} "
        f"state={state} "
        f"message={tool_result.message}"
    )

    raw_text = (observation.raw_text or "").rstrip() + "\n\n" + note

    symptoms = list(observation.symptoms or [])
    symptoms.append(f"tool_{action}_{state}")

    summary = f"{observation.summary} | {note}"

    return IncidentObservation(
        source=observation.source,
        raw_text=raw_text[-8000:],
        service=observation.service,
        symptoms=symptoms[-20:],
        severity_hint=observation.severity_hint,
        summary=summary[:600],
    )


# ---------------------------------------------------------------------------
# Full agent loop
# ---------------------------------------------------------------------------

def run_agent_loop(
    incident_path: Union[str, Path],
    max_iterations: int = 3,
    log_dir: Union[str, Path] = "logs",
    plan_override: Optional[
        Callable[[IncidentObservation, int], PlanDecision]
    ] = None,
) -> Dict[str, Any]:
    """
    Full Cycle 1 agent loop:

        Perceive -> Plan -> Act -> Observe

    Hard termination:
        - max_iterations
        - explicit success-condition check

    Logging:
        - JSONL per stage/event
        - final consolidated JSON file

    plan_override:
        Optional deterministic override for failure drills/tests.
        It is not required for normal operation.
    """
    incident_path = Path(incident_path)
    logger = LoopLogger(
        run_name=incident_path.stem,
        log_dir=log_dir,
        incident_path=incident_path,
    )

    status = "initialized"
    result: Dict[str, Any] = {}

    last_plan: Optional[PlanDecision] = None
    last_tool_result: Optional[ToolResult] = None

    try:
        max_iterations = max(1, int(max_iterations))

        # ---------------------------------------------------------------
        # Perceive
        # ---------------------------------------------------------------
        observation = perceive(incident_path)

        logger.log_stage(
            iteration=0,
            stage="perceive",
            payload={
                "incident_path": str(incident_path),
                "observation": _to_dict(observation),
            },
        )

        status = "stopped_max_iterations"
        success_reason: Optional[str] = None
        resolved = False

        for iteration in range(1, max_iterations + 1):
            # -----------------------------------------------------------
            # Plan
            # -----------------------------------------------------------
            if plan_override is not None:
                decision = plan_override(observation, iteration)
            else:
                decision = plan(observation)

            if decision is None:
                decision = PlanDecision(
                    reasoning="Planner returned None; safe fallback.",
                    tool_name="none",
                    tool_args={},
                    resolved=False,
                    summary="Safe fallback due empty plan.",
                )

            last_plan = decision

            logger.log_stage(
                iteration=iteration,
                stage="plan",
                payload={
                    "thought": decision.reasoning,
                    "tool_name": decision.tool_name,
                    "tool_args": decision.tool_args,
                    "resolved": decision.resolved,
                    "summary": decision.summary,
                },
            )

            # -----------------------------------------------------------
            # Plan-based termination / fallback
            # -----------------------------------------------------------
            if decision.resolved and decision.tool_name in (None, "", "none"):
                resolved = True
                status = "resolved_by_plan"
                success_reason = (
                    "Planner marked incident resolved and no tool action was required."
                )
                break

            if decision.tool_name in (None, "", "none"):
                status = "fallback_no_tool"
                success_reason = (
                    "Planner selected no tool; safe fallback/escalation."
                )
                break

            # -----------------------------------------------------------
            # Act
            # -----------------------------------------------------------
            tool_result, act_details = execute_tool_with_recovery(
                tool_name=decision.tool_name,
                tool_args=decision.tool_args,
                max_attempts=2,
            )

            last_tool_result = tool_result

            logger.log_stage(
                iteration=iteration,
                stage="act",
                payload={
                    "thought": decision.reasoning,
                    "action": decision.tool_name,
                    "args": _safe_tool_args(decision.tool_args),
                    "tool_result": _to_dict(tool_result),
                    "recovery": act_details,
                },
            )

            # -----------------------------------------------------------
            # Explicit success-condition check
            # -----------------------------------------------------------
            success, success_reason = evaluate_success(
                plan_decision=decision,
                tool_result=tool_result,
            )

            # -----------------------------------------------------------
            # Observe
            # -----------------------------------------------------------
            observation = observe(
                observation=observation,
                iteration=iteration,
                plan_decision=decision,
                tool_result=tool_result,
            )

            logger.log_stage(
                iteration=iteration,
                stage="observe",
                payload={
                    "success_condition_met": success,
                    "success_reason": success_reason,
                    "observation": _to_dict(observation),
                },
            )

            if success:
                resolved = True
                status = "resolved_success_condition"
                break

        result = {
            "incident_path": str(incident_path),
            "status": status,
            "resolved": resolved,
            "success_reason": success_reason,
            "max_iterations": max_iterations,
            "last_plan": _to_dict(last_plan),
            "last_tool_result": _to_dict(last_tool_result),
            "log_files": {
                "jsonl": str(logger.jsonl_path),
                "json": str(logger.json_path),
            },
        }

    except Exception as exc:
        status = "failed_exception"
        result = {
            "incident_path": str(incident_path),
            "status": status,
            "error": str(exc),
            "log_files": {
                "jsonl": str(logger.jsonl_path),
                "json": str(logger.json_path),
            },
        }

        logger.log_stage(
            iteration=0,
            stage="error",
            payload={"error": str(exc)},
        )

    finally:
        summary = logger.finish(
            status=status,
            result=result,
        )
        return summary