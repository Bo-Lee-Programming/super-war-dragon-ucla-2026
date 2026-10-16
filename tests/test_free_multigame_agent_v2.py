"""Local player-view Pokémon battle fixtures, NOT official Testing results.

Checks decision legality against the official starter's structured template
and validates concrete damaging-target preferences. No server opponent or
real Showdown is started.
"""
import unittest
from types import SimpleNamespace
from altruagent import LegalAction
from examples.free_multigame_agent import create_agent as v1_agent
from examples.free_multigame_agent_v2 import create_agent as v2_agent


def scenario(slot0, slot1=None, active=None):
    slot1 = slot1 or [{"type": "pass"}]
    template = {"type": "doubles_turn", "slots": [
        {"slot": 0, "active": active or {}, "options": slot0},
        {"slot": 1, "active": {}, "options": slot1}
    ]}
    action = LegalAction(action_id="doubles_turn", label="play", input={"action": template})
    return SimpleNamespace(legal_actions=[action], raw={"observation": template})


def opt(move, power=None, targets=(1, 2), opponents=()):
    d = {"type": "move", "move_id": move, "targets": list(targets)}
    if power is not None:
        d["base_power"] = power
    d["target_options"] = [
        {"target": i + 1, "side": "opponent", "species": species}
        for i, species in enumerate(opponents)
    ]
    return d


class PokemonV2BattleCases(unittest.TestCase):
    def test_electric_immunity_vs_quadruple_weakness(self):
        state = scenario([opt("thunderbolt", opponents=("Garchomp", "Gyarados"))])
        old = v1_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        new = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(old["slot_0"]["target"], 1)
        self.assertEqual(new["slot_0"]["target"], 2)

    def test_fire_immunity_not_confused_with_resistance(self):
        state = scenario([opt("flamethrower", opponents=("Heatran", "Ferrothorn"))])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"]["target"], 2)

    def test_water_goes_for_fire_steel_not_grass_steel(self):
        state = scenario([opt("hydropump", opponents=("Ferrothorn", "Heatran"))])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"]["target"], 2)

    def test_server_exposed_types_override_static_species(self):
        move = opt("thunderbolt", opponents=("Gyarados", "Garchomp"))
        move["target_options"][0]["types"] = ["ground"]
        move["target_options"][1]["types"] = ["water", "flying"]
        state = scenario([move])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"]["target"], 2)

    def test_choose_ground_move_on_electric_target(self):
        state = scenario([opt("thunderbolt", opponents=("Garchomp", "Raichu")),
                          opt("earthpower", opponents=("Garchomp", "Raichu"))])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"], {"type": "move", "move_id": "earthpower", "target": 2})

    def test_self_heal_not_treated_as_friendly_fire(self):
        state = scenario([opt("recover", targets=(-1,)),
                          {"type": "switch", "species": "Pikachu"}])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"], {"type": "move", "move_id": "recover", "target": -1})

    def test_ally_damage_avoided_when_other_option_exists(self):
        state = scenario([opt("tackle", targets=(-2,)),
                          opt("thunderbolt", targets=(1,), opponents=("Gyarados",))])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"]["move_id"], "thunderbolt")

    def test_forced_switch_avoids_duplicate_bench_species(self):
        state = scenario(
            [{"type": "switch", "species": "A"}, {"type": "switch", "species": "B"}],
            [{"type": "switch", "species": "A"}, {"type": "switch", "species": "C"}])
        got = v2_agent().choose_action(state, SimpleNamespace(game_type="pokemon_vgc_doubles_draft"))
        self.assertEqual(got["slot_0"], {"type": "switch", "species": "A"})
        self.assertEqual(got["slot_1"], {"type": "switch", "species": "C"})

    def test_no_fabricated_move_or_target_in_diverse_templates(self):
        cases = [
            scenario([opt("earthpower", opponents=("Pikachu", "Gyarados")),
                      opt("surf", targets=(0,))]),
            scenario([opt("swordsdance", targets=(-1,))]),
            scenario([opt("flamethrower", opponents=("Ferrothorn", "Tyranitar"))]),
            scenario([{"type": "pass"}],
                     [opt("watergun", targets=(1,), opponents=("Groudon",))])
        ]
        ctx = SimpleNamespace(game_type="pokemon_vgc_doubles_draft")
        for s in cases:
            with self.subTest(case=s.raw["observation"]):
                got = v2_agent().choose_action(s, ctx)
                self.assertEqual(got["type"], "doubles_turn")
                for i in (0, 1):
                    chosen = got[f"slot_{i}"]
                    options = s.legal_actions[0].input["action"]["slots"][i]["options"]
                    valid = any(
                        (o["type"] == chosen["type"]) and (
                        chosen["type"] == "pass"
                        or (chosen["type"] == "switch" and chosen["species"] == o["species"])
                        or (chosen["type"] == "move" and chosen["move_id"] == o["move_id"]
                            and (chosen.get("target") in o["targets"]
                                 if o.get("targets") else "target" not in chosen))
                    ) for o in options)
                    self.assertTrue(valid, chosen)

if __name__ == "__main__":
    unittest.main()
