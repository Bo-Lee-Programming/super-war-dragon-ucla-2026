"""Equivalent board positions and deterministic healing failures."""
from types import SimpleNamespace
from altruagent import LegalAction
from examples.pokemon_policy_v10 import doubles


def option(name, targets=(1,)):
    return {"type":"move", "move_id":name, "targets":list(targets)}


def fixture(patient="Eelektross", attack="thunderbolt", swapped=False, fields=None):
    actors = [{"species":patient, "current_hp_fraction":.1}, {"species":"Audino"}]
    options = [[option(attack)], [option("healpulse", (-2 if swapped else -1,)), option("lightscreen", (0,))]]
    if swapped:
        actors.reverse()
        options.reverse()
    slots = [{"slot":i, "active":mon, "options":moves} for i,(mon,moves) in enumerate(zip(actors, options))]
    return SimpleNamespace(raw={"observation":{"turn":1, "fields":fields or {},
                           "opponent_active_pokemon":[{"species":"Diancie", "current_hp_fraction":.1,
                                                         "moves":["moonblast"]}]}},
                           legal_actions=[LegalAction(action_id="doubles_turn", label="", input={"action":{"slots":slots}})])


def test_trick_room_speed_tie_does_not_change_healing_with_board_position():
    # All three public base speeds are50 (estimated86). A tied KO must not
    # become guaranteed prevention merely because that slot is visited first.
    for swapped in (False, True):
        chosen = doubles(fixture(swapped=swapped, fields={"TRICK_ROOM":0}))
        assert chosen["slot_0" if swapped else "slot_1"]["move_id"] == "lightscreen"


def test_fast_partner_ko_is_collected_before_valuing_healing_in_either_slot():
    for swapped in (False, True):
        chosen = doubles(fixture(patient="Gengar", attack="shadowball", swapped=swapped))
        assert chosen["slot_0" if swapped else "slot_1"]["move_id"] == "healpulse"


def test_fast_partner_fakeout_is_collected_before_valuing_healing_in_either_slot():
    for swapped in (False, True):
        chosen = doubles(fixture(patient="Incineroar", attack="fakeout", swapped=swapped))
        assert chosen["slot_0" if swapped else "slot_1"]["move_id"] == "healpulse"


def test_patient_protect_blocks_all_three_ally_heal_rewards():
    for heal, species, attack in (("pollenpuff","Amoonguss","sludgebomb"),
                                 ("healpulse","Clawitzer","waterpulse"),
                                 ("floralhealing","Comfey","drainingkiss")):
        s = fixture(patient="Iron Hands", attack="protect")
        slots = s.legal_actions[0].input["action"]["slots"]
        slots[0]["active"]["current_hp_fraction"] = .4
        slots[0]["options"] = [option("protect", (0,))]
        slots[1]["active"] = {"species":species}
        slots[1]["options"] = [option(heal, (-1,)), option(attack)]
        s.raw["observation"]["opponent_active_pokemon"] = [{"species":"Garchomp", "moves":["tackle"]}]
        assert doubles(s)["slot_1"] == {"type":"move", "move_id":attack, "target":1}


def priority_fixture(moves, fields=None):
    s = fixture(patient="Dragapult", fields=fields)
    slots = s.legal_actions[0].input["action"]["slots"]
    slots[0]["options"] = [option(m) for m in moves]
    slots[1].update(active=None, options=[{"type":"pass"}])
    s.raw["observation"]["opponent_active_pokemon"] = [
        {"species":"Garchomp", "current_hp_fraction":.05, "moves":["earthquake"]}]
    return s


def test_negative_priority_dragon_tail_is_not_a_fast_ko_from_speed_alone():
    assert doubles(priority_fixture(("dragontail","tackle")))["slot_0"]["move_id"] == "tackle"


def test_positive_priority_stays_before_normal_attacks_under_trick_room():
    for fields in ({}, {"TRICK_ROOM":0}):
        assert doubles(priority_fixture(("dragontail","quickattack"), fields))["slot_0"]["move_id"] == "quickattack"
