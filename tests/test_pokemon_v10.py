"""Concrete participant-view regressions; these are not measured win rates."""
from copy import deepcopy
from types import SimpleNamespace

from altruagent import LegalAction
from test_free_multigame_agent_v2 import opt, scenario
from examples.pokemon_policy_v9 import doubles as v9_doubles
from examples.pokemon_policy_v10 import (PokemonPolicyV10, damage, doubles, draft_pick,
                                        lineup, move, _own_history)


def battle(moves, foes, active="Incineroar", partner_moves=None, partner="Pelipper", turn=1):
    s = scenario(moves, partner_moves, {"species":active})
    s.raw["observation"]={"turn":turn,"opponent_active_pokemon":deepcopy(foes)}
    s.legal_actions[0].input["action"]["slots"][1]["active"]={"species":partner}
    return s


def test_weather_ball_in_rain_is_stab_water_100_power():
    m=move({"move_id":"weatherball","base_power":50,"move_type":"NORMAL"},{"weather":{"RAINDANCE":0}})
    assert (m["type"],m["power"]) == ("water",100)


def test_hurricane_rain_removes_accuracy_discount():
    a={"species":"Pelipper"}; d={"species":"Rillaboom"}
    assert damage({"move_id":"hurricane"},a,d,{"weather":{"RAINDANCE":0}}) > damage({"move_id":"hurricane"},a,d,{})*1.4


def test_loaded_dice_multihit_not_scored_as_one_hit():
    a=move({"move_id":"iciclespear"},{},{"item":"Loaded Dice"})
    assert a["power"] == 112.5


def test_fakeout_not_used_after_first_turn():
    s=battle([opt("fakeout",opponents=("Arcanine",)),opt("tackle",opponents=("Arcanine",))], [{"species":"Arcanine"}],turn=2)
    assert doubles(s)["slot_0"]["move_id"] == "tackle"
    assert v9_doubles(s)["slot_0"]["move_id"] == "fakeout"


def test_fakeout_available_after_public_switch_but_not_later_turn():
    o={"turn":4,"team":{"p2: Incineroar":{}},"protocol_log":["|turn|3","|switch|p2a: Incineroar|Incineroar|100/100","|turn|4"]}
    assert _own_history(o,0)[0]
    o["protocol_log"] += ["|cant|p2a: Incineroar|slp", "|turn|5"]
    o["turn"]=5
    assert not _own_history(o,0)[0]


def test_fakeout_flanks_fast_threat_to_save_ally():
    foes=[{"species":"Iron Valiant","moves":["thunderbolt"],"current_hp_fraction":1},
          {"species":"Toxapex","moves":["liquidation"],"current_hp_fraction":1}]
    s=battle([opt("fakeout",opponents=("Iron Valiant","Toxapex")),opt("flareblitz",opponents=("Iron Valiant","Toxapex"))],foes,
             partner_moves=[opt("hurricane",opponents=("Iron Valiant","Toxapex"))])
    s.raw["observation"]["weather"]={"RAINDANCE":0}
    chosen=doubles(s)
    assert chosen["slot_0"] == {"type":"move","move_id":"fakeout","target":1}
    assert chosen["slot_1"]["move_id"] == "hurricane"


def test_joint_targeting_does_not_overkill_already_dying_target():
    foes=[{"species":"Gyarados","current_hp_fraction":.05},{"species":"Gyarados","current_hp_fraction":1}]
    attacks=[opt("thunderbolt",opponents=("Gyarados","Gyarados"))]
    s=battle(attacks,foes,active="Thundurus",partner="Thundurus",partner_moves=attacks)
    old=v9_doubles(s); chosen=doubles(s)
    assert old["slot_0"]["target"] == old["slot_1"]["target"] == 1
    assert {chosen["slot_0"]["target"],chosen["slot_1"]["target"]} == {1,2}


def test_no_repeating_tailwind_when_already_active():
    s=battle([opt("tailwind",targets=(0,)),opt("airslash",opponents=("Toxapex",))],[{"species":"Toxapex"}],active="Tornadus")
    s.raw["observation"]["side_conditions"]={"TAILWIND":1}
    assert doubles(s)["slot_0"]["move_id"] == "airslash"


def test_no_repeating_screen_when_already_active():
    s=battle([opt("reflect",targets=(0,)),opt("tackle",opponents=("Toxapex",))],[{"species":"Toxapex"}],active="Grimmsnarl")
    s.raw["observation"]["side_conditions"]={"REFLECT":1}
    assert doubles(s)["slot_0"]["move_id"] == "tackle"


def test_do_not_recover_at_full_hp():
    s=battle([opt("recover",targets=(0,)),opt("tackle",opponents=("Toxapex",))],[{"species":"Toxapex"}],active="Porygon2")
    assert doubles(s)["slot_0"]["move_id"] == "tackle"


def test_spore_rejected_against_goggles_and_grass():
    s=battle([opt("spore",opponents=("Incineroar","Rillaboom")),opt("sludgebomb",opponents=("Incineroar","Rillaboom"))],
             [{"species":"Incineroar","item":"Safety Goggles"},{"species":"Rillaboom"}],active="Amoonguss")
    assert doubles(s)["slot_0"]["move_id"] == "sludgebomb"


def test_sleeping_target_not_spored_again():
    s=battle([opt("spore",opponents=("Toxapex",)),opt("sludgebomb",opponents=("Toxapex",))],[{"species":"Toxapex","status":"slp"}],active="Amoonguss")
    assert doubles(s)["slot_0"]["move_id"] == "sludgebomb"


def test_psychic_terrain_blocks_fakeout():
    s=battle([opt("fakeout",opponents=("Iron Valiant",)),opt("knockoff",opponents=("Iron Valiant",))],[{"species":"Iron Valiant"}])
    s.raw["observation"]["fields"]={"PSYCHIC_TERRAIN":0}
    assert doubles(s)["slot_0"]["move_id"] == "knockoff"


def test_prankster_status_does_not_target_dark_type():
    s=battle([opt("thunderwave",opponents=("Incineroar",)),opt("tackle",opponents=("Incineroar",))],[{"species":"Incineroar"}],active="Grimmsnarl")
    s.legal_actions[0].input["action"]["slots"][0]["active"]["ability"]="Prankster"
    assert doubles(s)["slot_0"]["move_id"] == "tackle"


def test_storm_drain_redirects_water_away_from_fire_partner():
    s=battle([opt("hydropump",opponents=("Gastrodon","Incineroar")),opt("icebeam",opponents=("Gastrodon","Incineroar"))],
             [{"species":"Gastrodon","ability":"Storm Drain"},{"species":"Incineroar"}],active="Iron Bundle")
    assert doubles(s)["slot_0"]["move_id"] == "icebeam"


def test_actual_rain_weather_ball_beats_hurricane_against_fire():
    s=battle([opt("hurricane",opponents=("Arcanine",)),opt("weatherball",power=50,opponents=("Arcanine",))],[{"species":"Arcanine"}],active="Pelipper")
    s.raw["observation"]["weather"]={"RAINDANCE":0}
    assert v9_doubles(s)["slot_0"]["move_id"] == "hurricane"
    assert doubles(s)["slot_0"]["move_id"] == "weatherball"


def test_foul_play_uses_target_attack():
    option={"move_id":"foulplay"}; a={"species":"Wo-Chien"}
    weak={"species":"Porygon2","base_stats":{"atk":20,"def":90,"hp":85}}
    strong={"species":"Porygon2","base_stats":{"atk":180,"def":90,"hp":85}}
    assert damage(option,a,strong)>damage(option,a,weak)*2


def test_forced_switch_pair_keeps_only_legal_distinct_replacements():
    s=scenario([{"type":"switch","species":"Gyarados"},{"type":"switch","species":"Incineroar"}],
               [{"type":"switch","species":"Gyarados"}])
    action=doubles(s)
    assert action["slot_0"]["species"] == "Incineroar"
    assert action["slot_1"]["species"] == "Gyarados"


def test_public_card_cache_is_scoped_and_does_not_mutate_state():
    policy=PokemonPolicyV10()
    card={"species":"Iron Valiant","moves":["Thunderbolt"],"evs":{"spa":252}}
    state=SimpleNamespace(raw={"observation":{"available_cards":[card]}},legal_actions=[])
    a=SimpleNamespace(session_id="matchA",agent_id="our-seat")
    b=SimpleNamespace(session_id="matchB",agent_id="our-seat")
    policy.prepare(state,a)
    s=battle([opt("hurricane",opponents=("Iron Valiant",))],[{"species":"Iron Valiant","moves":[]}])
    prepared=policy.prepare(s,a)
    assert prepared.raw["observation"]["opponent_active_pokemon"][0]["public_set"]["moves"] == ["Thunderbolt"]
    assert "public_set" not in s.raw["observation"]["opponent_active_pokemon"][0]
    assert "public_set" not in policy.prepare(s,b).raw["observation"]["opponent_active_pokemon"][0]


def test_draft_prefers_damage_carry_over_passive_wall():
    cards=[{"card_id":"tox","species":"Toxapex","moves":["Liquidation","Haze","Toxic","Protect"]},
           {"card_id":"flutter","species":"Flutter Mane","moves":["Moonblast","Shadow Ball","Icy Wind","Protect"]}]
    actions=[LegalAction(action_id="draft_pick:"+x["card_id"],label="",input={}) for x in cards]
    s=SimpleNamespace(raw={"observation":{"available_cards":cards,"my_roster":["Grimmsnarl","Amoonguss"],"opponent_roster":["Garchomp","Iron Hands"]}},legal_actions=actions)
    assert draft_pick(s).action_id == "draft_pick:flutter"


def test_lineup_avoids_four_support_pokemon():
    roster=["Grimmsnarl","Amoonguss","Cresselia","Klefki","Flutter Mane","Urshifu-Rapid-Strike"]
    action=LegalAction(action_id="select_lineup",label="",input={"action":{"roster":roster}})
    s=SimpleNamespace(raw={"observation":{"your_roster":[{"species":x} for x in roster],"opponent_roster":["Garchomp","Incineroar","Iron Hands","Kingambit"]}},legal_actions=[action])
    chosen=lineup(s)
    assert {"Flutter Mane","Urshifu-Rapid-Strike"} <= set(chosen["bring"])
    assert not set(chosen["leads"]) <= {"Grimmsnarl","Amoonguss","Cresselia","Klefki"}


def test_v8_friendly_fire_regressions_remain_safe(monkeypatch):
    import test_super_war_dragon_v8 as old
    monkeypatch.setattr(old,"doubles",doubles)
    for case in (old.test_replay_earthquake_must_not_ignore_grass_foes_and_fire_ally,
                 old.test_ground_spread_has_zero_value_into_two_flying_foes,
                 old.test_spread_still_used_when_effective_and_ally_immune,
                 old.test_spread_uses_visible_current_types):
        case()


def test_joint_protect_when_earthquake_is_the_available_damage():
    s=battle([opt("earthquake",targets=(0,),opponents=("Iron Hands","Incineroar"))],
             [{"species":"Iron Hands"},{"species":"Incineroar"}],active="Garchomp",partner="Incineroar",
             partner_moves=[opt("tackle",opponents=("Iron Hands","Incineroar")),opt("protect",targets=(0,))])
    assert doubles(s)["slot_1"]["move_id"] == "protect"


def test_unknown_shape_returns_none_for_verified_entrypoint_fallback():
    assert doubles(SimpleNamespace(raw={},legal_actions=[])) is None


def test_visible_air_balloon_blocks_ground_damage_until_popped():
    attacker={"species":"Garchomp"}
    defender={"species":"Heatran","item":"Air Balloon"}
    assert damage({"move_id":"earthquake"},attacker,defender) == 0
    assert damage({"move_id":"earthquake"},attacker,{**defender,"item":None}) > 0


def test_air_balloon_changes_selected_attack_to_non_ground():
    s=battle([opt("earthquake",targets=(0,),opponents=("Heatran",)),opt("dragonclaw",opponents=("Heatran",))],
             [{"species":"Heatran","item":"airballoon"}],active="Garchomp")
    assert doubles(s)["slot_0"]["move_id"] == "dragonclaw"


def test_hypnosis_does_not_repeat_against_sleeping_target():
    s=battle([opt("hypnosis",opponents=("Toxapex",)),opt("tackle",opponents=("Toxapex",))],
             [{"species":"Toxapex","status":"slp"}],active="Cresselia")
    assert doubles(s)["slot_0"]["move_id"] == "tackle"


def test_hypnosis_remains_valid_against_grass_with_goggles():
    from examples.pokemon_policy_v10 import _status_ok
    assert _status_ok("hypnosis",{"species":"Rillaboom","item":"Safety Goggles"},{},{})
    assert not _status_ok("hypnosis",{"species":"Toxapex","status":"par"},{},{})
    assert not _status_ok("hypnosis",{"species":"Toxapex","ability":"Insomnia"},{},{})


def paradox_state(extra=()):
    """Sanitized shape of the completed V8 own-seat first-turn observation."""
    s=battle([opt("moonblast",opponents=("Iron Valiant",))],
             [{"species":"Iron Valiant","name":"Iron Valiant","ability":"quarkdrive","item":None}],active="Flutter Mane")
    own=s.legal_actions[0].input["action"]["slots"][0]["active"]
    own.update(name="Flutter Mane",ability="protosynthesis",item="boosterenergy",active=True)
    s.raw["observation"].update(team={"p2: Flutter Mane":deepcopy(own)},active_pokemon=[deepcopy(own)],
        protocol_log=["|switch|p1a: Iron Valiant|Iron Valiant, L50|100/100",
                      "|-enditem|p1a: Iron Valiant|Booster Energy",
                      "|-activate|p1a: Iron Valiant|ability: Quark Drive|[fromitem]",
                      "|-start|p1a: Iron Valiant|quarkdrivespe",*extra])
    return s


def test_visible_quarkdrive_speed_applies_without_draft_cache():
    from examples.pokemon_policy_v10 import speed
    state=paradox_state()
    policy=PokemonPolicyV10()
    prepared=policy.prepare(state,SimpleNamespace(session_id="no-draft",agent_id="me"))
    raw=state.raw["observation"]; obs=prepared.raw["observation"]
    assert speed(obs["opponent_active_pokemon"][0],obs,False) == speed(raw["opponent_active_pokemon"][0],raw,False)*1.5
    assert "_public_stat_boosts" not in raw["opponent_active_pokemon"][0]
    assert "_public_stat_boosts" not in obs["active_pokemon"][0]  # item alone is not activation evidence


def test_protosynthesis_attack_boost_reaches_legal_active_descriptor():
    from examples.pokemon_policy_v10 import stat
    state=paradox_state(["|-start|p2a: Flutter Mane|protosynthesisspa"])
    prepared=PokemonPolicyV10().prepare(state,SimpleNamespace())
    raw=state.legal_actions[0].input["action"]["slots"][0]["active"]
    active=prepared.legal_actions[0].input["action"]["slots"][0]["active"]
    assert stat(active,"spa") == stat(raw,"spa")*1.3
    assert stat(active,"spe") == stat(raw,"spe")


def test_visible_paradox_effect_clears_on_end_or_slot_replacement():
    from examples.pokemon_policy_v10 import _public_stat_effects
    endings=["|-end|p1a: Iron Valiant|Quark Drive|[silent]",
             "|switch|p1a: Iron Valiant|Iron Valiant, L50|100/100",
             "|drag|p1a: Rillaboom|Rillaboom, L50|100/100",
             "|replace|p1a: Zoroark|Zoroark, L50|100/100",
             "|faint|p1a: Iron Valiant"]
    for ending in endings:
        state=paradox_state([ending])
        assert "p1a" not in _public_stat_effects(state.raw["observation"])
        prepared=PokemonPolicyV10().prepare(state,SimpleNamespace())
        assert "_public_stat_boosts" not in prepared.raw["observation"]["opponent_active_pokemon"][0]


def test_end_only_clears_matching_side_and_new_start_can_reactivate():
    from examples.pokemon_policy_v10 import _public_stat_effects
    state=paradox_state(["|-start|p2a: Flutter Mane|protosynthesisspa",
                         "|-end|p2a: Flutter Mane|Protosynthesis",
                         "|-end|p1a: Iron Valiant|Quark Drive",
                         "|-start|p1a: Iron Valiant|quarkdriveatk"])
    effects=_public_stat_effects(state.raw["observation"])
    assert effects == {"p1a":{"label":"ironvaliant","ability":"quarkdrive","stat":"atk"}}


def forced_replacements(bench=("pelipper",), both=True):
    """A bad switch matchup must not make a mandatory replacement optional."""
    options = [{"type":"switch", "species":s} for s in bench] + [{"type":"pass"}]
    state = battle(options, [{"species":"ironvaliant", "moves":["thunderbolt"]}],
                   active="rillaboom", partner="archaludon", turn=5,
                   partner_moves=deepcopy(options) if both else [{"type":"pass"}])
    for i, slot in enumerate(state.legal_actions[0].input["action"]["slots"]):
        slot["force_switch"] = i == 0 or both
        if slot["force_switch"]:
            slot["active"].update(fainted=True, current_hp_fraction=0)
    state.raw["observation"]["team"] = {
        "p1: "+s:{"species":s, "moves":["hurricane"], "current_hp_fraction":1}
        for s in bench}
    return state


def test_double_forced_replacement_with_one_reserve_cannot_pass_twice():
    action = doubles(forced_replacements())
    choices = [action["slot_0"], action["slot_1"]]
    assert choices.count({"type":"pass"}) == 1
    assert choices.count({"type":"switch", "species":"pelipper"}) == 1


def test_double_forced_replacement_uses_two_distinct_reserves():
    action = doubles(forced_replacements(("pelipper", "gyarados")))
    choices = [action["slot_0"], action["slot_1"]]
    assert all(c["type"] == "switch" for c in choices)
    assert {c["species"] for c in choices} == {"pelipper", "gyarados"}


def test_single_forced_replacement_keeps_other_slots_required_pass():
    action = doubles(forced_replacements(both=False))
    assert action["slot_0"] == {"type":"switch", "species":"pelipper"}
    assert action["slot_1"] == {"type":"pass"}


def test_forced_replacement_without_legal_reserves_does_not_invent_switches():
    action = doubles(forced_replacements(()))
    assert action["slot_0"] == action["slot_1"] == {"type":"pass"}


def test_forced_replacement_preserves_each_slots_legal_choices():
    state = forced_replacements(("pelipper", "gyarados"))
    state.legal_actions[0].input["action"]["slots"][1]["options"] = [
        {"type":"switch", "species":"pelipper"}, {"type":"pass"}]
    action = doubles(state)
    assert action["slot_0"] == {"type":"switch", "species":"gyarados"}
    assert action["slot_1"] == {"type":"switch", "species":"pelipper"}


def test_public_draft_magic_bounce_blocks_unrevealed_status_targets():
    from examples.pokemon_policy_v10 import _status_ok
    foe = {"species":"Hatterene", "ability":None, "item":"unknown_item",
           "public_set":{"ability":"Magic Bounce", "item":"Safety Goggles"}}
    for name in ("spore", "hypnosis", "taunt", "partingshot", "thunderwave"):
        assert not _status_ok(name, foe, {}, {})
    # An actually revealed replacement ability takes precedence over the draft.
    assert _status_ok("hypnosis", {**foe, "ability":"Healer"}, {}, {})
    assert _status_ok("hypnosis", {"species":"Hatterene", "ability":None}, {}, {})


def test_completed_selfplay_shape_does_not_spore_public_magic_bounce():
    policy = PokemonPolicyV10()
    context = SimpleNamespace(session_id="completed-selfplay", agent_id="our-seat")
    draft = SimpleNamespace(raw={"observation":{"available_cards":[
        {"species":"Hatterene", "ability":"Magic Bounce", "item":"Safety Goggles"}]}}, legal_actions=[])
    policy.prepare(draft, context)
    state = battle([opt("spore", opponents=("Hatterene",)), opt("sludgebomb", opponents=("Hatterene",))],
                   [{"species":"Hatterene", "ability":None, "item":"unknown_item", "current_hp_fraction":.44}],
                   active="Amoonguss", turn=2)
    prepared = policy.prepare(state, context)
    assert doubles(prepared)["slot_0"]["move_id"] == "sludgebomb"


def test_public_original_items_do_not_restore_consumed_immunity():
    from examples.pokemon_policy_v10 import _status_ok
    for current in (None, "", "unknown_item"):
        foe = {"species":"Toxapex", "item":current, "public_set":{"item":"Safety Goggles"}}
        assert _status_ok("spore", foe, {}, {})
        balloon = {"species":"Heatran", "item":current, "public_set":{"item":"Air Balloon"}}
        assert damage({"move_id":"earthquake"}, {"species":"Garchomp"}, balloon) > 0


def test_lone_amoonguss_does_not_redirect_for_empty_or_fainted_partner():
    # Completed external game turn 8: only Amoonguss remains, against the
    # sleeping Archaludon; slot 0 is None and its only legal action is pass.
    for missing in (None, {"species":"Lucario", "fainted":True, "current_hp_fraction":0}):
        for redirect in ("ragepowder", "followme"):
            state = battle([{"type":"pass"}],
                           [{"species":"Archaludon", "status":"SLP", "current_hp_fraction":.6,
                             "moves":["bodypress"], "boosts":{"def":3, "spa":-4}}, None],
                           partner="Amoonguss", turn=8,
                           partner_moves=[opt(redirect, targets=(0,)), opt("pollenpuff", targets=(1,), opponents=("Archaludon",))])
            slots = state.legal_actions[0].input["action"]["slots"]
            slots[0]["active"] = missing
            slots[1]["active"].update(current_hp_fraction=93/220)
            assert doubles(state)["slot_1"]["move_id"] == "pollenpuff"
