"""Super War Dragon: zero-paid-inference multi-game tournament candidate.

Contestant-facing observations only. Red Alert uses the separately-tested
FreeRuleAgent. Pokemon constructs genuinely valid structured decisions instead
of returning the server's *template*. Werewolf uses legal seat actions.
NOT an official Testing match, registered agent, or proven competitive policy.
"""
from __future__ import annotations

import json
from typing import Any

from altruagent import TERMINATE_MESSAGING, SendMessage
from examples.free_rule_agent import FreeRuleAgent
from examples import smoke_agent


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _observation(raw: dict) -> dict:
    value = raw.get("observation")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return _dict(value)


def _template(state, kind: str) -> dict:
    if not state.legal_actions or state.legal_actions[0].action_id != kind:
        return {}
    return _dict(_dict(state.legal_actions[0].input).get("action"))


def _pokemon_option_score(option: dict) -> float:
    if option.get("type") == "pass":
        return -1000
    if option.get("type") == "switch":
        return -100
    if option.get("type") != "move":
        return -1000
    name = str(option.get("move_id", "")).lower().replace("-", "")
    if name in {"protect", "detect", "endure", "wideguard", "quickguard"}:
        return 4
    if name in {"sleeppowder", "spore", "thunderwave", "icywind",
                "tailwind", "trickroom", "fakeout"}:
        return 24
    if name in {"helpinghand", "followme", "ragepowder"}:
        return 9
    power = option.get("base_power", option.get("power", 0))
    power = power if isinstance(power, (float, int)) and not isinstance(power, bool) else 0
    # Most live templates give only move_id and targets. Favor actual attacks
    # over unknowable type-specific theory, especially with a short timer.
    score = 15 + min(max(power, 0), 180) / 8
    if name in {"struggle", "splash", "celebrate"}:
        score = -10
    return score


def _best_target(option: dict):
    targets = option.get("targets") or []
    if not isinstance(targets, list):
        targets = []
    if not targets:
        return None
    described = option.get("target_options")
    if isinstance(described, list):
        for t in described:
            if isinstance(t, dict) and t.get("side") == "opponent" and t.get("target") in targets:
                return t["target"]
    return next((target for target in targets if type(target) is int and target > 0), targets[0])


def _pokemon_doubles(state):
    template = _template(state, "doubles_turn")
    # The SDK's official example is the syntax-safe fallback, used whenever
    # the server changes its template shape unexpectedly.
    fallback = smoke_agent.choose_action(state, None)
    slots = template.get("slots")
    if not isinstance(slots, list) or len(slots) != 2:
        return fallback
    by_slot = {}
    for index, entry in enumerate(slots):
        if not isinstance(entry, dict):
            return fallback
        number = entry.get("slot", index)
        if type(number) is not int or number not in (0, 1) or number in by_slot:
            return fallback
        by_slot[number] = entry.get("options")
    if set(by_slot) != {0, 1} or not all(isinstance(by_slot[i], list) for i in (0, 1)):
        return fallback
    decisions = []
    already_switched = set()
    for slot in (0, 1):
        options = by_slot[slot]
        ranked = sorted((o for o in options if isinstance(o, dict)),
                        key=_pokemon_option_score, reverse=True)
        chosen = None
        for o in ranked:
            kind = o.get("type")
            if kind == "move":
                move = o.get("move_id")
                if not isinstance(move, str) or not move:
                    continue
                target = _best_target(o)
                name = move.lower().replace("-", "")
                # Never attack own teammate merely because it is legal.
                supportive = name in {"helpinghand", "healpulse", "pollenpuff", "coaching"}
                if target is not None and type(target) is int and target < 0 and not supportive:
                    continue
                chosen = {"type": "move", "move_id": move}
                if target is not None:
                    chosen["target"] = target
                break
            if kind == "switch":
                species = o.get("species")
                if isinstance(species, str) and species and species not in already_switched:
                    chosen = {"type": "switch", "species": species}
                    already_switched.add(species)
                    break
            if kind == "pass":
                chosen = {"type": "pass"}
                break
        if chosen is None:
            return fallback
        decisions.append(chosen)
    if decisions[0]["type"] == decisions[1]["type"] == "pass":
        return fallback
    return {"type": "doubles_turn", "slot_0": decisions[0], "slot_1": decisions[1]}


def _pokemon_lineup(state):
    template = _template(state, "select_lineup")
    roster = template.get("roster")
    if (not isinstance(roster, list) or
            not all(isinstance(species, str) and species for species in roster) or
            len(set(roster)) < 4):
        return smoke_agent.choose_action(state, None)
    # Prefer unique species, preserve the official server roster IDs.
    picked = list(dict.fromkeys(roster))[:4]
    return {"type": "select_lineup", "bring": picked, "leads": picked[:2]}


def _seer_wolves(obs: dict) -> set[int]:
    # Only player-observed inspections, never engine-hidden role lists.
    known = set()
    for key in ("investigations", "seer_results", "checks", "results"):
        data = obs.get(key)
        if isinstance(data, dict):
            data = [{"player": k, "role": v} for k, v in data.items()]
        if not isinstance(data, list):
            continue
        for r in data:
            if not isinstance(r, dict):
                continue
            if str(r.get("role", r.get("result", ""))).lower() != "wolf":
                continue
            target = r.get("seat", r.get("player", r.get("position")))
            if isinstance(target, str) and target.lower().startswith("player"):
                target = target[6:]
            if str(target).isdigit():
                known.add(int(target))
    return known


def _werewolf_action(state):
    actions = state.legal_actions
    if not actions:
        return smoke_agent.choose_action(state, None)
    raw = _dict(getattr(state, "raw", None))
    obs = _observation(raw)
    game = _dict(raw.get("game_state"))
    phase = game.get("phase")
    our_role = str(obs.get("role", obs.get("your_role", ""))).lower()
    me = raw.get("your_position")
    legal = {int(a.action_id): a for a in actions if str(a.action_id).isdigit()}
    if not legal:
        return actions[0]
    abstain = legal.get(7)
    eligible = {n: a for n, a in legal.items() if n != 7}
    if phase == "night_seer":
        # Look at an unknown player, not a seat already inspected.
        checked = set()
        for key in ("investigations", "seer_results", "checks"):
            data = obs.get(key)
            if isinstance(data, dict):
                for n in data:
                    n = n[6:] if str(n).startswith("Player") else n
                    if str(n).isdigit():
                        checked.add(int(n))
            elif isinstance(data, list):
                for r in data:
                    if isinstance(r, dict):
                        n = r.get("seat", r.get("player", r.get("position")))
                        n = n[6:] if str(n).startswith("Player") else n
                        if str(n).isdigit():
                            checked.add(int(n))
        novel = [n for n in eligible if n not in checked]
        return eligible[min(novel)] if novel else actions[0]
    if phase == "day_vote":
        wolves = _seer_wolves(obs)
        verified = sorted(n for n in wolves if n in eligible)
        if verified:
            return eligible[verified[0]]
        # Don't auto-abstain: three successive no-elimination days favor wolves.
        return eligible[min(eligible)] if eligible else (abstain or actions[0])
    if phase == "night_wolf":
        # A wolf's teammate position may be present in the PRIVATE own view.
        allies = set()
        for key in ("wolf_teammate", "wolf_ally", "teammate"):
            value = obs.get(key)
            if isinstance(value, int):
                allies.add(value)
            if isinstance(value, str) and value.startswith("Player") and value[6:].isdigit():
                allies.add(int(value[6:]))
        candidates = [n for n in sorted(eligible) if n not in allies and n != me]
        return eligible[candidates[0]] if candidates else actions[0]
    return actions[0]


class SuperWarDragonFree:
    def __init__(self):
        self.red_alert = FreeRuleAgent()
        self.spoken_rounds = set()

    def choose_action(self, state, context):
        game = str(getattr(context, "game_type", "") or "")
        if game == "red_alert":
            return self.red_alert.choose_action(state, context)
        if game.startswith("pokemon"):
            kind = state.legal_actions[0].action_id if state.legal_actions else ""
            if kind == "select_lineup":
                return _pokemon_lineup(state)
            if kind == "doubles_turn":
                return _pokemon_doubles(state)
            return state.legal_actions[0] if state.legal_actions else smoke_agent.choose_action(state, context)
        if game == "werewolf":
            return _werewolf_action(state)
        return smoke_agent.choose_action(state, context)

    def choose_message(self, state, context):
        if str(getattr(context, "game_type", "")) != "werewolf":
            return TERMINATE_MESSAGING
        round_id = getattr(state, "state_version", None)
        # One helpful public statement per discussion window; then exit.
        if round_id in self.spoken_rounds:
            return TERMINATE_MESSAGING
        self.spoken_rounds.add(round_id)
        obs = _observation(_dict(getattr(state, "raw", None)))
        wolves = sorted(_seer_wolves(obs))
        if wolves and str(obs.get("role", obs.get("your_role", ""))).lower() == "seer":
            return SendMessage(f"I am the seer. I investigated Player{wolves[0]} and saw a wolf. Please consider voting there.")
        return SendMessage("Let's compare the claims and previous votes. Please explain your suspicions and avoid an automatic abstention.")

    def on_action_result(self, result, context):
        if str(getattr(context, "game_type", "")) == "red_alert":
            self.red_alert.on_action_result(result, context)


def create_agent():
    return SuperWarDragonFree()
