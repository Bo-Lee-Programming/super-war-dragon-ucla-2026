"""Regression for V4, after 1600 paired whole-game simulated matches.
These do not imply a real tournament or official Testing result.
"""
import unittest
from types import SimpleNamespace
from altruagent import LegalAction
from examples.free_multigame_agent_v4 import create_agent
from examples.free_multigame_agent_v3 import create_agent as v3


def state(ids, raw):
    return SimpleNamespace(
        legal_actions=[LegalAction(action_id=str(n), label=str(n), input={}) for n in ids],
        raw=raw, state_version=1, new_messages=[],
    )


class WerewolfV4(unittest.TestCase):
    ctx = SimpleNamespace(game_type="werewolf")

    def test_wolf_never_votes_for_private_known_teammate(self):
        s = state([0, 1, 2, 7], {
            "your_position": 5, "game_state": {"phase": "day_vote"},
            "observation": {"role": "wolf", "wolf_teammate": 0},
        })
        self.assertEqual(v3().choose_action(s, self.ctx).action_id, "0")
        self.assertNotEqual(create_agent().choose_action(s, self.ctx).action_id, "0")

    def test_wolf_never_kills_known_teammate(self):
        s = state([0, 1, 2], {
            "your_position": 5, "game_state": {"phase": "night_wolf"},
            "observation": {"role": "wolf", "wolf_teammate": 0},
        })
        self.assertEqual(create_agent().choose_action(s, self.ctx).action_id, "1")

    def test_revealed_villager_vote_triggers_public_suspicion(self):
        # Public vote history: Player2 had voted to eliminate confirmed innocent.
        s = state([0, 2, 7], {
            "your_position": 5,
            "game_state": {"phase": "day_vote",
                "dead": [{"name": "Player1", "role": "villager", "cause": "vote"}],
                "vote_history": [{"votes": {"Player2": "Player1"}}]},
            "observation": {"role": "villager"},
        })
        self.assertEqual(create_agent().choose_action(s, self.ctx).action_id, "2")

    def test_seer_confirmed_wolf_overrides_public_votes(self):
        s = state([0, 1, 2, 7], {
            "your_position": 5,
            "game_state": {"phase": "day_vote",
                "dead": [{"name": "Player3", "role": "villager"}],
                "vote_history": [{"votes": {"Player2": "Player3"}}]},
            "observation": {"role": "seer",
                "investigations": [{"player": 1, "role": "wolf"}]},
        })
        self.assertEqual(create_agent().choose_action(s, self.ctx).action_id, "1")

    def test_draft_logic_identical_to_v3(self):
        c = SimpleNamespace(game_type="pokemon_vgc_doubles_draft")
        s = state(["draft_pick:c0", "draft_pick:c1"], {
            "observation": {"available_cards": [
                {"card_id": "c0", "species": "Garchomp"},
                {"card_id": "c1", "species": "Amoonguss"},
            ]}})
        self.assertEqual(
            create_agent().choose_action(s, c).action_id,
            v3().choose_action(s, c).action_id,
        )


if __name__ == "__main__":
    unittest.main()
