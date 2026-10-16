"""Behavior/budget checks; no combat outcome claims."""
from pathlib import Path
import sys,importlib.util
from copy import deepcopy
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_super_war_dragon_v6 import make,actor,orders,has
spec=importlib.util.spec_from_file_location('memory_candidate',ROOT/'examples/redalert_composition_memory_candidate.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def fixture(enemies=(),money=2000,tick=250,train=('e1','e3')):
    state,ctx=make(buildings=('fact','powr','powr','barr','proc','proc','weap','fix'),
        units=[actor('harv',100),actor('harv',101)],build=(),train=train,
        money=money,power=200,draw=140,enemies=list(enemies))
    state.raw['observation']['tick']=tick
    ctx.game_config={'rules':{'units':{'e1':{'cost':100},'e3':{'cost':300}}}}
    return state,ctx

def test_no_unseen_vehicle_inference():
    agent=mod.FastRedAlertV10();state,ctx=fixture()
    assert has(orders(agent.choose_action(state,ctx)),'train','e1')
    assert not agent.enemy_vehicle_seen

def test_observed_tank_memory_survives_fog():
    agent=mod.FastRedAlertV10();state,ctx=fixture([actor('3tnk',900,70,70)])
    assert has(orders(agent.choose_action(state,ctx)),'train','e3')
    later,ctx=fixture(tick=500)
    assert has(orders(agent.choose_action(later,ctx)),'train','e3')

def test_visible_v2_is_vehicle_evidence():
    agent=mod.FastRedAlertV10();state,ctx=fixture([actor('v2rl',900,70,70)])
    assert has(orders(agent.choose_action(state,ctx)),'train','e3')

def test_tick_reset_and_separate_match_do_not_share_evidence():
    agent=mod.FastRedAlertV10();state,ctx=fixture([actor('3tnk',900,70,70)])
    agent.choose_action(state,ctx)
    fresh,ctx=fixture(tick=1)
    assert has(orders(agent.choose_action(fresh,ctx)),'train','e1')
    other=mod.FastRedAlertV10()
    assert has(orders(other.choose_action(fresh,ctx)),'train','e1')

def test_rocket_budget_and_legal_hint_preserved():
    agent=mod.FastRedAlertV10();state,ctx=fixture([actor('3tnk',900,70,70)],money=450)
    assert not has(orders(agent.choose_action(state,ctx)),'train')
    later,ctx=fixture(tick=500,train=('e1',))
    assert has(orders(agent.choose_action(later,ctx)),'train','e1')

def test_wreck_does_not_add_vehicle_evidence():
    wreck=actor('3tnk',900,70,70);wreck['wreck']=True
    state,ctx=fixture([wreck]);agent=mod.FastRedAlertV10()
    agent.choose_action(state,ctx)
    assert not agent.enemy_vehicle_seen
