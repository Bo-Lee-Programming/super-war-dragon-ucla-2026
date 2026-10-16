"""Production budget regressions; no combat or match-win simulation."""
from examples.fast_redalert_agent_v10 import FastRedAlertV10, FALLBACK_COST
from test_super_war_dragon_v6 import actor, make, orders, has

BASE = ('fact','powr','powr','barr','proc','proc','weap','fix')
MINERS = [actor('harv',100),actor('harv',101)]

def ready(money, **overrides):
    kwargs=dict(buildings=BASE,units=MINERS,money=money,build=(),train=('e1','e3','harv','3tnk','ftrk'),power=200,draw=140)
    kwargs.update(overrides)
    return make(**kwargs)

def choose(state,ctx): return orders(FastRedAlertV10().choose_action(state,ctx))

def test_tank_price_plus_operating_floor_survives_infantry_scheduler():
    s,c=ready(1350)
    assert choose(s,c)==[{'cmd':'train','item':'3tnk','count':1}]

def test_tank_savings_not_spent_on_cheaper_vehicle():
    s,c=ready(1200,train=('3tnk','ftrk'))
    assert choose(s,c)==[]
    s,c=ready(1200)
    assert choose(s,c)==[]

def test_infantry_surplus_and_tank_do_not_double_count_reserve():
    s,c=ready(1650)
    assert choose(s,c)==[{'cmd':'train','item':'e1','count':3},{'cmd':'train','item':'3tnk','count':1}]

def test_authoritative_tank_cost_controls_savings():
    s,c=ready(1550)
    c.game_config={'rules':{'units':{'3tnk':{'cost':1300}}}}
    assert choose(s,c)==[{'cmd':'train','item':'3tnk','count':1}]

def test_legal_allied_light_tank_also_protects_production_budget():
    s,c=ready(950,train=('e1','1tnk','jeep'))
    assert choose(s,c)==[{'cmd':'train','item':'1tnk','count':1}]

def test_occupied_vehicle_queue_does_not_save_for_second_tank():
    for kind in ('3tnk','ftrk','harv'):
        s,c=ready(900,queued=[{'queue':'Vehicle','item':kind,'progress':.5,'ready':False}])
        assert has(choose(s,c),'train','e1')

def test_missing_and_second_harvester_precede_tank():
    for miners in ([],MINERS[:1]):
        s,c=ready(1500,units=miners)
        out=choose(s,c)
        assert has(out,'train','harv') and not has(out,'train','3tnk')

def test_refinery_and_power_keep_infrastructure_priority():
    s,c=ready(2700,buildings=('fact','powr','powr','barr','proc','weap','fix'),build=('proc',))
    assert has(choose(s,c),'build','proc')
    s.raw['observation']['economy']['power_provided']=140
    s.raw['legal_actions']['build']=['powr','proc']
    assert choose(s,c)[0]=={'cmd':'build','item':'powr'}

def test_emergency_still_produces_anti_tank_infantry():
    s,c=ready(1350,units=MINERS+[actor('e1',999)],enemies=[actor('2tnk',500,15,10)])
    out=choose(s,c)
    assert has(out,'attack_move') and has(out,'train','e3')

def test_budget_and_legal_train_options_over_cash_and_queue_grid():
    for cash in range(0,3001,50):
        for queue in ([],[dict(queue='Infantry',item='e3',progress=.4,ready=False)],[dict(queue='Vehicle',item='3tnk',progress=.5,ready=False)]):
            s,c=ready(cash,queued=queue)
            acts=choose(s,c)
            committed=sum(int(FALLBACK_COST[q['item']]*(1-q['progress'])) for q in queue)
            spend=sum(FALLBACK_COST[a['item']]*a.get('count',1) for a in acts if a['cmd'] in {'train','build'})
            assert spend<=max(0,cash-committed)
            assert all(a['item'] in s.raw['legal_actions']['train'] for a in acts if a['cmd']=='train')
