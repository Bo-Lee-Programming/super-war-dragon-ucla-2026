"""Regression scenarios, not official match results or measured win rates."""
from types import SimpleNamespace

from altruagent import LegalAction, TERMINATE_MESSAGING
from examples.free_multigame_agent_v6 import SuperWarDragonV6
from examples.free_multigame_agent_v7 import SuperWarDragonV7
from examples.fast_redalert_agent_v6 import FastRedAlertV6
from examples.fast_redalert_agent_v7 import FastRedAlertV7
from examples.pokemon_policy_v7 import exposure
from test_super_war_dragon_v6 import make, actor, orders, has
from test_free_multigame_agent_v2 import scenario, opt

PK = SimpleNamespace(game_type="pokemon_vgc_doubles_draft")
WW = SimpleNamespace(game_type="werewolf")


def test_vehicle_cannot_spend_economy_reserve():
    st, ctx = make(money=1200, units=[actor("harv", 90)],
                   buildings=("fact", "powr", "barr", "proc", "weap", "fix"))
    assert has(orders(FastRedAlertV6().choose_action(st, ctx)), "train", "2tnk")
    assert not has(orders(FastRedAlertV7().choose_action(st, ctx)), "train", "2tnk")


def test_sole_harvester_replacement_before_optional_building():
    st, ctx = make(money=1100, units=[], build=())
    assert not has(orders(FastRedAlertV6().choose_action(st, ctx)), "train", "harv")
    assert has(orders(FastRedAlertV7().choose_action(st, ctx)), "train", "harv")


def test_lost_yard_does_not_disable_surviving_defense():
    st, ctx = make(buildings=("powr", "barr", "proc", "weap"),
                   units=[actor("e1", 91, idle=True)], enemies=[actor("e1", 900, 15, 10)])
    assert not orders(FastRedAlertV6().choose_action(st, ctx))
    assert has(orders(FastRedAlertV7().choose_action(st, ctx)), "attack_move")


def test_opening_saves_for_first_refinery():
    st, ctx = make(money=900, buildings=("fact", "powr", "barr"), build=("proc",))
    assert has(orders(FastRedAlertV6().choose_action(st, ctx)), "train", "e1")
    assert not has(orders(FastRedAlertV7().choose_action(st, ctx)), "train", "e1")


def test_forced_switch_pair_reserves_only_replacement_for_other_slot():
    st = scenario([{"type": "switch", "species": "A"}, {"type": "switch", "species": "B"}],
                  [{"type": "switch", "species": "A"}])
    new = SuperWarDragonV7().choose_action(st, PK)
    assert new["slot_0"] == {"type": "switch", "species": "B"}
    assert new["slot_1"] == {"type": "switch", "species": "A"}


def test_icy_wind_is_not_zero_damage_status_move():
    st = scenario([opt("icywind", targets=(1,), opponents=("Garchomp",)),
                   opt("protect", targets=(0,))])
    assert SuperWarDragonV6().choose_action(st, PK)["slot_0"]["move_id"] == "protect"
    assert SuperWarDragonV7().choose_action(st, PK)["slot_0"]["move_id"] == "icywind"


def test_only_observed_ability_blocks_ground_attack():
    move = opt("earthpower", targets=(1,), opponents=("Rotom-Wash",))
    move["target_options"][0]["ability"] = "Levitate"
    st = scenario([move, opt("energyball", targets=(1,), opponents=("Rotom-Wash",))])
    assert SuperWarDragonV7().choose_action(st, PK)["slot_0"]["move_id"] == "energyball"


def test_status_immunities_use_current_types():
    st = scenario([opt("thunderwave", targets=(1,), opponents=("Garchomp",)),
                   opt("protect", targets=(0,))])
    assert SuperWarDragonV7().choose_action(st, PK)["slot_0"]["move_id"] == "protect"


def test_electric_roster_has_resistant_answer_and_not_two_weak_leads():
    roster = ["ironbundle", "tornadus", "gyarados", "klefki", "garchomp", "amoonguss"]
    template = {"type": "select_lineup", "roster": roster}
    st = SimpleNamespace(legal_actions=[LegalAction("select_lineup", "preview", {"action": template})],
                         raw={"observation": {"opponent_roster": ["ironhands", "thundurus"]}})
    got = SuperWarDragonV7().choose_action(st, PK)
    assert len(set(got["bring"])) == 4
    assert set(got["leads"]) <= set(got["bring"])
    assert "garchomp" in got["bring"] or "amoonguss" in got["bring"]
    assert exposure(got["leads"], ["ironhands", "thundurus"]) == 0


def wolf_state():
    return SimpleNamespace(raw={"your_position": 0,
        "observation": {"role": "seer", "investigations": [
            {"seat": 1, "role": "wolf"}, {"seat": 5, "role": "wolf"}]},
        "game_state": {"day": 3, "phase": "day_vote", "dead": [
            {"position": 1, "name": "Player1", "role": "wolf"}], "vote_history": []}},
        legal_actions=[], new_messages=[])


def test_seer_announces_living_wolf_not_old_dead_finding():
    st = wolf_state()
    old = SuperWarDragonV6().choose_message(st, WW)
    new_agent = SuperWarDragonV7()
    new = new_agent.choose_message(st, WW)
    assert "Player1" in old.content
    assert "Player5" in new.content and "Player1" not in new.content
    assert len(new.content.split()) <= 50
    assert new_agent.choose_message(st, WW) is TERMINATE_MESSAGING


def test_eliminated_seer_does_not_message():
    st = wolf_state()
    st.raw["eliminated"] = True
    assert SuperWarDragonV7().choose_message(st, WW) is TERMINATE_MESSAGING


def test_v7_randomized_redalert_batches(monkeypatch):
    import test_super_war_dragon_v6_fuzz as fixtures
    monkeypatch.setattr(fixtures, "FastRedAlertV6", FastRedAlertV7)
    fixtures.test_random_legal_batches()


def test_v7_existing_pokemon_target_contracts():
    from scripts.evaluate_pokemon_targets_1012 import PAIRS, state
    for move, a, b, preferred in PAIRS:
        for opponents in ((a, b), (b, a)):
            result = SuperWarDragonV7().choose_action(state(move, opponents), PK)
            assert result["slot_0"]["target"] == opponents.index(preferred) + 1


def test_live_failure_draco_meteor_never_targets_fairy_when_neutral_target_exists():
    st = scenario([opt("dracometeor", opponents=("Iron Valiant", "Incineroar"))])
    assert SuperWarDragonV6().choose_action(st, PK)["slot_0"]["target"] == 1
    assert SuperWarDragonV7().choose_action(st, PK)["slot_0"]["target"] == 2


def test_freeze_dry_targets_water_not_fire_and_uses_special_water_matchup():
    st = scenario([opt("freezedry", opponents=("Incineroar", "Gyarados")),
                   opt("icebeam", opponents=("Incineroar", "Gyarados"))],
                  active={"species": "Iron Bundle"})
    chosen = SuperWarDragonV7().choose_action(st, PK)["slot_0"]
    assert chosen == {"type": "move", "move_id": "freezedry", "target": 2}
