"""Visible Unaware stage rules cross-checked against official Showdown."""
from copy import deepcopy
import pytest
from examples import pokemon_policy_v10 as policy


def hit(name, attacker, defender, observation=None):
    return policy.damage({"move_id":name}, attacker, defender, {} if observation is None else observation)


@pytest.mark.parametrize("stage", [-4, 4])
@pytest.mark.parametrize("name,stat", [("waterfall","def"),("surf","spd"),("psyshock","def")])
def test_attacking_unaware_ignores_only_target_defensive_stages(stage, name, stat):
    attacker={"species":"Dondozo","ability":"Unaware"}
    target={"species":"Archaludon","boosts":{stat:stage}}
    assert hit(name, attacker, target) == hit(name, attacker, {**target,"boosts":{stat:0}})
    assert hit(name, {**attacker,"ability":None}, target) != hit(name, attacker, target)


@pytest.mark.parametrize("stage", [-4, 4])
@pytest.mark.parametrize("name,stat", [("waterfall","atk"),("surf","spa"),("bodypress","def")])
def test_defending_unaware_ignores_offensive_stages_including_bodypress(stage, name, stat):
    attacker={"species":"Archaludon","boosts":{stat:stage}}
    target={"species":"Dondozo","ability":"Unaware"}
    assert hit(name, attacker, target) == hit(name, {**attacker,"boosts":{stat:0}}, target)
    assert hit(name, attacker, {**target,"ability":None}) != hit(name, attacker, target)


def test_foulplay_offensive_event_belongs_to_user_even_when_target_atk_is_borrowed():
    attacker={"species":"Umbreon"}
    target={"species":"Dondozo","ability":"Unaware","boosts":{"atk":4,"def":2}}
    assert hit("foulplay",attacker,target) == hit("foulplay",attacker,{**target,"boosts":{"atk":0,"def":2}})
    # Attacking Unaware ignores defense stages, while retaining the borrowed Atk.
    attacker["ability"]="Unaware"; target["ability"]=None
    assert hit("foulplay",attacker,target) == hit("foulplay",attacker,{**target,"boosts":{"atk":4,"def":0}})
    assert hit("foulplay",attacker,target) > hit("foulplay",attacker,{**target,"boosts":{"atk":0,"def":0}})


@pytest.mark.parametrize("breaker", ["Mold Breaker","Teravolt","Turboblaze"])
def test_explicit_breaker_bypasses_defensive_unaware_except_ability_shield(breaker):
    attacker={"species":"Garchomp","ability":breaker,"boosts":{"atk":4}}
    target={"species":"Dondozo","ability":"Unaware"}
    assert hit("dragonclaw",attacker,target) == hit("dragonclaw",attacker,{**target,"ability":None})
    shielded={**target,"item":"Ability Shield"}
    assert hit("dragonclaw",attacker,shielded) == hit("dragonclaw",{**attacker,"boosts":{}},shielded)


@pytest.mark.parametrize("name,stat", [("sunsteelstrike","atk"),("moongeistbeam","spa"),("photongeyser","spa")])
def test_move_ability_bypass_and_ability_shield(name,stat):
    attacker={"species":"Mew","boosts":{stat:4}}
    target={"species":"Dondozo","ability":"Unaware"}
    assert hit(name,attacker,target) == hit(name,attacker,{**target,"ability":None})
    shielded={**target,"item":"Ability Shield"}
    assert hit(name,attacker,shielded) == hit(name,{**attacker,"boosts":{}},shielded)


def test_own_stages_and_nonstage_public_modifiers_remain_and_inputs_unchanged():
    attacker={"species":"Dondozo","ability":"Unaware","boosts":{"atk":2},"_public_stat_boosts":{"atk":1.3}}
    target={"species":"Archaludon","boosts":{"def":4},"_public_stat_boosts":{"def":1.3},"item":"Eviolite"}
    before=deepcopy((attacker,target))
    assert hit("waterfall",attacker,target) == hit("waterfall",attacker,{**target,"boosts":{}})
    assert hit("waterfall",attacker,target) > hit("waterfall",{**attacker,"boosts":{}},target)
    assert hit("waterfall",attacker,target) < hit("waterfall",attacker,{**target,"_public_stat_boosts":{}})
    assert (attacker,target)==before


@pytest.mark.parametrize("effects", [{"GASTRO_ACID":0},["Gastro Acid"]])
def test_known_gastroacid_disables_unaware_even_with_ability_shield(effects):
    attacker={"species":"Archaludon","boosts":{"def":4}}
    target={"species":"Dondozo","ability":"Unaware","effects":effects,"item":"Ability Shield"}
    assert hit("bodypress",attacker,target) == hit("bodypress",attacker,{**target,"ability":None})
    attacking={"species":"Dondozo","ability":"Unaware","effects":effects}
    assert hit("waterfall",attacking,attacker) == hit("waterfall",{**attacking,"ability":None},attacker)


def test_no_public_ability_fallback_and_selection_proxy_unchanged():
    attacker={"species":"Dondozo","ability":"Unaware","boosts":{"atk":3}}
    target={"species":"Archaludon","ability":None,"boosts":{"def":4},"public_set":{"ability":"Unaware"}}
    unknown={**attacker,"ability":None,"public_set":{"ability":"Unaware"}}
    assert hit("waterfall",unknown,target)==hit("waterfall",{**unknown,"public_set":{}},{**target,"public_set":{}})
    option={"move_id":"waterfall"}
    assert policy.damage(option,attacker,target)==policy.damage(option,{**attacker,"ability":None},target)
    assert hit("waterfall",attacker,target)!=policy.damage(option,attacker,target)


def test_defender_own_defensive_boosts_still_apply_with_unaware():
    attacker={"species":"Archaludon","boosts":{"def":4}}
    target={"species":"Dondozo","ability":"Unaware","boosts":{"def":2}}
    assert hit("bodypress",attacker,target)<hit("bodypress",attacker,{**target,"boosts":{}})


@pytest.mark.parametrize("breaker", ["Mold Breaker","Teravolt","Turboblaze"])
def test_gastroacid_suppresses_breaker_but_not_move_ability_bypass(breaker):
    attacker={"species":"Mew","ability":breaker,"boosts":{"atk":4},"effects":{"GASTRO_ACID":0}}
    target={"species":"Dondozo","ability":"Unaware"}
    assert hit("tackle",attacker,target)==hit("tackle",{**attacker,"boosts":{}},target)
    assert hit("sunsteelstrike",attacker,target)==hit("sunsteelstrike",attacker,{**target,"ability":None})


@pytest.mark.parametrize("key", [None,"active_pokemon","opponent_active_pokemon"])
def test_current_visible_gas_suppresses_unaware_but_ability_shield_protects(key):
    attacker={"species":"Dondozo","ability":"Unaware"}
    target={"species":"Archaludon","ability":"Neutralizing Gas" if key is None else "Stamina","boosts":{"def":4}}
    gas={"species":"Weezing","ability":"Neutralizing Gas"}
    observation={key:[gas]} if key else {}
    assert hit("waterfall",attacker,target,observation)==hit("waterfall",{**attacker,"ability":None},target,observation)
    shielded={**attacker,"item":"Ability Shield"}
    assert hit("waterfall",shielded,target,observation)==hit("waterfall",shielded,{**target,"boosts":{}},observation)


@pytest.mark.parametrize("gas_patch", [{"fainted":True},{"current_hp_fraction":0},{"effects":{"GASTRO_ACID":0}}])
def test_fainted_or_suppressed_visible_gas_does_not_suppress_unaware(gas_patch):
    attacker={"species":"Dondozo","ability":"Unaware"}
    target={"species":"Archaludon","boosts":{"def":4}}
    obs={"opponent_active_pokemon":[{"species":"Weezing","ability":"Neutralizing Gas",**gas_patch}]}
    assert hit("waterfall",attacker,target,obs)==hit("waterfall",attacker,{**target,"boosts":{}},obs)


def test_gas_suppresses_breaker_without_suppressing_shielded_unaware():
    attacker={"species":"Mew","ability":"Mold Breaker","boosts":{"atk":4}}
    target={"species":"Dondozo","ability":"Unaware","item":"Ability Shield"}
    obs={"active_pokemon":[{"species":"Weezing","ability":"Neutralizing Gas"}]}
    assert hit("tackle",attacker,target,obs)==hit("tackle",{**attacker,"boosts":{}},target,obs)
