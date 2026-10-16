"""Cost-only audit round trips: no server, credentials or live matches."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

from altruagent import WAIT
from altruagent.models import DecisionContext
from altruagent.runner import _with_game_config
from examples.decision_audit import AuditedAgent, redalert_cost_snapshot
from examples.fast_redalert_agent_v10 import FastRedAlertV10


def context(config=None, **kwargs):
    values=dict(session_id='local-fixture',tournament_id=None,game_type='red_alert',agent_id='fixture-agent',seat_position=0,game_config=config)
    values.update(kwargs)
    return DecisionContext(**values)


def entries(directory):
    return [json.loads(line) for path in sorted(directory.glob('*.jsonl')) for line in path.read_text().splitlines()]


def config_from_snapshot(entry):
    return {'rules':{group:{item:{'cost':value} for item,value in costs.items()} for group,costs in entry['costs'].items()}}


def test_whitelist_omits_non_cost_fields_and_secret_names():
    secret='eak_live_'+'a'*64
    config={'token':secret,'rules':{'units':{'e1':{'cost':100,'token':secret,'url':'private'},'e3':{'cost':300.0},'zero':{'cost':0},'official_key':{'cost':123},secret:{'cost':5},'sk-'+'z'*20:{'cost':9}},'private':{'cost':secret}},'observations':{'hidden_role':'wolf'}}
    original=deepcopy(config)
    snap=redalert_cost_snapshot(config)
    assert snap['costs']=={'actors':{},'units':{'e1':100,'e3':300.0,'zero':0},'buildings':{}}
    assert snap['status']=='partial'
    payload=json.dumps(snap,allow_nan=False)
    assert secret not in payload and 'private' not in payload and 'hidden_role' not in payload and 'token' not in payload
    assert config==original


def test_nonfinite_negative_boolean_and_string_prices_remain_unknown():
    invalid=[True,False,-1,-.5,float('nan'),float('inf'),float('-inf'),'100',None,{},[]]
    snap=redalert_cost_snapshot({'rules':{'units':{f'bad{i}':{'cost':cost} for i,cost in enumerate(invalid)}}})
    assert snap['status']=='no_valid_costs'
    assert snap['omitted_cost_entries']==len(invalid)
    assert not any(snap['costs'].values())
    json.dumps(snap,allow_nan=False)


def test_missing_config_rules_and_empty_costs_have_explicit_status():
    for value in (None,[], 'secret'):
        assert redalert_cost_snapshot(value)=={'schema_version':1,'source':'context.game_config.rules','status':'missing_config','costs':{}}
    for value in ({},{'rules':None},{'rules':'secret'}):
        assert redalert_cost_snapshot(value)['status']=='missing_rules'
    assert redalert_cost_snapshot({'rules':{}})['status']=='no_valid_costs'


def test_actual_sdk_context_round_trip_preserves_cost_lookup_precedence():
    delivered={'rules':{'actors':{'e1':{'cost':120,'weapon':'test'}},'units':{'e1':{'cost':100},'e3':{'cost':300},'3tnk':{'cost':1500}},'buildings':{'fix':{'cost':1200}}},'maps':{'omitted':True}}
    calls=[]
    game=SimpleNamespace(get_game_config=lambda kind:(calls.append(kind) or delivered))
    ctx=_with_game_config(game,context())
    assert calls==['red_alert'] and ctx.game_config is delivered
    snap=redalert_cost_snapshot(ctx.game_config)
    assert snap['status']=='available'
    rebuilt=replace(ctx,game_config=config_from_snapshot(snap))
    policy=FastRedAlertV10()
    assert [policy._cost(item,ctx) for item in ('e1','e3','3tnk','fix','powr')]==[policy._cost(item,rebuilt) for item in ('e1','e3','3tnk','fix','powr')]


def test_cost_event_once_per_match_seat_and_old_events_unchanged(tmp_path):
    action={'type':'orders','orders':[]}; seen=[]
    policy=SimpleNamespace(choose_action=lambda state,ctx:(seen.append(ctx) or action))
    agent=AuditedAgent(policy,tmp_path)
    state=SimpleNamespace(raw={'observation':{'cash':1}},new_messages=[])
    ctx=context({'rules':{'units':{'e1':{'cost':100}}}})
    for _ in range(3):
        assert agent.choose_action(state,ctx) is action
        agent.on_action_result({'accepted':True},ctx)
    logged=entries(tmp_path)
    assert [e['event'] for e in logged]==['cost_snapshot','decision','result','decision','result','decision','result']
    assert all(c is ctx for c in seen)
    assert [e['decision'] for e in logged if e['event']=='decision']==[action]*3
    # Old readers that select decision/result events need no schema migration.
    old_reader=[e for e in logged if e['event'] in {'decision','result'}]
    assert len(old_reader)==6
    for other in (replace(ctx,seat_position=1),replace(ctx,session_id='other-fixture')):
        assert agent.choose_action(state,other) is action
    assert sum(e['event']=='cost_snapshot' for e in entries(tmp_path))==3


def test_missing_snapshot_once_and_wait_still_logged(tmp_path):
    agent=AuditedAgent(SimpleNamespace(choose_action=lambda s,c:WAIT),tmp_path)
    ctx=context();state=SimpleNamespace(state_version=5)
    for _ in range(2): assert agent.choose_action(state,ctx) is WAIT
    logged=entries(tmp_path)
    assert [e['event'] for e in logged]==['cost_snapshot','wait_sample']
    assert logged[0]['status']=='missing_config'


def test_other_games_do_not_log_or_inspect_config(tmp_path):
    class NoConfig:
        session_id='other';seat_position=0;game_type='werewolf'
        @property
        def game_config(self): raise AssertionError('must not read other game config')
    action={'type':'vote','target':2}
    agent=AuditedAgent(SimpleNamespace(choose_action=lambda s,c:action),tmp_path)
    assert agent.choose_action(SimpleNamespace(raw={}),NoConfig()) is action
    assert [e['event'] for e in entries(tmp_path)]==['decision']


def test_disk_failure_preserves_action_and_retries_only_missing_snapshot(tmp_path):
    blocked=tmp_path/'blocked';blocked.write_text('fixture')
    action={'type':'orders','orders':[]}
    agent=AuditedAgent(SimpleNamespace(choose_action=lambda s,c:action),blocked)
    ctx=context({'rules':{'units':{'e1':{'cost':100}}}})
    state=SimpleNamespace(raw={})
    assert agent.choose_action(state,ctx) is action
    # Repoint this test-only object instead of changing the blocked file.
    agent.directory=tmp_path/'recovered'
    for _ in range(2): assert agent.choose_action(state,ctx) is action
    assert [e['event'] for e in entries(agent.directory)]==['cost_snapshot','decision','decision']


def test_partial_cost_schema_does_not_claim_complete_replay():
    # The policy's first truthy metadata section can shadow a later cost.
    # Dropping malformed metadata cannot reconstruct that case; flag partial.
    snap=redalert_cost_snapshot({'rules':{'actors':{'e1':{'weapon':'x'}},'units':{'e1':{'cost':100}}}})
    assert snap['status']=='partial' and snap['omitted_cost_entries']==1
