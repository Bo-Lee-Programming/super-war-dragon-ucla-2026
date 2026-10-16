import json
from types import SimpleNamespace

from examples.decision_audit import AuditedAgent, clean


def test_audit_redacts_fields_and_inline_credentials():
    value = clean({"official_key": "secret", "nested": [{"token": "secret"}],
                   "text": "eak_live_" + "a" * 64, "hp": 72})
    assert value == {"official_key": "[redacted]", "nested": [{"token": "[redacted]"}],
                     "text": "[redacted]", "hp": 72}


def test_audit_preserves_decision_and_feedback_and_separates_seats(tmp_path):
    action = {"type": "orders", "orders": []}
    results = []
    policy = SimpleNamespace(choose_action=lambda s, c: action,
                             on_action_result=lambda result, ctx: results.append(result))
    wrapped = AuditedAgent(policy, tmp_path)
    state = SimpleNamespace(raw={"observation": {"role": "seer"}}, messages=[])
    for seat in (0, 1):
        context = SimpleNamespace(session_id="match", game_type="werewolf", seat_position=seat)
        assert wrapped.choose_action(state, context) is action
        wrapped.on_action_result({"accepted": True}, context)
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 2
    assert results == [{"accepted": True}, {"accepted": True}]
    for file in files:
        entries = [json.loads(line) for line in file.read_text().splitlines()]
        assert [e["event"] for e in entries] == ["decision", "result"]
        assert len({e["seat"] for e in entries}) == 1


def test_audit_disk_failure_does_not_change_action(tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied")
    action = {"action": "vote", "target": 2}
    wrapped = AuditedAgent(SimpleNamespace(choose_action=lambda s, c: action), blocked)
    assert wrapped.choose_action(SimpleNamespace(raw={}), SimpleNamespace(session_id="x")) is action
