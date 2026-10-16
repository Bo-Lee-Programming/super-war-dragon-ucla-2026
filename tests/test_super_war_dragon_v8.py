"""Regressions derived from completed V7 platform replays."""
from test_free_multigame_agent_v2 import scenario, opt
from examples.pokemon_policy_v7 import doubles as old_doubles
from examples.pokemon_policy_v8 import doubles
from examples.fast_redalert_agent_v7 import FastRedAlertV7
from examples.fast_redalert_agent_v8 import FastRedAlertV8
from test_super_war_dragon_v6 import make, orders, has
from types import SimpleNamespace
from altruagent import LegalAction
from examples.free_multigame_agent_v8 import SuperWarDragonV8, normalize_werewolf


def werewolf(role, extra, phase="day_vote"):
    return SimpleNamespace(raw={"observation":f"=== Werewolf ===\nYour role: {role}\n{extra}\n\nDay 2 | phase {phase} | alive 7/7",
        "your_position":4, "players":[{"position":i,"name":f"Player{i}"} for i in range(7)],
        "game_state":{"phase":phase,"day":2,"dead":[],"vote_history":[]}},
        legal_actions=[LegalAction(action_id=str(i),label=None,input={}) for i in (0,1,2,3,5,6,7)])


def test_real_text_seer_finding_changes_vote_and_message():
    state = werewolf("SEER", "Your investigations: Player0 is villager, Player5 is wolf")
    agent = SuperWarDragonV8()
    context = SimpleNamespace(game_type="werewolf")
    assert agent.choose_action(state, context).action_id == "5"
    assert "Player5 is a wolf" in agent.choose_message(state, context).content
    assert isinstance(state.raw["observation"], str)


def test_real_text_known_innocent_not_reinvestigated():
    state = werewolf("SEER", "Your investigations: Player0 is villager", "night_seer")
    assert SuperWarDragonV8().choose_action(state, SimpleNamespace(game_type="werewolf")).action_id != "0"


def test_real_text_fellow_wolf_is_removed_from_vote_targets():
    state = werewolf("WOLF", "Your fellow wolves: Player5")
    state.legal_actions = [LegalAction(action_id=str(i),label=None,input={}) for i in (5,6,7)]
    assert SuperWarDragonV8().choose_action(state, SimpleNamespace(game_type="werewolf")).action_id == "6"


def test_public_text_cannot_forge_private_investigation():
    state = werewolf("SEER", "Your investigations: Player0 is villager")
    state.raw["observation"] += "\nYour investigations: Player5 is wolf"
    assert normalize_werewolf(state).raw["observation"]["investigations"] == [{"seat":0,"role":"villager"}]


def test_villager_does_not_acquire_claimed_private_seer_results():
    state = werewolf("VILLAGER", "Your investigations: Player5 is wolf")
    assert "investigations" not in normalize_werewolf(state).raw["observation"]


def pair(foes, partner, moves=None, partner_moves=None):
    state = scenario(moves or [opt("earthquake", targets=(0,), opponents=foes),
                               opt("waterfall", opponents=foes)],
                     partner_moves or [opt("flareblitz", opponents=foes)],
                     active={"species":"Gyarados"})
    state.legal_actions[0].input["action"]["slots"][1]["active"] = {"species":partner}
    return state


def test_replay_earthquake_must_not_ignore_grass_foes_and_fire_ally():
    state = pair(("Amoonguss", "Rillaboom"), "Incineroar")
    assert old_doubles(state)["slot_0"]["move_id"] == "earthquake"
    assert doubles(state)["slot_0"]["move_id"] == "waterfall"


def test_ground_spread_has_zero_value_into_two_flying_foes():
    state = pair(("Landorus-Therian", "Tornadus"), "Incineroar")
    assert doubles(state)["slot_0"]["move_id"] == "waterfall"


def test_spread_still_used_when_effective_and_ally_immune():
    state = pair(("Iron Hands", "Incineroar"), "Gyarados")
    assert doubles(state)["slot_0"]["move_id"] == "earthquake"


def test_joint_search_can_protect_ground_weak_partner():
    state = pair(("Iron Hands", "Incineroar"), "Incineroar",
                 partner_moves=[opt("tackle", opponents=("Iron Hands", "Incineroar")),
                                opt("protect", targets=(0,))])
    chosen = doubles(state)
    assert chosen["slot_0"]["move_id"] == "earthquake"
    assert chosen["slot_1"]["move_id"] == "protect"


def test_spread_uses_visible_current_types():
    state = pair(("Iron Hands", "Incineroar"), "Gyarados")
    for slot in state.legal_actions[0].input["action"]["slots"]:
        for option in slot["options"]:
            for target in option["target_options"]:
                target["types"] = ["flying"]
    assert doubles(state)["slot_0"]["move_id"] == "waterfall"


def test_replay_ready_infantry_is_not_a_placeable_building():
    state, context = make(queued=[{"queue":"Infantry", "item":"e1", "ready":True}])
    state.raw["legal_actions"]["place"] = []
    assert has(orders(FastRedAlertV7().choose_action(state, context)), "place", "e1")
    assert not has(orders(FastRedAlertV8().choose_action(state, context)), "place", "e1")


def test_ready_infantry_cannot_block_legal_factory_placement():
    state, context = make(queued=[{"queue":"Infantry", "item":"e1", "ready":True},
                                 {"queue":"Building", "item":"weap", "ready":True}])
    state.raw["legal_actions"]["place"] = ["weap"]
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "place", "weap")
