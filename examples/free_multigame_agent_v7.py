"""Unsubmitted local V7 candidate; independent of the AWS-hosted Markdown."""
from altruagent import SendMessage, TERMINATE_MESSAGING
from examples.free_multigame_agent import _dict, _observation
from examples.free_multigame_agent_v5 import (
    _player_lookup, _private_seer_records, _revealed_dead,
)
from examples.free_multigame_agent_v6 import SuperWarDragonV6
from examples.fast_redalert_agent_v7 import FastRedAlertV7
from examples.pokemon_policy_v7 import doubles, lineup


class SuperWarDragonV7(SuperWarDragonV6):
    def __init__(self):
        super().__init__()
        self._redalert_v6 = FastRedAlertV7()

    def choose_action(self, state, context):
        if getattr(context, "game_type", "") == "pokemon_vgc_doubles_draft" and state.legal_actions:
            action_id = state.legal_actions[0].action_id
            candidate = (doubles(state) if action_id == "doubles_turn" else
                         lineup(state) if action_id == "select_lineup" else None)
            if candidate is not None:
                return candidate
        return super().choose_action(state, context)

    def choose_message(self, state, context):
        if getattr(context, "game_type", "") != "werewolf":
            return TERMINATE_MESSAGING
        raw = _dict(state.raw)
        if raw.get("eliminated"):
            return TERMINATE_MESSAGING
        obs = _observation(raw)
        if str(obs.get("role", obs.get("your_role", ""))).lower() != "seer":
            return super().choose_message(state, context)
        lookup = _player_lookup(raw)
        dead = _revealed_dead(raw, lookup)
        known = _private_seer_records(obs, lookup)
        living_wolves = sorted(n for n, role in known.items() if role == "wolf" and n not in dead)
        game = _dict(raw.get("game_state"))
        votes = game.get("vote_history", [])
        history_len = len(votes) if isinstance(votes, list) else 0
        window = (str(game.get("day", history_len)), history_len)
        if window in self._discussion_windows_sent:
            return TERMINATE_MESSAGING
        self._discussion_windows_sent.add(window)
        if living_wolves:
            return SendMessage(f"I am the seer. My investigation found Player{living_wolves[0]} is a wolf. "
                               "This player is still alive; I propose voting for that seat.")
        # Do not sacrifice the living seer by repeating a dead wolf finding.
        return SendMessage("Compare completed public votes and revealed roles. "
                           "Please propose a living target and explain your evidence.")


def create_agent():
    return SuperWarDragonV7()
