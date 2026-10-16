"""V9 keeps V8 Werewolf/Red Alert and consumes actual Pokemon battle metadata."""
from copy import copy

from examples.free_multigame_agent import _dict, _observation
from examples.free_multigame_agent_v8 import SuperWarDragonV8
from examples.pokemon_policy_v9 import doubles, lineup


def normalize_pokemon(state, context):
    raw = _dict(state.raw)
    observation = _observation(raw)
    rosters = observation.get("rosters")
    agent_id = getattr(context, "agent_id", None)
    if isinstance(rosters, dict) and agent_id in rosters:
        # The live draft uses agent IDs as dictionary keys, not seat numbers.
        observation = {**observation, "my_roster": rosters[agent_id],
                       "opponent_roster": next((v for k, v in rosters.items() if k != agent_id), [])}
        state = copy(state)
        state.raw = {**raw, "observation": observation}
    return state


class SuperWarDragonV9(SuperWarDragonV8):
    def choose_action(self, state, context):
        if getattr(context, "game_type", "") == "pokemon_vgc_doubles_draft":
            state = normalize_pokemon(state, context)
            if state.legal_actions:
                kind = state.legal_actions[0].action_id
                action = doubles(state) if kind == "doubles_turn" else lineup(state) if kind == "select_lineup" else None
                if action is not None:
                    return action
        return super().choose_action(state, context)


def create_agent():
    return SuperWarDragonV9()
