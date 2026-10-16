"""Pure local boundary checks using official DecisionContext; no network."""
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import importlib.util,json,sys
import pytest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from altruagent.models import DecisionContext
from examples.free_multigame_agent_v10 import SuperWarDragonV10
from test_super_war_dragon_v6 import make,actor,orders,has

SESSION='11111111-1111-4111-8111-111111111111'
OTHER='22222222-2222-4222-8222-222222222222'

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

@pytest.fixture
def wrapper(monkeypatch):
    candidate=load_module(ROOT/'examples/redalert_composition_memory_candidate.py','examples.redalert_composition_memory_candidate')
    monkeypatch.setitem(sys.modules,'examples.redalert_composition_memory_candidate',candidate)
    monkeypatch.setenv('RA_COMPOSITION_TEST_SEATS',json.dumps({SESSION:0,OTHER:1}))
    module=load_module(ROOT/'examples/testing_composition_wrapper.py','testing_wrapper_fixture')
    module.candidate_type=candidate.FastRedAlertV10
    return module

def ctx(session=SESSION,seat=0,tournament=None,game='red_alert'):
    return DecisionContext(session_id=session,tournament_id=tournament,game_type=game,agent_id='test',seat_position=seat)

@pytest.mark.parametrize('tournament',['formal-tournament','',0,False])
def test_every_non_none_tournament_is_exact_baseline(wrapper,tournament):
    delegate=wrapper.TestingCompositionRouter()._delegate(ctx(tournament=tournament))
    assert type(delegate) is SuperWarDragonV10
    assert not isinstance(delegate._redalert_v6,wrapper.candidate_type)

def test_missing_tournament_field_is_baseline(wrapper):
    context=SimpleNamespace(session_id=SESSION,seat_position=0,game_type='red_alert')
    assert not isinstance(wrapper.TestingCompositionRouter()._delegate(context)._redalert_v6,wrapper.candidate_type)

@pytest.mark.parametrize('context',[ctx(session='33333333-3333-4333-8333-333333333333'),ctx(seat=1),ctx(seat=None),ctx(seat=False),ctx(game='pokemon_vgc_doubles_draft'),ctx(game='werewolf')])
def test_unknown_session_other_seat_and_other_games_are_baseline(wrapper,context):
    assert not isinstance(wrapper.TestingCompositionRouter()._delegate(context)._redalert_v6,wrapper.candidate_type)

def test_seats_sessions_and_formal_delegate_are_independent(wrapper):
    router=wrapper.TestingCompositionRouter()
    a=router._delegate(ctx());b=router._delegate(ctx(seat=1));c=router._delegate(ctx(session=OTHER,seat=1));d=router._delegate(ctx(tournament='formal'))
    assert len({id(x) for x in [a,b,c,d]})==4
    assert len({id(x._redalert_v6) for x in [a,b,c,d]})==4
    assert isinstance(a._redalert_v6,wrapper.candidate_type)
    assert isinstance(c._redalert_v6,wrapper.candidate_type)
    assert router._delegate(ctx()) is a
    a._redalert_v6.enemy_vehicle_seen=True
    assert not c._redalert_v6.enemy_vehicle_seen

def test_allowlist_is_frozen_at_module_startup(wrapper,monkeypatch):
    monkeypatch.setenv(wrapper.ENV_NAME,'{}')
    assert isinstance(wrapper.TestingCompositionRouter()._delegate(ctx())._redalert_v6,wrapper.candidate_type)
    with pytest.raises(TypeError):wrapper._PROCESS_ALLOWLIST[SESSION]=1

@pytest.mark.parametrize('text',['','null','[]','{','{"*":0}',json.dumps({SESSION:True}),json.dumps({SESSION:2}),json.dumps({SESSION:'0'}),'"secret-not-json"','{"'+SESSION+'":0,"'+SESSION+'":1}'])
def test_bad_config_fails_closed(wrapper,text):
    assert dict(wrapper.parse_allowlist(text))=={}

def test_candidate_production_changes_only_allowlisted_testing_seat(wrapper):
    state,oldctx=make(buildings=('fact','powr','powr','barr','proc','proc','weap','fix'),
        units=[actor('harv',100),actor('harv',101)],build=(),train=('e1','e3'),money=2000,power=200,draw=140,
        enemies=[actor('v2rl',900,70,70)])
    router=wrapper.TestingCompositionRouter();candidate=ctx();baseline=ctx(seat=1);formal=ctx(tournament='formal')
    cfg={'rules':{'units':{'e1':{'cost':100},'e3':{'cost':300}}}}
    candidate,baseline,formal=(replace(c,game_config=cfg) for c in (candidate,baseline,formal))
    assert has(orders(router.choose_action(state,candidate)),'train','e3')
    assert has(orders(router.choose_action(state,baseline)),'train','e1')
    assert has(orders(router.choose_action(state,formal)),'train','e1')

def test_results_go_to_same_seat_delegate(wrapper):
    router=wrapper.TestingCompositionRouter();a=router._delegate(ctx());b=router._delegate(ctx(seat=1));called=[]
    a.on_action_result=lambda result,context:called.append(('candidate',result))
    b.on_action_result=lambda result,context:called.append(('baseline',result))
    router.on_action_result({'accepted':True},ctx());router.on_action_result({'accepted':False},ctx(seat=1))
    assert called==[('candidate',{'accepted':True}),('baseline',{'accepted':False})]

@pytest.mark.parametrize('field,value',[
    ('tournament_id',{}),('tournament_id',[]),('tournament_id','None'),
    ('session_id',{}),('seat_position',[]),('game_type',{}),
])
def test_malformed_unhashable_context_still_routes_baseline(wrapper,field,value):
    c=replace(ctx(),**{field:value})
    delegate=wrapper.TestingCompositionRouter()._delegate(c)
    assert not isinstance(delegate._redalert_v6,wrapper.candidate_type)

def test_formal_and_unknown_routes_do_not_load_optional_research(wrapper,monkeypatch):
    def fail_if_called():raise AssertionError('Research loader touched baseline route')
    monkeypatch.setattr(wrapper,'_load_candidate_class',fail_if_called)
    audited=wrapper.create_agent()
    assert audited.policy.__class__ is wrapper.TestingCompositionRouter
    for c in (ctx(tournament='formal'),ctx(seat=1),ctx(game='werewolf')):
        assert not isinstance(audited.policy._delegate(c)._redalert_v6,wrapper.candidate_type)

def test_missing_optional_module_falls_back_once(wrapper,monkeypatch,capsys):
    monkeypatch.setattr(wrapper.util,'find_spec',lambda name:None)
    router=wrapper.TestingCompositionRouter()
    first=router._delegate(ctx())
    assert not isinstance(first._redalert_v6,wrapper.candidate_type)
    assert router._delegate(ctx()) is first
    assert capsys.readouterr().out.count('candidate unavailable; baseline selected')==1

def test_wrong_candidate_hash_is_not_imported(wrapper,monkeypatch,tmp_path):
    bad=tmp_path/'wrong.py';bad.write_text('raise RuntimeError("must never execute")')
    monkeypatch.setattr(wrapper.util,'find_spec',lambda name:SimpleNamespace(origin=str(bad)))
    def fail_if_called(name):raise AssertionError('Wrong source was imported')
    monkeypatch.setattr(wrapper,'import_module',fail_if_called)
    assert wrapper._load_candidate_class() is None
    assert not isinstance(wrapper.TestingCompositionRouter()._delegate(ctx())._redalert_v6,wrapper.candidate_type)

@pytest.mark.parametrize('failure',['import','construct'])
def test_optional_candidate_failure_cannot_break_factory(wrapper,monkeypatch,failure):
    if failure=='import':
        def broken(name):raise ImportError('synthetic optional import failure')
        monkeypatch.setattr(wrapper,'import_module',broken)
    else:
        def broken():raise RuntimeError('synthetic optional constructor failure')
        monkeypatch.setattr(wrapper,'_load_candidate_class',lambda:broken)
    agent=wrapper.create_agent()
    assert not isinstance(agent.policy._delegate(ctx())._redalert_v6,wrapper.candidate_type)

def test_official_parser_missing_tournament_is_not_proof_of_testing(wrapper):
    from altruagent.models import OfficialAssignment
    from altruagent.supervisor import assignment_kind
    assignment=OfficialAssignment.from_dict({'match_id':'synthetic','seat_id':'own'})
    assert assignment.tournament_id is None
    assert assignment_kind(assignment)=='tournament'
    # DecisionContext omits assignment.context. A validated Testing allowlist is
    # therefore a necessary operational prerequisite, not replaceable by None.
    assert isinstance(wrapper.TestingCompositionRouter()._delegate(ctx(tournament=assignment.tournament_id))._redalert_v6,wrapper.candidate_type)

def test_only_line_endings_may_change_pinned_candidate_bytes(wrapper):
    source=(ROOT/'examples/redalert_composition_memory_candidate.py').read_bytes().replace(b'\r\n',b'\n')
    assert wrapper._source_digest(source)==wrapper._CANDIDATE_SHA256_LF
    assert wrapper._source_digest(source.replace(b'\n',b'\r\n'))==wrapper._CANDIDATE_SHA256_LF
    assert wrapper._source_digest(source+b'\n# changed')!=wrapper._CANDIDATE_SHA256_LF

def test_baseline_modules_are_frozen_release_in_this_verification(wrapper):
    import examples.free_multigame_agent_v10 as baseline
    import examples.decision_audit as audit
    assert Path(baseline.__file__).resolve().is_relative_to(ROOT.resolve())
    assert Path(audit.__file__).resolve().is_relative_to(ROOT.resolve())
