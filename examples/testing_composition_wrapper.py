"""Explicit Testing-only RA experiment router; formal matches always use baseline.

Publish this file as examples.testing_composition_wrapper and the frozen candidate
as examples.redalert_composition_memory_candidate. Set RA_COMPOSITION_TEST_SEATS
before process startup to a JSON object of exact DecisionContext.session_id UUIDs
and candidate 0-based seat integers, e.g. {"<real-test-session-uuid>": 0}.
No match discovery, network access, credentials or observation inspection occurs.
Missing/malformed configuration fails closed to baseline for every game.
"""
from __future__ import annotations

import json
import os
import hashlib
from importlib import import_module, util
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from examples.decision_audit import AuditedAgent
from examples.free_multigame_agent_v10 import SuperWarDragonV10

ENV_NAME = 'RA_COMPOSITION_TEST_SEATS'
_MISSING = object()
_CANDIDATE_MODULE = 'examples.redalert_composition_memory_candidate'
_CANDIDATE_SHA256_LF = '4330d32be5db5b53f638dd05dbeca8cc79cdc40fd8a9d9cf62326267f8fc5d2f'


def _source_digest(source):
    # Git may normalize CRLF on a research branch. Permit only that byte change.
    return hashlib.sha256(source.replace(b'\r\n', b'\n')).hexdigest()


def _load_candidate_class():
    """A broken optional research package must not break formal factories."""
    try:
        spec = util.find_spec(_CANDIDATE_MODULE)
        if spec is None or not spec.origin:
            return None
        source = Path(spec.origin)
        if source.suffix != '.py' or _source_digest(source.read_bytes()) != _CANDIDATE_SHA256_LF:
            return None
        factory = getattr(import_module(_CANDIDATE_MODULE), 'FastRedAlertV10', None)
        return factory if callable(factory) else None
    except Exception:
        return None


def _key_part(value):
    # Preserve exact type boundaries and keep malformed/unhashable identities
    # isolated without making the fallback itself fail before a baseline call.
    if value is None or type(value) in (str, int, bool):
        return (type(value).__name__, value)
    return ('invalid', type(value).__name__, id(value))


def parse_allowlist(encoded):
    """No wildcard/default route. Reject the entire ambiguous configuration."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate session')
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            return MappingProxyType({})
        for session, seat in value.items():
            if (not isinstance(session, str) or str(UUID(session)) != session
                    or type(seat) is not int or seat not in (0, 1)):
                return MappingProxyType({})
        return MappingProxyType(dict(value))
    except (ValueError, TypeError, AttributeError):
        return MappingProxyType({})


# Immutable for this process. Later environment edits cannot retarget a running seat.
_PROCESS_ALLOWLIST = parse_allowlist(os.environ.get(ENV_NAME, '{}'))


class TestingCompositionRouter:
    def __init__(self):
        self._agents = {}

    def _delegate(self, context):
        tournament = getattr(context, 'tournament_id', _MISSING)
        session = getattr(context, 'session_id', None)
        seat = getattr(context, 'seat_position', None)
        game = getattr(context, 'game_type', None)
        candidate = (tournament is None and game == 'red_alert'
                     and isinstance(session, str) and type(seat) is int
                     and session in _PROCESS_ALLOWLIST
                     and _PROCESS_ALLOWLIST[session] == seat)
        # Separate baseline/candidate instances even if a caller unexpectedly
        # changes context; a Testing candidate can never become a formal delegate.
        key = tuple(_key_part(x) for x in
                    (session, seat, game, tournament, getattr(context, 'agent_id', None))) + (candidate,)
        if key not in self._agents:
            agent = SuperWarDragonV10()
            if candidate:
                factory = _load_candidate_class()
                try:
                    if factory is None:
                        raise RuntimeError('Candidate unavailable')
                    replacement = factory()
                except Exception:
                    print(f'[RA experiment pid={os.getpid()} session={session} seat={seat}] '
                          'candidate unavailable; baseline selected', flush=True)
                else:
                    agent._redalert_v6 = replacement
                    print(f'[RA experiment pid={os.getpid()} session={session} seat={seat}] '
                          'approved candidate selected', flush=True)
            self._agents[key] = agent
        return self._agents[key]

    def choose_action(self, state, context):
        return self._delegate(context).choose_action(state, context)

    def choose_message(self, state, context):
        return self._delegate(context).choose_message(state, context)

    def on_action_result(self, result, context):
        return self._delegate(context).on_action_result(result, context)


def create_agent():
    return AuditedAgent(TestingCompositionRouter())
