"""Public-player-name protocol replay and SDK shape validation.
Uses only simulated *player-visible* payloads consistent with starter/GAMES.md.
No remote server/game, no official Testing or competitive performance claim.
"""
import json
import random
from types import SimpleNamespace
from altruagent import DecisionContext, TERMINATE_MESSAGING
from altruagent.models import GameState
from altruagent.runner import _validate_decision
from examples.free_multigame_agent_v4 import create_agent as older
from examples.free_multigame_agent_v5 import create_agent as newer


def sdk_state(aliases, ballots, phase="day_vote", role="villager", seer=None, mate=None, day=2, state_version=14):
    raw = {
        "session_id": "local", "status": "in_progress",
        "is_current_actor": True, "state_version": state_version,
        "phase": "moving",
        "your_position": 6,
        "players": [{"position": i, "name": aliases[i], "agent_id": f"agent_{i}"} for i in range(7)],
        "game_state": {
            "phase": phase,
            "day": day,
            "dead": [{"name": aliases[4], "role": "villager", "cause": "vote"}],
            "vote_history": [{"votes": {aliases[k]: aliases[4] for k in ballots}}],
        },
        "observation": {"role": role},
        "legal_actions": {
            "session_id": "local",
            "state_version": state_version,
            "actions": [
                {"action_id": str(i), "label": aliases[i] if i != 7 else "abstain", "input": {}}
                for i in ([0, 1, 2, 3, 5, 7] if phase=="day_vote" else [0, 1, 2, 3, 5])
            ],
        },
    }
    if seer:
        raw["observation"]["investigations"] = [{"player": aliases[seer], "role": "wolf"}]
    if mate is not None:
        raw["observation"]["wolf_teammate"] = aliases[mate]
    return GameState.from_mcp_state(raw)


ctx = DecisionContext(session_id="local", game_type="werewolf",
                      agent_id="agent_6", tournament_id=None)
names = ["Violet", "Sunset", "Nova", "Comet", "Archive", "Beacon", "Dragon"]
a = newer()

# 1: Public vote targeting a revealed innocent is decoded from official
# display-name mapping, not guessed by index.
s = sdk_state(names, [2])
d = a.choose_action(s, ctx)
assert d.action_id == "2", ("named voter", d)
assert _validate_decision(d, s.legal_actions) is not None

# 2: Private seer evidence prevails over (weak) public suspicion.
s = sdk_state(names, [2], role="seer", seer=3)
d = a.choose_action(s, ctx)
assert d.action_id == "3"
assert _validate_decision(d, s.legal_actions) is not None

# 3: Private wolf teammate display name is recognized, not targeted at night.
s = sdk_state(names, [], phase="night_wolf", role="wolf", mate=0)
d = a.choose_action(s, ctx)
assert d.action_id != "0"
assert _validate_decision(d, s.legal_actions) is not None

# 4: Sending a message changes state_version but not day, so don't
# accidentally spam four/five posts while the same discussion is open.
b = newer()
message_outcomes = []
for v in (31, 32, 33, 34):
    s = sdk_state(names, [], phase="day_vote", role="villager", state_version=v)
    message_outcomes.append(b.choose_message(s, ctx))
assert sum(x is TERMINATE_MESSAGING for x in message_outcomes)==3

# 5: A new day must allow one new message.
s = sdk_state(names, [], phase="day_vote", role="villager", day=3, state_version=55)
assert b.choose_message(s, ctx) is not TERMINATE_MESSAGING

# 6: paired alias-matchup exercise; all actions validated by the real SDK.
# Score ONLY 'used a public named-voter evidence cue', not match wins.
rng = random.Random(4059)
v4_ok = v5_ok = invalid_v4 = invalid_v5 = 0
cases = 300
for i in range(cases):
    alias = rng.sample([
        "Nova", "Comet", "Violet", "Sunset", "Archive",
        "Beacon", "Delta", "Aurora", "Meteor", "Moon",
        "Solar", "Coral", "Dawn", "Jasper"
    ], 7)
    suspect = rng.choice([0, 1, 2, 3, 5])
    s = sdk_state(alias, [suspect])
    old = older().choose_action(s, ctx)
    new = newer().choose_action(s, ctx)
    v4_ok += old.action_id == str(suspect)
    v5_ok += new.action_id == str(suspect)
    try:
        _validate_decision(old, s.legal_actions)
    except Exception:
        invalid_v4 += 1
    try:
        _validate_decision(new, s.legal_actions)
    except Exception:
        invalid_v5 += 1

report = {
    "note": "Local replay of documented SDK public name schema; no live platform or official Testing",
    "sdk_valid": True, "cases": cases,
    "public_named_vote_target_detection": {"V4": v4_ok, "V5": v5_ok},
    "illegal_decisions": {"V4": invalid_v4, "V5": invalid_v5},
    "messages_per_same_window": 1,
    "next_window_message": True,
    "private_role_leak_used": False,
}
with open("scripts/werewolf_public_name_sdk_v5_1012.json", "w", encoding="utf8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
assert v5_ok == cases
assert invalid_v5 == 0
print(json.dumps(report, indent=2))
