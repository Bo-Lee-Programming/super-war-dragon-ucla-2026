"""Write-only, per-seat local records for competition compliance and debugging.

Records never become policy input. They contain only this seat's delivered
state, proposed actions and action results, with credential-like fields removed.
Do not commit or publish .local_runtime, which may include private role data.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

from altruagent import SendMessage, WithReasoning, WAIT, TERMINATE_MESSAGING


_SECRET_FIELD = re.compile(r"key|token|secret|password|authorization|cookie|url", re.I)
_SECRET_VALUE = re.compile(r"(?:eak_live_[0-9a-fA-F]+|Bearer\s+\S+|sk-[A-Za-z0-9_-]{12,})")


def clean(value):
    if isinstance(value, dict):
        return {str(k): "[redacted]" if _SECRET_FIELD.search(str(k)) else clean(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[redacted]", value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, WithReasoning):
        return {"action": clean(value.action), "reasoning_summary": clean(value.reasoning_summary)}
    if isinstance(value, SendMessage):
        return {"content": clean(value.content), "recipients": value.recipients}
    if is_dataclass(value):
        return clean(asdict(value))
    return {"type": type(value).__name__}


class AuditedAgent:
    def __init__(self, policy, directory=None):
        self.policy = policy
        self.directory = Path(directory or os.environ.get("ALTRUAGENT_AUDIT_DIR", ".local_runtime/records"))
        self._warned = False
        self._last_wait = float("-inf")
        self._last_message_end = None

    def _write(self, event, context, **data):
        try:
            session = re.sub(r"[^A-Za-z0-9_-]", "_", str(context.session_id))[:100]
            seat = getattr(context, "seat_position", None)
            # No reads, shared tactical cache, or cross-seat aggregation.
            path = self.directory / f"{session}_seat_{seat}_{os.getpid()}.jsonl"
            self.directory.mkdir(parents=True, exist_ok=True)
            entry = {"time": datetime.now(timezone.utc).isoformat(), "event": event,
                     "game": getattr(context, "game_type", None), "seat": seat, **data}
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(clean(entry), ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError):
            # Disk trouble must not alter an otherwise legal game decision.
            if not self._warned:
                print("Local decision audit unavailable; autonomous play continues.", flush=True)
                self._warned = True

    def choose_action(self, state, context):
        decision = self.policy.choose_action(state, context)
        if decision is WAIT:
            if time.monotonic() - self._last_wait >= 30:
                self._write("wait_sample", context, state_version=getattr(state, "state_version", None))
                self._last_wait = time.monotonic()
            return decision
        self._write("decision", context, state=getattr(state, "raw", {}),
                    messages=getattr(state, "new_messages", []), decision=decision)
        return decision

    def choose_message(self, state, context):
        decision = self.policy.choose_message(state, context)
        if decision is TERMINATE_MESSAGING:
            marker = (context.session_id, getattr(state, "state_version", None))
            if marker == self._last_message_end:
                return decision
            self._last_message_end = marker
        self._write("message", context, state=getattr(state, "raw", {}),
                    messages=getattr(state, "new_messages", []), decision=decision)
        return decision

    def on_action_result(self, result, context):
        self._write("result", context, result=result)
        callback = getattr(self.policy, "on_action_result", None)
        if callable(callback):
            callback(result, context)
