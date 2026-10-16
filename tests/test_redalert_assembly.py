"""Assembly-only player-view regressions, without simulated combat outcomes."""
from copy import deepcopy
from examples.fast_redalert_agent_v10 import FastRedAlertV10
from test_super_war_dragon_v6 import actor, make, orders

BASE = ('fact','powr','powr','barr','proc','proc','weap','fix')

def force(tanks=1, rifles=5, tank_hp=100):
    return ([actor('3tnk',400+i,idle=True,act='Idle',hp=tank_hp) for i in range(tanks)] +
            [actor('e1',500+i,idle=True,act='Idle') for i in range(rifles)])

def situation(combat=None, miners=None, **overrides):
    if combat is None: combat=force()
    if miners is None: miners=[actor('harv',100),actor('harv',101)]
    args=dict(buildings=BASE, units=miners+combat, money=0, build=(), train=('3tnk',),power=200,draw=140)
    args.update(overrides)
    state,ctx=make(**args)
    state.raw['observation']['military']={'kills_cost':1000,'deaths_cost':2000}
    state.raw['time']={'remaining_seconds':600}
    ctx.game_config={'rules':{'units':{'3tnk':{'cost':1150},'e1':{'cost':100},'harv':{'cost':1100}}}}
    return state,ctx

def choose(state,ctx,cls=FastRedAlertV10):
    return orders(cls().choose_action(deepcopy(state),ctx))

def assault(state,ctx,cls=FastRedAlertV10):
    return [o for o in choose(state,ctx,cls) if o['cmd']=='attack_move' and o['to']==[80,80]]

def test_losing_blind_single_tank_wave_waits():
    s,c=situation()
    assert not assault(s,c)

def test_two_healthy_departing_tanks_can_attack():
    s,c=situation(force(2,2))
    assert len(assault(s,c)[0]['units'])==4

def test_equivalent_actual_departing_material_can_attack():
    s,c=situation(force(0,25))
    assert len(assault(s,c)[0]['units'])==23

def test_reserved_defenders_not_counted_in_material_threshold():
    s,c=situation(force(1,12))
    assert not assault(s,c)  # 2350 available, but only 2150 departs.

def test_active_tank_elsewhere_does_not_complete_idle_tank_pair():
    combat=force(1,5)+[actor('3tnk',900,60,60,idle=False,act='AttackMove')]
    s,c=situation(combat)
    assert not assault(s,c)

def test_two_damaged_tanks_do_not_count_as_healthy_pair():
    s,c=situation(force(2,2,tank_hp=40))
    assert not assault(s,c)

def test_authoritative_cost_changes_material_equivalence():
    s,c=situation(force(0,25))
    assert assault(s,c)
    c.game_config['rules']['units']['3tnk']['cost']=1500
    assert not assault(s,c)

def test_even_or_profitable_trades_keep_original_wave():
    for kills in (2000,3000):
        s,c=situation();s.raw['observation']['military']['kills_cost']=kills
        assert assault(s,c)

def test_visible_objective_keeps_original_attack_logic():
    s,c=situation(enemy_buildings=[actor('proc',999,80,80)])
    assert assault(s,c)

def test_missing_or_idle_miners_dont_wait_for_unavailable_reinforcements():
    for miners in ([],[actor('harv',100,idle=True,act='Idle')],
                   [actor('harv',100,idle=False,act=None)],
                   [actor('harv',100,idle=False,act='Move')],
                   [actor('harv',100,idle=False,act='UnknownActivity')]):
        s,c=situation(miners=miners)
        assert assault(s,c)

def test_lost_factory_refinery_or_no_legal_tank_does_not_hold_force():
    for overrides in ({'buildings':tuple(b for b in BASE if b!='weap')},
                      {'buildings':tuple(b for b in BASE if b!='proc')},
                      {'train':()}):
        s,c=situation(**overrides)
        assert assault(s,c)

def test_existing_late_desperation_exception_is_preserved():
    s,c=situation();s.raw['time']['remaining_seconds']=60
    assert assault(s,c)

def test_base_defense_and_emergency_production_identical():
    s,c=situation(money=2000,train=('e1','e3','3tnk','harv'),enemies=[actor('2tnk',999,15,10)])
    acts=choose(s,c)
    assert any(o['cmd']=='attack_move' and o['to']==[15,10] for o in acts)
    assert any(o['cmd']=='train' and o['item']=='e3' for o in acts)

def test_production_mining_and_inputs_unchanged():
    s,c=situation(money=1800,train=('e1','3tnk','harv'))
    before=deepcopy(s.raw)
    new=choose(s,c)
    assert new==[{'cmd':'train','item':'e1','count':3},{'cmd':'train','item':'3tnk','count':1}]
    assert s.raw==before

def test_small_visible_resistance_still_requires_material_advantage():
    s,c=situation(force(2,2),enemy_buildings=[actor('proc',999,80,80)],
                  enemies=[actor('3tnk',910+i,70,70) for i in range(5)])
    assert not assault(s,c)

def test_retreat_commands_unchanged_by_assembly_gate():
    combat=force()+[actor('3tnk',700,50,50,idle=False,act='AttackMove',hp=20)]
    s,c=situation(combat,enemies=[actor('3tnk',900,51,50)])
    new=choose(s,c)
    assert [o for o in new if o['cmd']=='move']==[{'cmd':'move','units':[700],'to':[10,10]}]
