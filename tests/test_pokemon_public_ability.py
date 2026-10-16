"""Public-card knowledge regressions; no simulated or claimed match wins."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from altruagent import LegalAction
from examples import pokemon_policy_v10 as policy


@pytest.mark.parametrize("species,ability,attack,attacker", [
    ("Bronzong", "Levitate", "earthquake", "Garchomp"),
    ("Heatran", "Flash Fire", "flamethrower", "Arcanine"),
    ("Clodsire", "Water Absorb", "hydropump", "Iron Bundle"),
    ("Gastrodon", "Storm Drain", "hydropump", "Iron Bundle"),
    ("Thundurus", "Volt Absorb", "thunderbolt", "Iron Valiant"),
    ("Raichu", "Lightning Rod", "thunderbolt", "Iron Valiant"),
    ("Goodra", "Sap Sipper", "energyball", "Hatterene"),
])
def test_public_immunity_is_used_before_api_reveals_it(species, ability, attack, attacker):
    target = {"species": species, "ability": None, "public_set": {"ability": ability}}
    assert policy.damage({"move_id": attack}, {"species": attacker}, target) == 0


def test_visible_replacement_overrides_original_immunity():
    mon = {"species": "Bronzong", "ability": "Heatproof", "public_set": {"ability": "Levitate"}}
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, mon) > 0


def test_explicit_empty_current_ability_is_not_replaced_by_draft():
    mon = {"species": "Bronzong", "ability": "", "public_set": {"ability": "Levitate"}}
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, mon) > 0


def test_missing_public_knowledge_does_not_guess_species_ability():
    mon = {"species": "Bronzong", "ability": None}
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, mon) > 0


@pytest.mark.parametrize("breaker", ["Mold Breaker", "Teravolt", "Turboblaze"])
@pytest.mark.parametrize("species,ability,attack", [
    ("Bronzong", "Levitate", "earthquake"),
    ("Clodsire", "Water Absorb", "hydropump"),
    ("Heatran", "Flash Fire", "flamethrower"),
])
def test_known_breaker_does_not_gain_false_immunity_from_public_fallback(breaker, species, ability, attack):
    attacker = {"species": "Haxorus", "ability": breaker}
    defender = {"species": species, "ability": None, "public_set": {"ability": ability}}
    assert policy.damage({"move_id": attack}, attacker, defender) > 0
    assert policy.damage({"move_id": attack}, {**attacker, "ability": None, "public_set": {"ability": breaker}}, defender) > 0
    # A currently visible Ability Shield preserves the defensive ability.
    assert policy.damage({"move_id": attack}, attacker, {**defender, "item": "Ability Shield"}) == 0
    # A draft item is not evidence that the item is still held.
    used = {**defender, "item": None, "public_set": {"ability": ability, "item": "Ability Shield"}}
    assert policy.damage({"move_id": attack}, attacker, used) > 0


def test_breaker_does_not_ignore_balloon_or_type_immunity():
    attacker = {"species": "Haxorus", "ability": "Mold Breaker"}
    assert policy.damage({"move_id": "earthquake"}, attacker, {"species": "Heatran", "item": "Air Balloon"}) == 0
    assert policy.damage({"move_id": "earthquake"}, attacker, {"species": "Gyarados"}) == 0
    assert policy.damage({"move_id": "thunderbolt"}, attacker, {"species": "Clodsire"}) == 0


def test_breaker_does_not_ignore_unbreakable_shadow_shield():
    attacker = {"species": "Hydreigon", "ability": "Mold Breaker"}
    target = {"species": "Lunala", "ability": None, "public_set": {"ability": "Shadow Shield"}}
    without = {"species": "Lunala"}
    assert policy.damage({"move_id": "darkpulse"}, attacker, target) == policy.damage({"move_id": "darkpulse"}, attacker, without) * .5


def test_public_levitate_controls_grounding_and_terrain_sleep():
    mon = {"species": "Cresselia", "ability": None, "public_set": {"ability": "Levitate"}}
    assert not policy.grounded(mon)
    assert policy._status_ok("hypnosis", mon, {}, {"fields": {"ELECTRIC_TERRAIN": 1}})


def test_breaker_grounding_respects_terrain_and_visible_shield():
    mon = {"species": "Cresselia", "ability": None, "public_set": {"ability": "Levitate"}}
    attacker = {"species": "Haxorus", "ability": "Mold Breaker"}
    electric = {"fields": {"ELECTRIC_TERRAIN": 1}}
    assert not policy._status_ok("hypnosis", mon, attacker, electric)
    assert policy._status_ok("hypnosis", {**mon, "item": "Ability Shield"}, attacker, electric)
    move = {"move_id": "earthquake"}
    grassy = {"fields": {"GRASSY_TERRAIN": 1}}
    assert policy.damage(move, attacker, mon, grassy) == .5 * policy.damage(move, attacker, mon)


def test_public_rain_speed_matches_revealed_ability():
    mon = {"species": "Kingdra", "ability": None, "public_set": {"ability": "Swift Swim"}}
    rain = {"weather": {"RAINDANCE": 1}}
    assert policy.speed(mon, rain, False) == policy.speed({**mon, "ability": "swiftswim"}, rain, False)
    assert policy.speed(mon, rain, False) == 2 * policy.speed(mon, {}, False)


def test_public_prankster_sets_priority_and_dark_immunity():
    mon = {"species": "Klefki", "ability": None, "public_set": {"ability": "Prankster"}}
    move = policy.move({"move_id": "thunderwave"}, {}, mon)
    assert move["priority"] == 1
    dark = {"species": "Incineroar"}
    assert policy._priority_blocked(mon, dark, {}, move, [dark])


def test_public_armor_tail_protects_foes_partner():
    guard = {"species": "Farigiraf", "ability": None, "public_set": {"ability": "Armor Tail"}}
    target = {"species": "Eevee"}
    fakeout = policy.move({"move_id": "fakeout"})
    assert policy._priority_blocked({"species": "Incineroar"}, target, {}, fakeout, [guard, target])


def test_public_storm_drain_redirects_away_from_fire_target():
    foes = [{"species": "Gastrodon", "ability": None, "public_set": {"ability": "Storm Drain"}},
            {"species": "Incineroar"}]
    choices = [{"type": "move", "move_id": m, "targets": [1, 2]} for m in ("hydropump", "icebeam")]
    action = LegalAction(action_id="doubles_turn", label="", input={"action": {"slots": [
        {"slot": 0, "active": {"species": "Iron Bundle"}, "options": choices},
        {"slot": 1, "active": {}, "options": [{"type": "pass"}]},
    ]}})
    state = SimpleNamespace(raw={"observation": {"turn": 1, "opponent_active_pokemon": foes}}, legal_actions=[action])
    assert policy.doubles(state)["slot_0"]["move_id"] == "icebeam"


def prepared_pair(lines=(), current=None, fields=None):
    instance = policy.PokemonPolicyV10()
    context = SimpleNamespace(session_id="same-public-match", agent_id="our-seat")
    draft = SimpleNamespace(raw={"observation": {"available_cards": [
        {"species": "Bronzong", "ability": "Levitate"},
        {"species": "Hatterene", "ability": "Magic Bounce"},
    ]}}, legal_actions=[])
    instance.prepare(draft, context)
    battle = SimpleNamespace(raw={"observation": {
        "protocol_log": list(lines), "fields": fields or {},
        "opponent_active_pokemon": [
            {"species": "Bronzong", "ability": current},
            {"species": "Hatterene", "ability": current},
        ]}}, legal_actions=[])
    return instance, context, battle


@pytest.mark.parametrize("line", [
    "|-endability|p2a: Bronzong",
    "|-ability|p1a: Weezing|Neutralizing Gas",
    "|-end|p1a: Weezing|ability: Neutralizing Gas",
    "|-ability|p2a: Bronzong|Insomnia|[from] move: Worry Seed",
    "|-activate|p2a: Bronzong|move: Skill Swap|||[of] p2b: Hatterene",
    "|-activate|p2a: Bronzong|Skill Swap|||[of] p2b: Hatterene",
    "|-activate|p2a: Bronzong|ability: Mummy|Levitate|[of] p1a: Cofagrigus",
    "|-activate|p2a: Bronzong|ability: Lingering Aroma|Levitate|[of] p1a: Oinkologne",
    "|-activate|p2a: Bronzong|ability: Wandering Spirit|Levitate|[of] p1a: Runerigus",
    "|-transform|p2a: Bronzong|p1a: Ditto",
    "|detailschange|p2a: Bronzong|Other Forme",
    "|-formechange|p2a: Bronzong|Other Forme",
])
def test_public_mutation_or_suppression_disables_original_card_fallback(line):
    instance, context, battle = prepared_pair([line])
    untouched = deepcopy(battle.raw)
    got = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"]
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, got[0]) > 0
    assert policy._status_ok("hypnosis", got[1], {}, {})
    assert battle.raw == untouched
    # An event falling out of a truncated protocol window must not re-enable it.
    battle.raw["observation"]["protocol_log"] = ["|turn|8"]
    later = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"]
    assert policy._status_ok("hypnosis", later[1], {}, {})


def test_neutralizing_gas_field_alone_disables_card_fallback():
    instance, context, battle = prepared_pair(fields={"NEUTRALIZING_GAS": 1})
    got = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"]
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, got[0]) > 0
    assert policy._status_ok("hypnosis", got[1], {}, {})


def test_public_gastro_acid_effect_disables_card_fallback():
    instance, context, battle = prepared_pair()
    battle.raw["observation"]["opponent_active_pokemon"][0]["effects"] = {"GASTRO_ACID": 1}
    got = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"]
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, got[0]) > 0
    assert policy._status_ok("hypnosis", got[1], {}, {})


def test_revealed_current_replacement_survives_conservative_fallback_guard():
    instance, context, battle = prepared_pair(["|-activate|p2a: Bronzong|move: Skill Swap"], "Magic Bounce")
    got = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"]
    assert not policy._status_ok("hypnosis", got[1], {}, {})


def test_guard_does_not_cross_match_or_seat():
    instance, context, battle = prepared_pair(["|-endability|p2a: Bronzong"])
    instance.prepare(battle, context)
    clean, _, clean_battle = prepared_pair()
    for other in (SimpleNamespace(session_id="new-match", agent_id="our-seat"),
                  SimpleNamespace(session_id="same-public-match", agent_id="other-seat")):
        draft = SimpleNamespace(raw={"observation": {"available_cards": [{"species": "Bronzong", "ability": "Levitate"}]}}, legal_actions=[])
        instance.prepare(draft, other)
        got = instance.prepare(clean_battle, other).raw["observation"]["opponent_active_pokemon"][0]
        assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, got) == 0


def test_ordinary_public_ability_announcement_does_not_disable_fallback():
    instance, context, battle = prepared_pair(["|-ability|p1a: Chien-Pao|Sword of Ruin"])
    got = instance.prepare(battle, context).raw["observation"]["opponent_active_pokemon"][0]
    assert policy.damage({"move_id": "earthquake"}, {"species": "Garchomp"}, got) == 0
