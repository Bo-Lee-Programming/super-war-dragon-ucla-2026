"""Super War Dragon V6: fast deterministic Red Alert + preserved V5 Pokemon/Werewolf.

Unlike the AWS Hosted Markdown strategy, this module is actual executable
Python and requires an Official Agent Key and self-hosted match assignment.
"""
from examples.fast_redalert_agent_v6 import FastRedAlertV6
from examples.free_multigame_agent_v5 import SuperWarDragonV5


class SuperWarDragonV6(SuperWarDragonV5):
    def __init__(self):
        super().__init__()
        self._redalert_v6 = FastRedAlertV6()

    def choose_action(self, state, context):
        if str(getattr(context, "game_type", "")) == "red_alert":
            return self._redalert_v6.choose_action(state, context)
        return super().choose_action(state, context)

    def on_action_result(self, result, context):
        if str(getattr(context, "game_type", "")) == "red_alert":
            self._redalert_v6.on_action_result(result, context)
        else:
            callback = getattr(super(), "on_action_result", None)
            if callable(callback):
                callback(result, context)


def create_agent():
    return SuperWarDragonV6()
