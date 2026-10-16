"""Observable shield mechanics and conservative joint-action regressions."""
from copy import deepcopy
import pytest
from examples import pokemon_policy_v10 as policy
from test_free_multigame_agent_v2 import opt
from test_pokemon_v10 import battle


@pytest.mark.parametrize("ability,species", [("multiscale", "Dragonite"), ("shadowshield", "Lunala")])
@pytest.mark.parametrize("name,attacker,hits", [
    ("rockblast", {"species":"Cloyster", "ability":"Skill Link"}, 5),
    ("scaleshot", {"species":"Dragonite", "item":"Loaded Dice"}, 4.5),
    ("bulletseed", {"species":"Rillaboom"}, 3),
    ("doublehit", {"species":"Rillaboom"}, 2),
    ("tackle", {"species":"Rillaboom"}, 1),
])
def test_only_first_equal_power_hit_has_full_hp_shield(ability, species, name, attacker, hits):
    foe = {"species":species, "ability":ability}
    unshielded = policy.damage({"move_id":name}, attacker, {**foe, "ability":None}, {})
    assert policy.damage({"move_id":name}, attacker, foe, {}) == pytest.approx(unshielded*(1-.5/hits))
    assert policy.damage({"move_id":name}, attacker, {**foe, "current_hp_fraction":.99}, {}) == pytest.approx(unshielded)
    # Selection's heuristic retains the exact old estimate.
    assert policy.damage({"move_id":name}, attacker, foe) == pytest.approx(unshielded*.5)


def credit(first="fakeout", second="dracometeor", first_mon=None, second_mon=None, enemy=None, fields=None, danger=0):
    ours = [first_mon or {"species":"Rillaboom"}, second_mon or {"species":"Archaludon"}]
    foes = {1:{"species":"Dragonite", "ability":"Multiscale"}, 2:enemy or {"species":"Magikarp"}}
    observation = {"fields":fields or {}}
    pair = [(None, None, policy.move({"move_id":name}, observation, mon)) for name,mon in zip((first,second),ours)]
    incoming = {(i,t):danger for i in (0,1) for t in foes}
    return ours, pair, foes, incoming, observation


def evaluate_credit(data, reverse=False):
    ours,pair,foes,incoming,observation = data
    if reverse:
        ours,pair = list(reversed(ours)),list(reversed(pair))
        incoming = {(1-i,t):value for (i,t),value in incoming.items()}
    return policy._shield_break_credit(int(reverse), int(not reverse), ours, pair, foes[1], foes, incoming, observation)


def test_strict_fast_fakeout_credit_is_slot_independent_and_does_not_mutate():
    data=credit(); before=deepcopy(data)
    assert evaluate_credit(data) == evaluate_credit(data, reverse=True) == 1
    assert data == before


def test_accuracy_weights_conditional_credit():
    data=credit("thunder", first_mon={"species":"Electrode"})
    assert evaluate_credit(data) == pytest.approx(.7)


def test_visible_protect_leaves_shield_intact_for_joint_estimate():
    data=credit(); data[2][1]["public_set"]={"moves":["Protect"]}
    assert evaluate_credit(data) == 0


def test_faster_or_tied_fakeout_interrupts_prior_hit_credit():
    for species in ("Weavile", "Rillaboom"):
        data=credit(enemy={"species":species, "public_set":{"moves":["Fake Out"]}})
        assert evaluate_credit(data) == evaluate_credit(data, reverse=True) == 0


def test_public_flinch_immunity_preserves_first_hit_credit():
    data=credit(first_mon={"species":"Rillaboom", "item":"Covert Cloak"}, enemy={"species":"Weavile", "moves":["fakeout"]})
    assert evaluate_credit(data) == 1


def test_equal_speed_has_no_predicted_break_even_in_trick_room():
    for fields in ({}, {"TRICKROOM":0}):
        assert evaluate_credit(credit("tackle", "tackle", {"species":"Dragonite"}, {"species":"Dragonite"}, fields=fields)) == 0


def test_trickroom_reverses_speed_but_never_priority():
    assert evaluate_credit(credit("tackle", first_mon={"species":"Electrode"})) == 1
    assert evaluate_credit(credit("tackle", first_mon={"species":"Electrode"}, fields={"TRICKROOM":0})) == 0
    assert evaluate_credit(credit("tackle", first_mon={"species":"Torkoal"}, fields={"TRICKROOM":0})) == 1
    assert evaluate_credit(credit("dragontail", first_mon={"species":"Electrode"})) == 0
    assert evaluate_credit(credit("fakeout", first_mon={"species":"Torkoal"}, fields={"TRICKROOM":0})) == 1


def test_known_lethal_pressure_discounts_optional_break_credit():
    data=credit("tackle", first_mon={"species":"Archaludon"}, second_mon={"species":"Torkoal"}, enemy={"species":"Deoxys-Speed"}, danger=2)
    assert evaluate_credit(data) == pytest.approx(.2)


def test_multihit_rule_changes_selected_attack_against_visible_full_hp_shield():
    state=battle([opt("rockblast", opponents=("Lunala",)), opt("icebeam", opponents=("Lunala",))],
                 [{"species":"Lunala", "ability":"Shadow Shield", "moves":["splash"]}], active="Cloyster", partner_moves=[{"type":"pass"}])
    state.legal_actions[0].input["action"]["slots"][0]["active"]["ability"]="Skill Link"
    state.legal_actions[0].input["action"]["slots"][0]["active"]["nature"]="Modest"
    assert policy.doubles(state)["slot_0"]["move_id"] == "rockblast"


def test_unrevealed_ability_does_not_import_v10_4_public_fallback():
    attacker={"species":"Cloyster", "ability":"Skill Link"}
    target={"species":"Dragonite", "ability":None, "public_set":{"ability":"Multiscale"}}
    assert policy.damage({"move_id":"rockblast"},attacker,target,{}) == policy.damage({"move_id":"rockblast"},attacker,{"species":"Dragonite"},{})


@pytest.mark.parametrize("malformed", [None, "Fake Out", {"fakeout":True}, 7, False])
def test_known_moves_ignores_null_or_malformed_containers(malformed):
    assert policy._known_move_names({"moves":malformed, "public_set":{"moves":malformed}}) == set()
    assert policy._known_move_names({"moves":malformed, "public_set":{"moves":["Protect"]}}) == {"protect"}


def test_known_moves_accepts_lists_tuples_and_ignores_bad_members():
    assert policy._known_move_names({"moves":("Fake Out",None,7), "public_set":{"moves":["Protect",{}]}}) == {"fakeout","protect"}
