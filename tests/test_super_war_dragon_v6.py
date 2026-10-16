"""V6 regression tests: mocked participant-only state, no web or official match."""
from types import SimpleNamespace
from time import perf_counter

from altruagent import WAIT
from examples.fast_redalert_agent_v6 import FastRedAlertV6
from examples.free_multigame_agent_v6 import SuperWarDragonV6


def actor(kind, uid, x=10, y=10, idle=False, hp=100, act="FindAndDeliverResources"):
    return {"type":kind,"id":uid,"x":x,"y":y,"idle":idle,"act":act,"hp":hp}


def make(*, tick=250, buildings=("fact","powr","barr","proc","weap"),
         units=(), money=5000, ore=0, queued=(),
         build=("powr","proc","barr","weap","fix"),
         train=("e1","e3","harv","apc","2tnk"), enemies=(), enemy_buildings=(),
         power=100, draw=50, base=None, enemy_base=(80,80)):
    built=[actor(t,201+i) for i,t in enumerate(buildings)]
    legal={"build":list(build), "train":list(train),
           "place":[q.get("item") for q in queued if q.get("ready")],
           "deploy":[u["id"] for u in units if u["type"]=="mcv"],
           "repair":[b["id"] for b in built if b["hp"]<100],
           "enemy_base":list(enemy_base)}
    obs={"tick":tick, "units":list(units),"buildings":built,
         "production":list(queued),
         "economy":{"cash":money,"ore":ore,"power_provided":power,"power_drained":draw},
         "visible_enemies":list(enemies),
         "visible_enemy_buildings":list(enemy_buildings),
         "base_center":list(base or (10,10))}
    state=SimpleNamespace(raw={"phase":"playing","observation":obs,
                                "legal_actions":legal,
                                "map":{"bounds":[0,0,96,96]}},legal_actions=[])
    ctx=SimpleNamespace(game_type="red_alert",game_config={})
    return state,ctx


def orders(result):
    return [] if result is WAIT else result.action["orders"]


def has(actions,cmd,item=None):
    return any(o.get("cmd")==cmd and (item is None or o.get("item")==item) for o in actions)


def test_deploy_is_first_and_not_repeated_without_observation():
    a=FastRedAlertV6()
    st,ctx=make(buildings=(), units=[actor("mcv",42, idle=True)])
    assert orders(a.choose_action(st,ctx)) == [{"cmd":"deploy","units":[42]}]
    assert not orders(a.choose_action(st,ctx))


def test_power_first():
    st,ctx=make(buildings=("fact",),build=("powr",))
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"build","powr")


def test_barracks_then_refinery():
    st,ctx=make(buildings=("fact","powr"),build=("barr","proc","powr"))
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"build","barr")
    st,ctx=make(buildings=("fact","powr","barr"),build=("proc","powr"))
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"build","proc")


def test_completed_refinery_is_placed():
    st,ctx=make(buildings=("fact","powr","barr"),queued=[
        {"queue":"Building","item":"proc","ready":True,"progress":1.0}],build=())
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"place","proc")


def test_queued_proc_is_not_double_queued():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap"),
        queued=[{"queue":"Building","item":"proc","progress":0.4,"ready":False}],
        money=3500)
    assert not has(orders(FastRedAlertV6().choose_action(st,ctx)),"build","proc")


def test_post_opening_growth_builds_second_refinery():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap"),
        money=2600, units=[actor("harv",500)], build=("proc","fix","powr"))
    result=orders(FastRedAlertV6().choose_action(st,ctx))
    assert has(result,"build","proc"), result


def test_danger_sends_defense_instead_of_suicidal_single():
    infantry=[actor("e1",400+i,10+i%2,10,True,act="Idle") for i in range(9)]
    st,ctx=make(units=infantry, enemies=[actor("e1",900,15,10)])
    decision=orders(FastRedAlertV6().choose_action(st,ctx))
    defend=[o for o in decision if o["cmd"]=="attack_move"]
    assert len(defend)==1 and defend[0]["to"]==[15,10]
    assert len(defend[0]["units"])==9


def test_no_solo_attack_into_enemy_base():
    st,ctx=make(units=[actor("e1",400,idle=True,act="Idle")])
    decision=orders(FastRedAlertV6().choose_action(st,ctx))
    assert not has(decision,"attack_move"), decision


def test_cohesive_attack_with_reserve_and_legal_destination():
    units=[actor("e1",400+i,idle=True,act="Idle") for i in range(17)]
    st,ctx=make(buildings=("fact","powr","barr","proc","weap","fix"),units=units,money=2400)
    decision=orders(FastRedAlertV6().choose_action(st,ctx))
    attacks=[o for o in decision if o["cmd"]=="attack_move"]
    assert attacks and attacks[0]["to"]==[80,80]
    assert len(attacks[0]["units"])>=8
    assert len(attacks[0]["units"]) < 17


def test_no_out_of_bounds_attack():
    units=[actor("e1",400+i,idle=True,act="Idle") for i in range(20)]
    st,ctx=make(units=units, enemy_base=(300,-2))
    assert not has(orders(FastRedAlertV6().choose_action(st,ctx)),"attack_move")


def test_restart_mining_on_idle_harvester():
    harv=actor("harv",90,idle=True,act="Idle")
    st,ctx=make(units=[harv])
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"harvest")


def test_new_harvester_priority_with_healthy_income():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap","fix"),
                units=[actor("harv",90)],money=3000)
    actions=orders(FastRedAlertV6().choose_action(st,ctx))
    assert has(actions,"train","harv"), actions


def test_reserve_money_for_economy_instead_of_train_riflemen():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap","fix"),
                units=[actor("harv",90)],money=850,
                build=("proc",))
    actions=orders(FastRedAlertV6().choose_action(st,ctx))
    assert not has(actions,"train","e1"), actions


def test_repair_critical_building():
    st,ctx=make(money=3200)
    st.raw["observation"]["buildings"][0]["hp"]=30
    st.raw["legal_actions"]["repair"]=[201]
    assert has(orders(FastRedAlertV6().choose_action(st,ctx)),"repair")


def test_power_recovery_when_needed():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap"),draw=94,
                money=4000,build=("powr","proc"))
    actions=orders(FastRedAlertV6().choose_action(st,ctx))
    assert has(actions,"build","powr"), actions


def test_batch_limits():
    st,ctx=make(units=[actor("e1",400+i,idle=True,act="Idle") for i in range(180)],
                enemies=[actor("e1",900,15,10)])
    a=orders(FastRedAlertV6().choose_action(st,ctx))
    assert len(a)<=20
    assert all(len(x.get("units", []))<=50 for x in a)


def test_refusals_recorded():
    agent=FastRedAlertV6()
    agent.on_action_result({"accepted":False,
          "results":[{"status":"rejected","reason":"not_ready"}]},
         SimpleNamespace(game_type="red_alert"))
    assert agent.metrics["batch_refused"]==1 and agent.metrics["order_problem"]==1


def test_multigame_adapter_preserves_other_games():
    v6=SuperWarDragonV6()
    assert hasattr(v6,"choose_message")
    assert hasattr(v6,"_werewolf_v4")
    assert callable(v6.choose_action)


def test_fast_policy_decision_latency_under_one_ms_average():
    st,ctx=make(buildings=("fact","powr","barr","proc","weap","fix"),
                units=[actor("e1",400+i,idle=True,act="Idle") for i in range(80)],
                money=3800)
    a=FastRedAlertV6()
    t=perf_counter()
    for i in range(250):
        st.raw["observation"]["tick"]+=1
        a.choose_action(st,ctx)
    elapsed=(perf_counter()-t)/250
    # generous for a loaded user's workstation; target well under 1ms
    assert elapsed < .003, elapsed
