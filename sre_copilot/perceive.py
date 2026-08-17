"""
Perceive stage for SentinelOps Cycle 1.

This module reads one incident file and converts it into a structured
IncidentObservation. It is intentionally deterministic and does not call
the LLM.

The LLM is only used in the Plan stage.
"""

import re
from pathlib import Path
from typing import List, Union

from .interfaces import IncidentObservation


SERVICE_PATTERNS = [
    r"service\s*[:=]\s*([A-Za-z0-9._-]+)",
    r"affected service\s*[:=]\s*([A-Za-z0-9._-]+)",
    r"component\s*[:=]\s*([A-Za-z0-9._-]+)",
    r"app\s*[:=]\s*([A-Za-z0-9._-]+)",
    r"application\s*[:=]\s*([A-Za-z0-9._-]+)",
]

_SVC_KEY_VALUE_PATTERNS = [
    r"\bsvc=(?P<svc>[A-Za-z0-9_.-]+)",
    r"\bservice=(?P<svc>[A-Za-z0-9_.-]+)",
    r"\bservice_name=(?P<svc>[A-Za-z0-9_.-]+)",
    r"\bservice:\s*(?P<svc>[A-Za-z0-9_.-]+)",
]

FILENAME_SERVICE_HINTS = {
    "db": "database",
    "database": "database",
    "postgres": "database",
    "mysql": "database",
    "memory": "payments-api",
    "disk": "node-filesystem",
    "log": "node-filesystem",
    "crash": "payments-api",
    "api": "payments-api",
}


SYMPTOM_RULES = [
    (r"time\s*out|timeout|timed out|deadline exceeded", "timeout"),
    (r"memory|oom|out of memory|rss|heap", "memory"),
    (r"disk|filesystem|no space left|/var/log|storage|inode", "disk"),
    (r"crash|crash loop|restart loop|core dump|segfault|panic", "crash"),
    (r"latency|slow|degraded", "latency"),
    (r"connection refused|connection reset|5xx|503|502", "connectivity"),
]


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _extract_service(text: str) -> str:
    for pattern in _SVC_KEY_VALUE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group("svc").strip()

    for pattern in SERVICE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            for group in match.groups():
                if group:
                    return group.strip()

    return ""

def _infer_service_from_filename(stem: str) -> str:
    lowered = stem.lower()

    for hint, service in FILENAME_SERVICE_HINTS.items():
        if hint in lowered:
            return service

    return "unknown"


def _extract_symptoms(text: str) -> List[str]:
    lowered = text.lower()
    symptoms: List[str] = []

    for pattern, symptom in SYMPTOM_RULES:
        if re.search(pattern, lowered):
            if symptom not in symptoms:
                symptoms.append(symptom)

    return symptoms


def _extract_severity(text: str, symptoms: List[str]) -> str:
    lowered = text.lower()

    critical_markers = [
        "critical",
        "fatal",
        "down",
        "outage",
        "crash loop",
        "oom",
        "out of memory",
        "no space left",
    ]

    high_markers = [
        "timeout",
        "latency",
        "high",
        "full",
        "failed",
        "error",
        "degraded",
        "restart",
    ]

    if any(marker in lowered for marker in critical_markers):
        return "critical"

    if any(marker in lowered for marker in high_markers):
        return "high"

    if symptoms:
        return "medium"

    return "unknown"


def _summarize(text: str, max_chars: int = 300) -> str:
    first_line = _first_nonempty_line(text)

    if not first_line:
        return "No summary available."

    if len(first_line) > max_chars:
        return first_line[:max_chars].rstrip() + "..."

    return first_line


def perceive(incident_path: Union[str, Path]) -> IncidentObservation:
    """
    Read and parse one incident file.

    This never crashes the agent loop. If the file cannot be read, it returns
    a safe default observation.
    """
    path = Path(incident_path)
    source = str(path)

    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        return IncidentObservation.safe_default(
            source=source,
            raw_text=f"read_error: {exc}",
        )

    if not raw_text:
        return IncidentObservation.safe_default(source=source)

    service = _extract_service(raw_text) or _infer_service_from_filename(path.stem)
    symptoms = _extract_symptoms(raw_text)
    severity_hint = _extract_severity(raw_text, symptoms)
    summary = _summarize(raw_text)

    return IncidentObservation(
        source=source,
        raw_text=raw_text,
        service=service,
        symptoms=symptoms,
        severity_hint=severity_hint,
        summary=summary,
    )