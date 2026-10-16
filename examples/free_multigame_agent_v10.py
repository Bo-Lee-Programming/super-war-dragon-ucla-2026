"""V10 independent per-match strategies, with private write-only audit records."""
from examples.decision_audit import AuditedAgent
from examples.free_multigame_agent_v9 import SuperWarDragonV9, normalize_pokemon
from examples.fast_redalert_agent_v10 import FastRedAlertV10
from examples.pokemon_policy_v10 import PokemonPolicyV10
from examples.werewolf_policy_v10 import WerewolfPolicyV10


class SuperWarDragonV10(SuperWarDragonV9):
    def __init__(self):
        super().__init__()
        self._redalert_v6 = FastRedAlertV10()
        self._pokemon_v10 = PokemonPolicyV10()
        self._werewolf_v10 = WerewolfPolicyV10()

    def choose_action(self, state, context):
        game = getattr(context, "game_type", "")
        if game == "werewolf":
            return self._werewolf_v10.choose_action(state, context)
        if game == "pokemon_vgc_doubles_draft":
            state = normalize_pokemon(state, context)
            decision = self._pokemon_v10.choose_action(state, context)
            if decision is not None:
                return decision
        return super().choose_action(state, context)

    def choose_message(self, state, context):
        if getattr(context, "game_type", "") == "werewolf":
            return self._werewolf_v10.choose_message(state, context)
        return super().choose_message(state, context)


def create_agent():
    return AuditedAgent(SuperWarDragonV10())
