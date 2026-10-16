"""Offline contract tests. All seat tokens and execution IDs are synthetic."""
import asyncio
import json
import time
from datetime import datetime, timezone

import httpx
import pytest

from altruagent import mcp_transport as transport
from altruagent.client import AltruAgentClient
from altruagent.errors import AuthenticationError, is_transient_error
from altruagent.mcp_transport import call_tool, MCPToolError
from altruagent.models import SeatGrant
from altruagent.official import OfficialSeatAuth

URL = 'https://gameapi.example.test/mcp'

class Tokens:
    def __init__(self):
        self.calls = []
    def _current_access_token(self, *, force_relogin=False):
        self.calls.append(force_relogin)
        return 'synthetic-renewed' if force_relogin else 'synthetic-old'

def factory(handler):
    def create(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, transport=httpx.MockTransport(handler), follow_redirects=True)
    return create

def result(request, payload=None, **kwargs):
    body = json.loads(request.content)
    value = {'content': [], 'structuredContent': payload if payload is not None else {'ok': True}, 'isError': False}
    value.update(kwargs)
    return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'result': value})

def test_each_call_has_one_post_and_no_handshake_and_unique_id():
    requests = []
    def handler(request):
        requests.append(request)
        return result(request)
    client = Tokens()
    for _ in range(2):
        assert call_tool(client, URL, 'get_game_state', {'session_id': 'synthetic-session'}, httpx_client_factory=factory(handler)) == {'ok': True}
    assert len(requests) == 2
    assert all(r.method == 'POST' and str(r.url) == URL for r in requests)
    bodies = [json.loads(r.content) for r in requests]
    assert all(b['method'] == 'tools/call' for b in bodies)
    assert bodies[0]['id'] != bodies[1]['id']
    assert all(r.headers['accept'] == 'application/json, text/event-stream' and r.headers['content-type'] == 'application/json' for r in requests)
    assert all(r.headers['authorization'] == 'Bearer synthetic-old' for r in requests)

@pytest.mark.parametrize('status', [301, 302, 307, 308, 403, 408, 421, 429, 500, 503])
def test_non_401_never_refreshes_or_replays_even_redirect(status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={'Location': 'https://other.example.test/mcp', 'Retry-After': '1'}, json={'error': 'failure'})
    client = Tokens()
    with pytest.raises(MCPToolError) as exc:
        call_tool(client, URL, 'play_action', {'state_version': 1}, httpx_client_factory=factory(handler))
    assert exc.value.status_code == status
    assert len(requests) == 1 and client.calls == [False]

@pytest.mark.parametrize('fault', ['id', 'jsonrpc', 'missing_result', 'invalid_result', 'garbage', 'sse', 'rpc_error', 'both_result_error'])
def test_invalid_or_protocol_reply_stops_without_replay(fault):
    requests = []
    def handler(request):
        requests.append(request)
        body = result(request).json()
        if fault == 'id': body['id'] = 'wrong'
        if fault == 'jsonrpc': body['jsonrpc'] = '1.0'
        if fault == 'missing_result': body.pop('result')
        if fault == 'invalid_result': body['result'] = {'content': 'wrong'}
        if fault == 'rpc_error':
            body.pop('result')
            body['error'] = {'code': -32602, 'message': 'Invalid params'}
        if fault == 'both_result_error': body['error'] = {'code': -32602, 'message': 'Invalid params'}
        if fault == 'garbage': return httpx.Response(200, text='not JSON')
        if fault == 'sse': return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, text='event: message\ndata: ' + json.dumps(body) + '\n\n')
        return httpx.Response(200, json=body)
    with pytest.raises(MCPToolError) as exc:
        call_tool(Tokens(), URL, 'play_action', {}, httpx_client_factory=factory(handler))
    assert exc.value.protocol_error and not is_transient_error(exc.value)
    assert len(requests) == 1

def test_text_fallback_empty_structured_content_and_tool_error_semantics():
    values = [
        ({'structuredContent': None, 'content': [{'type': 'text', 'text': '{"state_version":7}'}]}, {'state_version': 7}),
        ({'structuredContent': {}, 'content': [{'type': 'text', 'text': '{"ignored":1}'}]}, {}),
        ({'structuredContent': None, 'content': [{'type': 'text', 'text': 'invalid-json'}]}, {}),
    ]
    for overrides, expected in values:
        assert call_tool(Tokens(), URL, 'get_game_state', {}, httpx_client_factory=factory(lambda r: result(r, **overrides))) == expected
    with pytest.raises(MCPToolError) as exc:
        call_tool(Tokens(), URL, 'play_action', {}, httpx_client_factory=factory(lambda r: result(r, isError=True, content=[{'type':'text','text':'bad action'}])))
    assert exc.value.protocol_error and not is_transient_error(exc.value)
    with pytest.raises(MCPToolError) as exc:
        call_tool(Tokens(), URL, 'play_action', {}, httpx_client_factory=factory(lambda r: result(r, {'error':'STALE_STATE','detail':'changed','next_actions':[{'tool':'get_game_state'}]})))
    assert exc.value.error_code == 'STALE_STATE' and exc.value.next_action == {'tool':'get_game_state'}

def test_longpoll_args_and_timeouts_are_preserved():
    arguments = {'session_id':'synthetic', 'since_version':23, 'since_message_seq':4, 'since_is_current_actor':False, 'since_phase':'battle', 'timeout_seconds':25}
    def handler(request):
        assert json.loads(request.content)['params']['arguments'] == arguments
        assert request.extensions['timeout'] == {'connect':10.0,'read':40.0,'write':10.0,'pool':10.0}
        return result(request, {'updated':False,'state_version':23})
    assert call_tool(Tokens(), URL, 'wait_for_update', arguments, httpx_client_factory=factory(handler))['updated'] is False

def test_sdk_supported_argument_conversion_matches_wire():
    value = datetime(2026, 1, 2, tzinfo=timezone.utc)
    def handler(request):
        assert json.loads(request.content)['params']['arguments'] == {'at':'2026-01-02T00:00:00Z','nothing':None}
        return result(request)
    call_tool(Tokens(), URL, 'test', {'at':value, 'nothing':None}, httpx_client_factory=factory(handler))

def test_unsendable_arguments_do_not_even_request_a_token():
    client = Tokens()
    with pytest.raises(MCPToolError) as exc:
        call_tool(client, URL, 'play_action', {'object':object()}, httpx_client_factory=lambda **kw: pytest.fail('network'))
    assert exc.value.local_error and client.calls == []

@pytest.mark.parametrize('error', [httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError])
def test_network_error_is_transient_and_not_replayed_inside_transport(error):
    requests = []
    def handler(request):
        requests.append(request)
        raise error('synthetic network failure', request=request)
    client = Tokens()
    with pytest.raises(MCPToolError) as exc:
        call_tool(client, URL, 'play_action', {}, httpx_client_factory=factory(handler))
    assert is_transient_error(exc.value) and len(requests) == 1 and client.calls == [False]

def test_whole_call_deadline_also_stops_trickling_body(monkeypatch):
    class Trickling(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b' '
                await asyncio.sleep(.01)
    monkeypatch.setattr(transport, 'MCP_SESSION_TIMEOUT_SECONDS', .1)
    started = time.monotonic()
    with pytest.raises(MCPToolError) as exc:
        call_tool(Tokens(), URL, 'wait_for_update', {}, httpx_client_factory=factory(lambda r: httpx.Response(200, stream=Trickling())))
    assert time.monotonic() - started < 2 and is_transient_error(exc.value)

@pytest.mark.parametrize('failure', [None, 'second_401', 'grant_error'])
def test_official_seat_refresh_keeps_execution_and_seat(failure):
    grants = []
    class Official:
        def grant(self, seat_id, execution_id):
            grants.append((seat_id, execution_id))
            if len(grants) == 2 and failure == 'grant_error':
                raise AuthenticationError('synthetic grant failed', status_code=503)
            return SeatGrant.from_dict({'seat_id':seat_id,'game_session_id':'synthetic-session','gameapi_server_url':'https://gameapi.example.test','agent_id':'synthetic-player','access_token':f'synthetic-{len(grants)}'})
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) == 1 or failure == 'second_401':
            return httpx.Response(401, json={'error':'UNAUTHENTICATED'})
        return result(request)
    with AltruAgentClient(control_url='https://gameapi.example.test', auth=OfficialSeatAuth(Official(), 'synthetic-seat', 'synthetic-execution'), load_env_file=False, transport=httpx.MockTransport(lambda r: pytest.fail('unexpected control call'))) as client:
        if failure:
            with pytest.raises(AuthenticationError if failure == 'grant_error' else MCPToolError):
                call_tool(client, URL, 'get_game_state', {}, httpx_client_factory=factory(handler))
        else:
            assert call_tool(client, URL, 'get_game_state', {}, httpx_client_factory=factory(handler)) == {'ok':True}
    assert grants == [('synthetic-seat','synthetic-execution')]*2
    assert len(requests) == (1 if failure == 'grant_error' else 2)
    assert [r.headers['authorization'] for r in requests] == ['Bearer synthetic-1','Bearer synthetic-2'][:len(requests)]

@pytest.mark.parametrize('mode', ['success', '401', '503', 'bad_json', 'unsendable'])
def test_production_default_uses_real_async_client_without_tls_changes(monkeypatch, mode):
    # No httpx_client_factory argument: exercise production selection, swapping
    # only the socket transport of the real AsyncClient for an offline mock.
    real_async_client = httpx.AsyncClient
    creations, requests = [], []
    def handler(request):
        requests.append(request)
        if mode == '401' and len(requests) == 1:
            return httpx.Response(401, json={'error':'UNAUTHENTICATED'})
        if mode == '503': return httpx.Response(503, json={'error':'AUTH_TEMPORARILY_UNAVAILABLE'})
        if mode == 'bad_json': return httpx.Response(200, text='<html>gateway</html>')
        return result(request)
    def instrumented(**kwargs):
        creations.append(kwargs)
        assert set(kwargs) == {'headers','timeout','auth'}
        assert kwargs['auth'] is None  # bearer header remains the sole auth
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(transport.httpx, 'AsyncClient', instrumented)
    client = Tokens()
    if mode in {'503','bad_json','unsendable'}:
        with pytest.raises(MCPToolError) as exc:
            call_tool(client, URL, 'play_action', {'value':object()} if mode == 'unsendable' else {})
        assert is_transient_error(exc.value) == (mode == '503')
    else:
        assert call_tool(client, URL, 'get_game_state', {}) == {'ok':True}
    expected = 0 if mode == 'unsendable' else 2 if mode == '401' else 1
    assert len(creations) == len(requests) == expected
    assert client.calls == ([] if mode == 'unsendable' else [False, True] if mode == '401' else [False])
