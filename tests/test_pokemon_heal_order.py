"""Public-state action checks for ally healing that may arrive after a KO."""
from types import SimpleNamespace
from altruagent import LegalAction
from examples.pokemon_policy_v10 import doubles


def option(name, targets=(1,)):
    return {"type":"move", "move_id":name, "targets":list(targets)}


def scenario(patient_hp=.1, foe_move="earthquake", fields=None):
    slots = [
        {"slot":0, "active":{"species":"Iron Hands", "current_hp_fraction":patient_hp},
         "options":[option("drainpunch")]},
        {"slot":1, "active":{"species":"Amoonguss"},
         "options":[option("pollenpuff", (-1,1)), option("sludgebomb"), option("ragepowder", (0,))]}]
    return SimpleNamespace(raw={"observation":{"turn":2, "fields":fields or {},
                           "opponent_active_pokemon":[{"species":"Garchomp", "moves":[foe_move]}]}},
                           legal_actions=[LegalAction(action_id="doubles_turn", label="", input={"action":{"slots":slots}})])


def test_doomed_patient_is_not_given_full_slow_pollen_puff_value():
    chosen = doubles(scenario())
    assert chosen["slot_1"] == {"type":"move", "move_id":"pollenpuff", "target":1}


def test_current_trick_room_retains_heal_before_the_threat():
    chosen = doubles(scenario(fields={"TRICK_ROOM":0}))
    assert chosen["slot_1"] == {"type":"move", "move_id":"pollenpuff", "target":-1}


def test_speed_boost_retains_heal_before_normal_priority_threat():
    s = scenario()
    s.legal_actions[0].input["action"]["slots"][1]["active"]["boosts"] = {"spe":3}
    assert doubles(s)["slot_1"]["target"] == -1


def test_nonlethal_earlier_hit_does_not_remove_healing_value():
    assert doubles(scenario(patient_hp=.4, foe_move="tackle"))["slot_1"]["target"] == -1


def test_triage_floral_healing_is_not_treated_as_slow_normal_priority():
    s = scenario()
    slot = s.legal_actions[0].input["action"]["slots"][1]
    slot["active"] = {"species":"Comfey", "ability":"Triage"}
    slot["options"] = [option("floralhealing", (-1,)), option("drainingkiss")]
    assert doubles(s)["slot_1"]["move_id"] == "floralhealing"
    slot["active"]["ability"] = "Flower Veil"
    assert doubles(s)["slot_1"]["move_id"] == "drainingkiss"


def test_heal_pulse_uses_the_same_patient_survival_check():
    s = scenario()
    slot = s.legal_actions[0].input["action"]["slots"][1]
    slot["active"] = {"species":"Cresselia"}
    slot["options"] = [option("healpulse", (-1,)), option("psychic")]
    assert doubles(s)["slot_1"]["move_id"] == "psychic"


def test_public_triage_retains_early_heal_unless_fallback_is_blocked():
    s = scenario()
    slot = s.legal_actions[0].input["action"]["slots"][1]
    slot["active"] = {"species":"Comfey", "ability":None, "public_set":{"ability":"Triage"}}
    slot["options"] = [option("floralhealing", (-1,)), option("drainingkiss")]
    assert doubles(s)["slot_1"]["move_id"] == "floralhealing"
    slot["active"]["_public_ability_fallback_blocked"] = True
    assert doubles(s)["slot_1"]["move_id"] == "drainingkiss"
