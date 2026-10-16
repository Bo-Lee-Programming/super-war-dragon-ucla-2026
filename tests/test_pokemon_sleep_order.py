"""Action regressions for sleep timing, using only legal player-view fixtures."""
from types import SimpleNamespace

from altruagent import LegalAction
from examples.pokemon_policy_v10 import doubles, _sleep_before_foe


def option(name, targets=(1,)):
    return {"type":"move", "move_id":name, "targets":list(targets)}


def state(first, second, foes, moves0, moves1, fields=None):
    slots = [{"slot":0, "active":first, "options":moves0},
             {"slot":1, "active":second, "options":moves1}]
    return SimpleNamespace(raw={"observation":{"turn":2, "fields":fields or {},
                            "opponent_active_pokemon":foes}},
                           legal_actions=[LegalAction(action_id="doubles_turn", label="",
                                                       input={"action":{"slots":slots}})])


def test_slow_spore_cannot_replace_protect_against_faster_thunderbolt():
    s = state({"species":"Pelipper", "current_hp_fraction":.1}, {"species":"Amoonguss"},
              [{"species":"Iron Valiant", "moves":["thunderbolt"], "current_hp_fraction":.2}],
              [option("scald"), option("protect", (0,))],
              [option("spore"), option("pollenpuff", (-1,1)), option("sludgebomb")])
    chosen = doubles(s)
    assert chosen["slot_0"]["move_id"] == "protect"
    assert chosen["slot_1"]["move_id"] == "sludgebomb"


def test_active_trick_room_restores_slow_sleep_first_action_value():
    s = state(None, {"species":"Amoonguss"}, [{"species":"Iron Hands", "moves":["drainpunch"]}],
              [{"type":"pass"}], [option("spore"), option("sludgebomb")])
    assert doubles(s)["slot_1"]["move_id"] == "sludgebomb"
    s.raw["observation"]["fields"] = {"TRICK_ROOM":0}
    assert doubles(s)["slot_1"]["move_id"] == "spore"


def test_slow_sleep_retains_future_value_against_steel_immunity():
    s = state(None, {"species":"Amoonguss"}, [{"species":"Archaludon", "moves":["bodypress"]}],
              [{"type":"pass"}], [option("spore"), option("sludgebomb")])
    assert doubles(s)["slot_1"]["move_id"] == "spore"


def test_sleep_speed_tie_is_not_guaranteed_action_prevention():
    mon = {"species":"Amoonguss"}
    for obs in ({}, {"fields":{"TRICK_ROOM":0}}):
        assert not _sleep_before_foe({"priority":0}, mon, mon, obs)


def test_priority_is_not_reversed_by_trick_room():
    slow, fast = {"species":"Amoonguss"}, {"species":"Iron Valiant"}
    assert _sleep_before_foe({"priority":1}, slow, fast, {"fields":{"TRICK_ROOM":0}})
    assert not _sleep_before_foe({"priority":-1}, fast, slow, {})


def test_fast_sleep_and_tailwind_apply_before_normal_threat():
    slow, fast = {"species":"Amoonguss"}, {"species":"Iron Hands"}
    assert not _sleep_before_foe({"priority":0}, slow, fast, {})
    assert _sleep_before_foe({"priority":0}, slow, fast, {"side_conditions":{"TAILWIND":0}})
