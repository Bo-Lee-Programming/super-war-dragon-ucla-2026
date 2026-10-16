"""Free, autonomous, deterministic Red Alert baseline for UCLA AltruAgent.

No external model calls, accounts, gameplay exploits, hidden information,
or paid inference. This is an OFFLINE-TESTED CANDIDATE, not a winning agent.
Launch after official registration:
    python -m agent --match --agent examples.free_rule_agent
Tournament day:
    python -m agent --tournament --agent examples.free_rule_agent
Never publish or enter an official match without owner authorization.
"""
from __future__ import annotations

from typing import Any
from altruagent import WAIT, WithReasoning

def dic(value: Any) -> dict:
    return value if isinstance(value, dict) else {}

def rows(value: Any) -> list[dict]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []

def names(value: Any) -> set[str]:
    return {str(x).lower() for x in value} if isinstance(value, list) else set()

def tick_of(raw: dict) -> int:
    tick = dic(raw.get("observation")).get("tick", 0)
    return tick if type(tick) is int and tick >= 0 else 0

def typed(actors: list[dict]) -> set[str]:
    return {str(x.get("type") or "").lower() for x in actors}

def queue_items(queued: list[dict], kind: str | None = None) -> set[str]:
    return {
        str(x.get("item") or "").lower() for x in queued
        if kind is None or str(x.get("queue") or "").lower() == kind.lower()
    }

def produce_ready(queued: list[dict]) -> list[str]:
    return [
        str(x.get("item")).lower() for x in queued
        if x.get("ready") is True
        and str(x.get("queue") or "").lower() in {"building", "defense"}
        and isinstance(x.get("item"), str)
    ]

class FreeRuleAgent:
    """One independent copy per match, with state-based and time-based guards."""

    def __init__(self) -> None:
        self.last_tick_by_action: dict[str, int] = {}
        self.errors: dict[str, int] = {}
        self.last_sent: list[dict] = []

    def _once_per(self, label: str, tick: int, span: int) -> bool:
        previous = self.last_tick_by_action.get(label)
        # if a new round or replay resets tick numbers, let a new action run
        if previous is not None and tick >= previous and tick - previous < span:
            return False
        self.last_tick_by_action[label] = tick
        return True

    def _send(self, orders: list[dict], note: str):
        if not orders:
            return WAIT
        self.last_sent = list(orders[:20])
        return WithReasoning(
            {"type": "orders", "orders": self.last_sent},
            note[:240],
        )

    def choose_action(self, state, context):
        if context.game_type != "red_alert":
            # This entry is focused on the user's confirmed Red Alert track.
            # Honor of Kings has no published interface as of Oct 12.
            if state.legal_actions:
                return state.legal_actions[0]
            return WAIT

        raw = dic(getattr(state, "raw", None))
        obs = dic(raw.get("observation"))
        if not obs or raw.get("phase") not in ("playing", None):
            return WAIT

        t = tick_of(raw)
        own_units = rows(obs.get("units"))
        buildings = rows(obs.get("buildings"))
        queues = rows(obs.get("production"))
        legal = dic(raw.get("legal_actions"))
        available_build = names(legal.get("build"))
        available_train = names(legal.get("train"))
        unit_kinds = typed(own_units)
        built = typed(buildings)
        queued = queue_items(queues)
        economy = dic(obs.get("economy"))
        cash = economy.get("cash", 0)
        power_provided = economy.get("power_provided", 0)
        power_drained = economy.get("power_drained", 0)
        cash = cash if isinstance(cash, (int, float)) else 0
        power_provided = power_provided if isinstance(power_provided, (int, float)) else 0
        power_drained = power_drained if isinstance(power_drained, (int, float)) else 0

        # (1) Deploy MCV only when there is no Construction Yard.
        if "fact" not in built and "mcv" in unit_kinds:
            mcvs = [x.get("id") for x in own_units
                    if str(x.get("type") or "").lower() == "mcv"
                    and type(x.get("id")) is int]
            if mcvs and self._once_per("deploy", t, 45):
                return self._send([{"cmd": "deploy", "units": [mcvs[0]]}],
                                  "Establish a construction yard before producing buildings.")
            return WAIT

        # (2) Place completed structures; cannot produce the next prerequisite without them.
        ready = produce_ready(queues)
        for item in ready:
            if self._once_per("place:"+item, t, 60):
                return self._send([{"cmd": "place", "item": item}],
                                  "Place a completed structure near the existing base.")

        # (3) Balanced opener. The legal list is authoritative; never guess a product code.
        low_power = power_drained + 30 > power_provided
        desired = []
        if low_power or "powr" not in built:
            desired.append("powr")
        if "proc" not in built:
            desired.append("proc")
        if "tent" not in built and "barr" not in built:
            desired.extend(("tent", "barr"))
        if "weap" not in built:
            desired.append("weap")
        if cash >= 3500 and len([b for b in buildings if b.get("type") == "proc"]) < 2:
            desired.append("proc")

        # Do not issue repeated build calls if the item is already queued.
        for item in desired:
            if item in queued or item not in available_build:
                continue
            if self._once_per("build:"+item, t, 85):
                return self._send([{"cmd": "build", "item": item}],
                                  "Grow the economy and production while avoiding duplicate queues.")

        # (4) Issue combat orders only if the server provides a ready-to-send command.
        # This uses the participant's legal observation, not a spectator/map cheat.
        combat = [u for u in own_units if str(u.get("type") or "").lower()
                  not in {"mcv", "harv", "harvester", "miner"}]
        suggested = legal.get("attack_now")
        if len(combat) >= 5 and isinstance(suggested, dict) and suggested.get("cmd") == "attack_move":
            if self._once_per("attack_now", t, 150):
                return self._send([suggested],
                                  "Advance available combat units toward a legal target.")

        # (5) Keep basic combat production going using listed trainable units.
        infantry_queue = [p for p in queues if str(p.get("queue") or "").lower() == "infantry"]
        vehicle_queue = [p for p in queues if str(p.get("queue") or "").lower() == "vehicle"]
        candidates = []
        for item in ("3tnk", "2tnk", "1tnk"):
            if item in available_train and len(vehicle_queue) < 3 and cash >= 1000:
                candidates.append((item, 1, "vehicle"))
                break
        if "e1" in available_train and len(infantry_queue) < 3 and cash >= 300:
            candidates.append(("e1", 3, "infantry"))
        for item, count, category in candidates:
            if self._once_per("train:"+category, t, 90):
                return self._send([{"cmd": "train", "item": item, "count": count}],
                                  "Increase unit count while keeping the economy active.")

        # If no production/attack needed, wait briefly for an updated game state.
        return WAIT

    def on_action_result(self, result, context):
        """Capture refusals in local memory, without leaking keys or logs."""
        if isinstance(result, dict) and result.get("accepted") is False:
            label = str(result.get("error") or "unknown")[:64]
            self.errors[label] = self.errors.get(label, 0) + 1

def create_agent():
    return FreeRuleAgent()
