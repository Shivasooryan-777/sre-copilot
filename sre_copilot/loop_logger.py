from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union


class LoopLogger:
    """
    JSONL + JSON logger for the Perceive -> Plan -> Act -> Observe loop.

    Writes:
    - logs/<run_id>.jsonl : append-safe event stream, one JSON object per event
    - logs/<run_id>.json  : final consolidated strict JSON run report

    This satisfies both:
    - Session 2 intent: one JSON line per stage/event
    - Session 3 intent: final JSON file for the run
    """

    def __init__(
        self,
        run_name: str,
        log_dir: Union[str, Path] = "logs",
        incident_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in str(run_name)
        )

        self.run_id = f"{safe_name}_{timestamp}_{uuid.uuid4().hex[:6]}"
        self.jsonl_path = self.log_dir / f"{self.run_id}.jsonl"
        self.json_path = self.log_dir / f"{self.run_id}.json"

        self.started_at = datetime.now(timezone.utc).isoformat()
        self.incident_path = str(incident_path) if incident_path else None
        self.events = []

        self._append_jsonl(
            {
                "type": "run_start",
                "run_id": self.run_id,
                "started_at": self.started_at,
                "incident_path": self.incident_path,
            }
        )

    def _append_jsonl(self, event: Dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_stage(
        self,
        iteration: int,
        stage: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Log one stage event.

        Expected stages:
        - perceive
        - plan
        - act
        - observe
        - error
        """
        event = {
            "type": "stage",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "iteration": iteration,
            "stage": stage,
            "payload": payload,
        }

        self.events.append(event)
        self._append_jsonl(event)

    def finish(
        self,
        status: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Write final consolidated JSON report and return it.
        """
        ended_at = datetime.now(timezone.utc).isoformat()

        iteration_values = [
            event.get("iteration", 0)
            for event in self.events
            if isinstance(event.get("iteration"), int)
        ]
        iterations = max(iteration_values + [0])

        summary = {
            "type": "run_summary",
            "run_id": self.run_id,
            "incident_path": self.incident_path,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "status": status,
            "iterations": iterations,
            "result": result,
            "events": self.events,
        }

        self._append_jsonl(summary)

        self.json_path.write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )

        return summary