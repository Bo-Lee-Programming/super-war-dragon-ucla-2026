"""Tests of the actual public Pokemon payload shapes captured in Testing."""
from types import SimpleNamespace

from test_free_multigame_agent_v2 import scenario, opt
from examples.pokemon_policy_v9 import doubles, damage_factor
from examples.free_multigame_agent_v9 import normalize_pokemon


def test_depleted_special_attack_changes_move_choice():
    special = dict(opt("dracometeor", opponents=("Arcanine",)), category="SPECIAL")
    physical = dict(opt("dragonclaw", opponents=("Arcanine",)), category="PHYSICAL")
    state = scenario([special,physical], active={"species":"Salamence", "boosts":{"spa":-4}})
    assert doubles(state)["slot_0"]["move_id"] == "dragonclaw"


def test_live_opponent_type_overrides_stale_species_hint():
    state = scenario([opt("thunderbolt", opponents=("Gyarados","Arcanine"))])
    state.raw["observation"] = {"opponent_active_pokemon":[
        {"species":"Gyarados", "types":["GROUND"]}, {"species":"Arcanine", "types":["WATER"]}]}
    assert doubles(state)["slot_0"]["target"] == 2


def test_visible_ability_from_observation_blocks_ground():
    state = scenario([opt("earthpower", opponents=("Rotom-Wash",)), opt("icebeam", opponents=("Rotom-Wash",))])
    state.raw["observation"] = {"opponent_active_pokemon":[{"species":"Rotom-Wash","ability":"Levitate"}]}
    assert doubles(state)["slot_0"]["move_id"] == "icebeam"


def test_weather_map_zero_value_still_means_rain_is_active():
    assert damage_factor({"move_id":"flareblitz","category":"PHYSICAL"},{},{},{"weather":{"RAINDANCE":0}}) == .5


def test_grassy_field_zero_value_halves_grounded_earthquake():
    move={"move_id":"earthquake","category":"PHYSICAL"}
    assert damage_factor(move,{}, {"species":"Incineroar"},{"fields":{"GRASSY_TERRAIN":0}}) == .5
    assert damage_factor(move,{}, {"species":"Gyarados"},{"fields":{"GRASSY_TERRAIN":0}}) == 1.


def test_physical_defense_boost_reduces_damage_proxy():
    move={"move_id":"closecombat","category":"PHYSICAL"}
    assert damage_factor(move,{}, {"boosts":{"def":2}}, {}) == .5


def test_draft_rosters_keyed_by_agent_id_are_resolved_without_mutation():
    raw = {"observation":{"rosters":{"other":[{"species":"Rillaboom"}], "ours":[{"species":"Incineroar"}]}}}
    state = SimpleNamespace(raw=raw)
    normalized = normalize_pokemon(state, SimpleNamespace(agent_id="ours"))
    assert normalized.raw["observation"]["my_roster"] == [{"species":"Incineroar"}]
    assert normalized.raw["observation"]["opponent_roster"] == [{"species":"Rillaboom"}]
    assert "my_roster" not in raw["observation"]


def test_v8_spread_regressions_still_pass(monkeypatch):
    import test_super_war_dragon_v8 as old
    monkeypatch.setattr(old, "doubles", doubles)
    for case in (old.test_replay_earthquake_must_not_ignore_grass_foes_and_fire_ally,
                 old.test_ground_spread_has_zero_value_into_two_flying_foes,
                 old.test_spread_still_used_when_effective_and_ally_immune,
                 old.test_joint_search_can_protect_ground_weak_partner,
                 old.test_spread_uses_visible_current_types):
        case()
