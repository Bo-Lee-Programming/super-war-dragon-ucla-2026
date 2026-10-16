"""Player-view regressions and an explicitly synthetic economy comparison.

These tests do not run OpenRA, model combat, or establish a match win rate.
"""
from types import SimpleNamespace

from examples.fast_redalert_agent_v8 import FastRedAlertV8
from examples.fast_redalert_agent_v10 import FastRedAlertV10, FALLBACK_COST
from test_super_war_dragon_v6 import actor, make, orders, has


HEALTHY = ("fact", "powr", "powr", "barr", "proc", "proc", "weap")
MINERS = [actor("harv", 100), actor("harv", 101)]


def test_authoritative_building_cost_controls_purchase():
    state, context = make(buildings=("fact",), build=("powr",), money=400,
                          train=(), units=())
    context.game_config = {"rules": {"buildings": {"powr": {"cost": 500}}}}
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "build", "powr")
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "build", "powr")


def test_empty_deploy_hint_is_authoritative():
    state, context = make(buildings=(), units=[actor("mcv", 42)], build=(), train=())
    state.raw["legal_actions"]["deploy"] = []
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "deploy")


def test_empty_repair_hint_does_not_send_ineligible_building():
    state, context = make(build=(), train=())
    state.raw["observation"]["buildings"][0]["hp"] = 30
    state.raw["legal_actions"]["repair"] = []
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "repair")


def test_service_depot_saving_prevents_permanent_infantry_spending():
    state, context = make(buildings=HEALTHY, units=MINERS, money=1200,
                          power=200, draw=110, build=("fix",), train=("e1", "apc"))
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "train", "e1")
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "train")
    state.raw["observation"]["economy"]["cash"] = 1500
    assert has(orders(FastRedAlertV10().choose_action(state, context)), "build", "fix")


def test_queued_costs_reserved_against_new_orders():
    state, context = make(buildings=HEALTHY, units=MINERS, money=700,
        build=(), train=("e1",), queued=[
            {"queue": "Building", "item": "fix", "progress": 0.1, "ready": False}])
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "train", "e1")
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "train")


def test_incoming_refinery_harvester_is_counted():
    state, context = make(buildings=("fact", "powr", "proc", "weap"),
        units=MINERS[:1], money=4000, build=(), train=("harv",), queued=[
            {"queue": "Building", "item": "proc", "progress": 0.9, "ready": False}])
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "train", "harv")
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "train", "harv")


def test_four_heavy_tanks_can_assault_without_twelve_infantry():
    tanks = [actor("3tnk", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=HEALTHY+("fix",), units=MINERS+tanks,
                          build=(), train=(), money=0)
    assert not has(orders(FastRedAlertV8().choose_action(state, context)), "attack_move")
    result = orders(FastRedAlertV10().choose_action(state, context))
    attack = next(o for o in result if o["cmd"] == "attack_move")
    assert attack["units"] == [200, 201, 202, 203]
    assert attack["to"] == [80, 80]


def test_one_scout_does_not_pull_entire_army_back():
    army = [actor("e1", 200+i, 12+i, 10, idle=True, act="Idle") for i in range(16)]
    state, context = make(buildings=HEALTHY, units=MINERS+army, build=(), train=(),
        enemies=[actor("e1", 900, 15, 10)], money=0)
    result = orders(FastRedAlertV10().choose_action(state, context))
    defense = next(o for o in result if o["cmd"] == "attack_move")
    assert 3 <= len(defense["units"]) <= 5


def test_heavy_visible_threat_gets_all_needed_defenders():
    army = [actor("3tnk", 200+i, 12+i, 10, idle=True, act="Idle") for i in range(5)]
    state, context = make(buildings=HEALTHY, units=MINERS+army, build=(), train=(),
        enemies=[actor("3tnk", 900+i, 15, 10) for i in range(3)], money=0)
    defense = next(o for o in orders(FastRedAlertV10().choose_action(state, context))
                   if o["cmd"] == "attack_move")
    assert len(defense["units"]) == 5


def test_damaged_tank_retreat_is_not_overridden_by_defense():
    units = MINERS+[actor("3tnk", 200, 20, 10, hp=20),
                    actor("3tnk", 201, 12, 10)]
    state, context = make(buildings=HEALTHY, units=units, build=(), train=(),
        enemies=[actor("3tnk", 900, 21, 10)], money=0)
    result = orders(FastRedAlertV10().choose_action(state, context))
    assert {"cmd":"move", "units":[200], "to":[10,10]} in result
    assert all(200 not in o.get("units", []) for o in result if o["cmd"] != "move")


def test_last_minute_positive_trade_score_preserved():
    tanks = [actor("3tnk", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=HEALTHY, units=MINERS+tanks,
                          build=(), train=(), money=0)
    state.raw["time"] = {"remaining_seconds": 65}
    state.raw["observation"]["military"] = {"kills_cost": 2500, "deaths_cost": 800}
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "attack_move")


def test_outnumbered_force_does_not_charge_visible_tanks():
    army = [actor("e1", 200+i, idle=True, act="Idle") for i in range(20)]
    state, context = make(buildings=HEALTHY, units=MINERS+army, build=(), train=(),
        enemies=[actor("3tnk", 900+i, 70, 70) for i in range(5)], money=0)
    assert has(orders(FastRedAlertV8().choose_action(state, context)), "attack_move")
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "attack_move")


def test_no_friendly_duplicate_orders_or_miner_combat():
    units = MINERS+[actor("3tnk", 200+i, 15, 10, idle=True, act="Idle",
                         hp=20 if i < 2 else 100) for i in range(20)]
    state, context = make(buildings=HEALTHY, units=units, money=3000,
                          enemies=[actor("3tnk", 900, 18, 10)])
    result = orders(FastRedAlertV10().choose_action(state, context))
    ids = [uid for order in result for uid in order.get("units", [])]
    assert len(ids) == len(set(ids))
    assert all(not ({100,101} & set(o.get("units", []))) for o in result
               if o["cmd"] in ("attack_move", "attack", "move"))


def test_lost_build_can_be_retried_from_fresh_view():
    agent = FastRedAlertV10()
    state, context = make(buildings=("fact",), units=(), build=("powr",), train=())
    assert has(orders(agent.choose_action(state, context)), "build", "powr")
    agent.on_action_result({"results":[{"index":0,"cmd":"build","status":"lost"}]}, context)
    state.raw["observation"]["tick"] += 1
    assert has(orders(agent.choose_action(state, context)), "build", "powr")


def test_delayed_lost_verdict_is_consumed_from_next_state():
    agent = FastRedAlertV10()
    state, context = make(buildings=("fact",), units=(), build=("powr",), train=())
    assert has(orders(agent.choose_action(state, context)), "build", "powr")
    state.raw["last_orders"] = {"pending":False, "state_version":250, "batch":1,
        "results":[{"index":0,"cmd":"build","status":"lost"}]}
    state.raw["observation"]["tick"] += 1
    assert has(orders(agent.choose_action(state, context)), "build", "powr")


def economy_trace(agent_type, income_per_second=40):
    """A cash-only stress scenario, with no combat and no engine simulation.

    Start with two refineries, two miners and factory; periodic income competes
    with infantry spending. Instant completion makes this harsher on savings.
    Only the time of the first depot purchase is measured.
    """
    bank = 1100
    agent = agent_type()
    for second in range(5, 305, 5):
        bank += 5*income_per_second
        state, context = make(tick=second*25, buildings=HEALTHY, units=MINERS,
            money=bank, power=200, draw=110, build=("fix",), train=("e1", "apc"))
        decision = orders(agent.choose_action(state, context))
        for order in decision:
            if order["cmd"] == "build" and order["item"] == "fix":
                return second
            if order["cmd"] == "train":
                bank -= FALLBACK_COST[order["item"]]*order.get("count",1)
    return None


def test_cash_stress_trace_unlocks_tanks_instead_of_spending_forever():
    assert economy_trace(FastRedAlertV8) is None
    assert economy_trace(FastRedAlertV10) == 10


def test_only_damaged_defenders_never_emit_an_empty_attack_order():
    state, context = make(buildings=HEALTHY, units=MINERS+[actor("3tnk", 200, 15, 10, hp=20)],
                          enemies=[actor("3tnk", 900, 16, 10)], build=(), train=(), money=0)
    result = orders(FastRedAlertV10().choose_action(state, context))
    assert all(o["units"] for o in result if "units" in o)


def test_randomized_player_views_use_only_current_legal_owned_actions():
    import random
    from examples.llm.redalert import order_ok, ORDER_FIELDS, DEFAULT_LIMITS
    rng = random.Random(100626)
    for sample in range(500):
        units = [actor(rng.choice(["harv", "e1", "e3", "3tnk"]), 100+i,
                       rng.randrange(5,90), rng.randrange(5,90),
                       idle=rng.choice([True,False]), hp=rng.randrange(1,101),
                       act=rng.choice(["Idle", "AttackMove", "FindAndDeliverResources"]))
                 for i in range(rng.randrange(60))]
        state, context = make(tick=sample*50, buildings=HEALTHY,
            units=units, money=rng.randrange(6000), power=200, draw=rng.randrange(200),
            enemies=[actor("e1", 900, rng.randrange(90), rng.randrange(90))],
            queued=[{"queue":"Building", "item":"fix", "progress":rng.random(),
                     "ready":False}] if sample%3 == 0 else [])
        result = orders(FastRedAlertV10().choose_action(state, context))
        legal = state.raw["legal_actions"]
        assert len(result) <= 20
        assert sum(len(o["units"]) if "units" in o else o.get("count",1)
                   for o in result) <= 200
        owned = {u["id"] for u in units}
        used = []
        for o in result:
            assert order_ok(o, ORDER_FIELDS, DEFAULT_LIMITS), o
            assert set(o.get("units",[])) <= owned
            used.extend(o.get("units",[]))
            if o["cmd"] in ("train", "build", "place"):
                assert o["item"] in legal[o["cmd"]]
        assert len(used) == len(set(used))


def test_v7_core_economy_and_yard_loss_regressions_remain_fixed():
    state, context = make(money=1100, units=[], build=())
    assert has(orders(FastRedAlertV10().choose_action(state, context)), "train", "harv")
    state, context = make(buildings=("powr","barr","proc","weap"),
        units=[actor("e1", 91, idle=True)], enemies=[actor("e1", 900, 15,10)])
    assert has(orders(FastRedAlertV10().choose_action(state, context)), "attack_move")


def test_refinery_loss_does_not_disable_surviving_tank_counterattack():
    tanks = [actor("3tnk", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=("fact","powr","weap","fix"),
                          units=tanks, money=0, build=(), train=())
    attack = next(o for o in orders(FastRedAlertV10().choose_action(state, context))
                  if o["cmd"] == "attack_move")
    assert set(attack["units"]) == {200,201,202,203}
    assert attack["to"] == [80,80]


def test_refinery_loss_does_not_send_small_force_to_enemy_base():
    infantry = [actor("e1", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=("fact","powr","weap"), units=infantry,
                          money=0, build=(), train=())
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "attack_move")


def test_refinery_loss_does_not_override_visible_disadvantage():
    tanks = [actor("3tnk", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=("fact","powr","weap","fix"), units=tanks,
        money=0, build=(), train=(),
        enemies=[actor("3tnk", 900+i, 70,70) for i in range(5)])
    assert not has(orders(FastRedAlertV10().choose_action(state, context)), "attack_move")


def test_refinery_loss_still_prioritizes_local_defense():
    tanks = [actor("3tnk", 200+i, idle=True, act="Idle") for i in range(4)]
    state, context = make(buildings=("fact","powr","weap","fix"), units=tanks,
        money=0, build=(), train=(), enemies=[actor("3tnk", 900, 15,10)])
    attacks = [o for o in orders(FastRedAlertV10().choose_action(state, context))
               if o["cmd"] == "attack_move"]
    assert attacks and all(o["to"] == [15,10] for o in attacks)
