"""V8 fixes derived from completed platform tests and own-seat input schema."""
from copy import copy
import re

from examples.free_multigame_agent import _dict, _observation
from examples.free_multigame_agent_v7 import SuperWarDragonV7
from examples.fast_redalert_agent_v8 import FastRedAlertV8
from examples.pokemon_policy_v8 import doubles, lineup


def normalize_werewolf(state):
    raw = _dict(state.raw)
    if _observation(raw):
        return state
    text = raw.get("observation", getattr(state, "observation", ""))
    if not isinstance(text, str) or not text.startswith("=== Werewolf ===\n"):
        return state
    # Read only the platform's private header, never public chat, dead roles
    # or arbitrary lines later in the observation.
    header = text.split("\n\n", 1)[0].splitlines()
    if len(header) < 2:
        return state
    role = re.fullmatch(r"Your role: (WOLF|SEER|VILLAGER)", header[1])
    if role is None:
        return state
    obs = {"role": role[1].lower()}
    for line in header[2:]:
        if obs["role"] == "wolf" and line.startswith("Your fellow wolves: "):
            obs["wolf_teammates"] = [int(n) for n in re.findall(r"\bPlayer([0-6])\b", line)]
        if obs["role"] == "seer" and line.startswith("Your investigations: "):
            obs["investigations"] = [{"seat": int(n), "role": found.lower()}
                for n, found in re.findall(r"\bPlayer([0-6]) is (wolf|villager)\b", line, re.I)]
    normalized = copy(state)
    normalized.raw = {**raw, "observation": obs}
    return normalized


class SuperWarDragonV8(SuperWarDragonV7):
    def __init__(self):
        super().__init__()
        self._redalert_v6 = FastRedAlertV8()

    def choose_action(self, state, context):
        game = getattr(context, "game_type", "")
        if game == "werewolf":
            state = normalize_werewolf(state)
        if game == "pokemon_vgc_doubles_draft" and state.legal_actions:
            kind = state.legal_actions[0].action_id
            action = doubles(state) if kind == "doubles_turn" else lineup(state) if kind == "select_lineup" else None
            if action is not None:
                return action
        return super().choose_action(state, context)

    def choose_message(self, state, context):
        if getattr(context, "game_type", "") == "werewolf":
            state = normalize_werewolf(state)
        return super().choose_message(state, context)


def create_agent():
    return SuperWarDragonV8()
