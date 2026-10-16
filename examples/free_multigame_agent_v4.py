"""Super War Dragon V4: player-view Werewolf public-evidence policy.

Preserves V3 Pokémon draft/preview/battle and Red Alert behavior.
No server-side hidden role enumeration or shared match memory.
This remains an unsubmitted LOCAL CANDIDATE, not an official Testing result.
"""
from __future__ import annotations
from typing import Any
from examples.free_multigame_agent import _dict, _observation, _seer_wolves
from examples.free_multigame_agent_v3 import SuperWarDragonV3


def _seat(v: Any):
    if type(v) is int and 0 <= v <= 6:
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if t.startswith("player"):
            t = t[6:]
        if t.isdigit() and 0 <= int(t) <= 6:
            return int(t)
    return None


def _known_wolf_teammates(obs: dict) -> set[int]:
    """Only private own observation fields documented to the acting wolf."""
    teammates = set()
    for k in ("wolf_teammate", "wolf_ally", "teammate", "wolf_teammates", "wolf_allies"):
        item = obs.get(k)
        if isinstance(item, (list, tuple)):
            values = item
        elif isinstance(item, dict):
            values = list(item.values())
        else:
            values = [item]
        for v in values:
            n = _seat(v)
            if n is not None:
                teammates.add(n)
    return teammates


def _public_vote_suspicion(raw: dict, legal: set[int]) -> dict[int, float]:
    """Read only public vote history and dead players' revealed roles."""
    game = _dict(raw.get("game_state"))
    dead = game.get("dead", [])
    revealed = {}
    if isinstance(dead, dict):
        dead = list(dead.values())
    if isinstance(dead, list):
        for record in dead:
            if not isinstance(record, dict):
                continue
            n = _seat(record.get("position", record.get("seat", record.get("player", record.get("name")))))
            role = str(record.get("role", "")).lower()
            if n is not None and role in ("wolf", "villager", "seer"):
                revealed[n] = role
    history = game.get("vote_history", [])
    if not isinstance(history, list):
        return {}
    score = {n: 0.0 for n in legal}
    for day in history:
        if not isinstance(day, dict):
            continue
        votes = day.get("votes", day.get("ballots", []))
        pairs = []
        if isinstance(votes, dict):
            pairs = list(votes.items())
        elif isinstance(votes, list):
            for v in votes:
                if isinstance(v, dict):
                    pairs.append((v.get("voter", v.get("from")), v.get("target", v.get("vote"))))
        for who, target in pairs:
            voter, target = _seat(who), _seat(target)
            if voter not in legal or target not in revealed:
                continue
            # A vote for a revealed wolf is evidence in the voter's favor.
            # Voting for a confirmed innocent contributes suspicion, but
            # only weakly: honest players can be mistaken.
            if revealed[target] == "wolf":
                score[voter] -= 3.0
            else:
                score[voter] += 1.0
    return score


class SuperWarDragonV4(SuperWarDragonV3):
    def _werewolf_v4(self, state):
        actions = getattr(state, "legal_actions", []) or []
        eligible = {}
        for a in actions:
            n = _seat(str(a.action_id))
            if n is not None:
                eligible[n] = a
        if not eligible:
            return actions[0] if actions else None

        raw = _dict(getattr(state, "raw", None))
        obs = _observation(raw)
        phase = str(_dict(raw.get("game_state")).get("phase", ""))
        my_role = str(obs.get("role", obs.get("your_role", ""))).lower()
        own_seat = _seat(raw.get("your_position"))
        targets = sorted(n for n in eligible if n != 7 and n != own_seat)
        if not targets:
            return eligible.get(7, actions[0])

        teammates = _known_wolf_teammates(obs) if my_role == "wolf" else set()
        safe_targets = [n for n in targets if n not in teammates] if my_role == "wolf" else targets
        if not safe_targets:
            safe_targets = targets

        if phase == "night_wolf":
            # Avoid our *known* teammate, even when their seat sorts first.
            return eligible[safe_targets[0]]

        if phase == "night_seer":
            inspected = set()
            for key in ("investigations", "seer_results", "checks", "results"):
                data = obs.get(key, [])
                if isinstance(data, dict):
                    inspected.update(n for k in data if (n := _seat(k)) is not None)
                elif isinstance(data, list):
                    for v in data:
                        if isinstance(v, dict):
                            n = _seat(v.get("seat", v.get("player", v.get("position"))))
                            if n is not None:
                                inspected.add(n)
            novel = [n for n in targets if n not in inspected]
            if not novel:
                novel = targets
            suspicion = _public_vote_suspicion(raw, set(novel))
            return eligible[max(novel, key=lambda n: (suspicion.get(n, 0), -n))]

        if phase == "day_vote":
            if my_role == "seer":
                confirmed = sorted(n for n in _seer_wolves(obs) if n in targets)
                if confirmed:
                    return eligible[confirmed[0]]
            scores = _public_vote_suspicion(raw, set(safe_targets))
            # When there is no actual public evidence, rotate the target so
            # every agent doesn't deterministically tunnel Player0 forever.
            if not scores or not any(abs(s) > 0.01 for s in scores.values()):
                day = len(_dict(raw.get("game_state")).get("vote_history", []) or [])
                position = own_seat if own_seat is not None else 0
                return eligible[safe_targets[(position + day) % len(safe_targets)]]
            return eligible[max(safe_targets, key=lambda n: (scores.get(n, 0), -n))]

        return actions[0]

    def choose_action(self, state, context):
        if str(getattr(context, "game_type", "")) == "werewolf":
            candidate = self._werewolf_v4(state)
            if candidate is not None:
                return candidate
        return super().choose_action(state, context)


def create_agent():
    return SuperWarDragonV4()
