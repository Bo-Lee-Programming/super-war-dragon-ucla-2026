"""Super War Dragon V5: documented-name Werewolf adapter + bounded discussion.

This revision fixes V4's assumption that public player names are always
"PlayerN". The official starter GAMES.md says public dead/vote history uses
*display names*, mapped through state.raw["players"]. It also avoids sending
the same generic chat repeatedly when state_version advances mid-window.
No remote match, credentials or opponent-private data are accessed.
"""
from __future__ import annotations

from typing import Any
from altruagent import SendMessage, TERMINATE_MESSAGING

from examples.free_multigame_agent import _dict, _observation
from examples.free_multigame_agent_v4 import SuperWarDragonV4, _seat


def _player_lookup(raw: dict) -> dict[str, int]:
    lookup: dict[str, int] = {}
    players = raw.get("players", [])
    if not isinstance(players, list):
        return lookup
    for player in players:
        if not isinstance(player, dict):
            continue
        n = _seat(player.get("position"))
        if n is None:
            continue
        lookup[str(n)] = n
        lookup[f"player{n}"] = n
        for field in ("name", "display_name"):
            name = player.get(field)
            if isinstance(name, str) and name.strip():
                lookup[name.strip().casefold()] = n
    return lookup


def _resolve(value: Any, lookup: dict[str, int]) -> int | None:
    if isinstance(value, dict):
        for field in ("position", "seat", "player", "name", "voter", "target"):
            if field in value:
                result = _resolve(value[field], lookup)
                if result is not None:
                    return result
        return None
    n = _seat(value)
    if n is not None:
        return n
    if isinstance(value, str):
        return lookup.get(value.strip().casefold())
    return None


def _private_seer_records(obs: dict, lookup: dict[str, int]) -> dict[int, str]:
    """Only results present in own observation; never game_state hidden roles."""
    known: dict[int, str] = {}
    for field in ("investigations", "seer_results", "checks", "results"):
        records = obs.get(field)
        if isinstance(records, dict):
            records = [{"player": k, "role": v} for k, v in records.items()]
        if not isinstance(records, list):
            continue
        for r in records:
            if not isinstance(r, dict):
                continue
            n = _resolve(r.get("seat", r.get("player", r.get("position", r.get("name")))), lookup)
            role = str(r.get("role", r.get("result", ""))).lower().strip()
            if n is not None and role in ("wolf", "werewolf", "villager", "seer"):
                known[n] = "wolf" if role == "werewolf" else role
    return known


def _own_wolf_allies(obs: dict, lookup: dict[str, int]) -> set[int]:
    result: set[int] = set()
    # The acting player's PRIVATE observation only, never engine roles.
    for key in ("wolf_teammate", "wolf_ally", "teammate", "wolf_teammates", "wolf_allies"):
        val = obs.get(key)
        if isinstance(val, dict):
            vals = list(val.values())
        elif isinstance(val, (list, tuple)):
            vals = val
        else:
            vals = [val]
        for item in vals:
            n = _resolve(item, lookup)
            if n is not None:
                result.add(n)
    return result


def _revealed_dead(raw: dict, lookup: dict[str, int]) -> dict[int, str]:
    game = _dict(raw.get("game_state"))
    dead = game.get("dead", [])
    if isinstance(dead, dict):
        dead = ([dict(name=k, role=v) if not isinstance(v, dict)
                 else dict(v, name=k) for k, v in dead.items()])
    if not isinstance(dead, list):
        return {}
    result = {}
    for person in dead:
        if not isinstance(person, dict):
            continue
        n = _resolve(person.get("position", person.get("seat", person.get("player", person.get("name")))), lookup)
        role = str(person.get("role", "")).lower()
        if n is not None and role in ("villager", "seer", "wolf", "werewolf"):
            result[n] = "wolf" if role == "werewolf" else role
    return result


def _public_suspicion(raw: dict, candidates: set[int], lookup: dict[str, int]) -> dict[int, float]:
    """Use only publicly revealed deaths and completed, public past votes."""
    revealed = _revealed_dead(raw, lookup)
    result = {n: 0.0 for n in candidates}
    history = _dict(raw.get("game_state")).get("vote_history", [])
    if not isinstance(history, list):
        return result
    for day in history:
        if not isinstance(day, dict):
            continue
        ballots = day.get("votes", day.get("ballots", []))
        if isinstance(ballots, dict):
            pairs = list(ballots.items())
        elif isinstance(ballots, list):
            pairs = [(x.get("voter", x.get("from", x.get("player"))),
                      x.get("target", x.get("vote", x.get("to"))))
                     for x in ballots if isinstance(x, dict)]
        else:
            pairs = []
        for voter, target in pairs:
            voter_id = _resolve(voter, lookup)
            target_id = _resolve(target, lookup)
            if voter_id not in candidates or target_id not in revealed:
                continue
            # A vote for a revealed wolf helps clear the voter; an incorrect
            # vote against a verified innocent is weak, not conclusive evidence.
            result[voter_id] += -3.0 if revealed[target_id] == "wolf" else 1.0
    return result


class SuperWarDragonV5(SuperWarDragonV4):
    def __init__(self):
        super().__init__()
        self._discussion_windows_sent: set[tuple] = set()

    def _werewolf_v4(self, state):  # V4 dispatch calls this overridable hook.
        actions = getattr(state, "legal_actions", []) or []
        legal = {}
        for a in actions:
            n = _seat(str(a.action_id))
            if n is not None:
                legal[n] = a
        if not legal:
            return actions[0] if actions else None
        raw = _dict(getattr(state, "raw", None))
        game = _dict(raw.get("game_state"))
        obs = _observation(raw)
        role = str(obs.get("role", obs.get("your_role", ""))).lower()
        phase = game.get("phase")
        lookup = _player_lookup(raw)
        our_seat = _resolve(raw.get("your_position"), lookup)
        targets = sorted(n for n in legal if n != 7 and n != our_seat)
        if not targets:
            return legal.get(7, actions[0])

        allies = _own_wolf_allies(obs, lookup) if role in ("wolf", "werewolf") else set()
        targets = [n for n in targets if n not in allies] or targets

        investigations = _private_seer_records(obs, lookup) if role == "seer" else {}
        if phase == "night_wolf":
            return legal[targets[0]]
        if phase == "night_seer":
            novel = [n for n in targets if n not in investigations] or targets
            suspicious = _public_suspicion(raw, set(novel), lookup)
            return legal[max(novel, key=lambda n: (suspicious.get(n, 0.0), -n))]
        if phase == "day_vote":
            verified_wolves = [n for n in targets if investigations.get(n) == "wolf"]
            if verified_wolves:
                return legal[verified_wolves[0]]
            eligible = [n for n in targets if investigations.get(n) not in ("villager", "seer")]
            if not eligible:
                eligible = targets
            suspicious = _public_suspicion(raw, set(eligible), lookup)
            if any(abs(v) > 1e-6 for v in suspicious.values()):
                return legal[max(eligible, key=lambda n: (suspicious[n], -n))]
            history = game.get("vote_history", [])
            day = len(history) if isinstance(history, list) else 0
            return legal[eligible[((our_seat or 0) + day) % len(eligible)]]
        return actions[0]

    def choose_message(self, state, context):
        if str(getattr(context, "game_type", "")) != "werewolf":
            return TERMINATE_MESSAGING
        raw = _dict(getattr(state, "raw", None))
        game = _dict(raw.get("game_state"))
        votes = game.get("vote_history", [])
        history_len = len(votes) if isinstance(votes, list) else 0
        # Unlike state_version, these remain stable as participants send chat.
        day = game.get("day", history_len)
        window = (str(day), history_len)
        if window in self._discussion_windows_sent:
            return TERMINATE_MESSAGING
        self._discussion_windows_sent.add(window)

        obs = _observation(raw)
        role = str(obs.get("role", obs.get("your_role", ""))).lower()
        lookup = _player_lookup(raw)
        if role == "seer":
            known = _private_seer_records(obs, lookup)
            wolves = sorted(n for n, r in known.items() if r == "wolf")
            if wolves:
                return SendMessage(
                    f"I am the seer. My investigation found Player{wolves[0]} is a wolf. "
                    "Please discuss this evidence before voting."
                )
        return SendMessage(
            "Please compare the previous public votes and any verifiable claims. "
            "We should reach a reasoned vote rather than abstain automatically."
        )


def create_agent():
    return SuperWarDragonV5()
