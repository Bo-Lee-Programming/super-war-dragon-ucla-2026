"""16 transparent PUBLIC-MECHANIC fixture decisions; not official match results.

Every pair has an unambiguous type-effectiveness preferred target. Two
orientations remove the "always target slot 1" advantage. Counts decision
quality (correct target), NOT win rate, expected damage or official score.
"""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from altruagent import LegalAction
from examples.free_multigame_agent import create_agent as baseline
from examples.free_multigame_agent_v2 import create_agent as candidate

# (attacking_move, known_opponent_A, known_opponent_B, preferred_opponent)
PAIRS = [
    ("thunderbolt", "Garchomp", "Gyarados", "Gyarados"),
    ("flamethrower", "Heatran", "Ferrothorn", "Ferrothorn"),
    ("hydropump", "Ferrothorn", "Heatran", "Heatran"),
    ("earthpower", "Gyarados", "Raichu", "Raichu"),
    ("icebeam", "Heatran", "Garchomp", "Garchomp"),
    ("energyball", "Charizard", "Groudon", "Groudon"),
    ("rockslide", "Torkoal", "Charizard", "Charizard"),
    ("shadowball", "Incineroar", "Cresselia", "Cresselia"),
    ("dracometeor", "Zacian", "Miraidon", "Miraidon")
]


def state(move, opponents):
    choice = {"type": "move", "move_id": move, "targets": [1, 2],
              "target_options": [{"side": "opponent", "target": n+1, "species": species}
                                 for n, species in enumerate(opponents)]}
    template = {"type": "doubles_turn", "slots": [
        {"slot": 0, "options": [choice]},
        {"slot": 1, "options": [{"type": "pass"}]}
    ]}
    action = LegalAction(action_id="doubles_turn", label="server template",
                         input={"action": template})
    return SimpleNamespace(legal_actions=[action], raw={"observation": template})


def run():
    agents = {"baseline_v1": baseline(), "type_aware_v2": candidate()}
    context = SimpleNamespace(game_type="pokemon_vgc_doubles_draft")
    wins = {name: 0 for name in agents}
    records = []
    for move, a, b, preferred in PAIRS:
        for opponents in ((a, b), (b, a)):
            preferred_target = opponents.index(preferred) + 1
            s = state(move, opponents)
            chosen = {}
            for name, policy in agents.items():
                output = policy.choose_action(s, context)
                target = output["slot_0"].get("target")
                chosen[name] = target
                wins[name] += int(target == preferred_target)
            records.append({"move": move, "opponents": list(opponents),
                            "preferred_target": preferred_target,
                            "chosen_target": chosen})
    result = {
        "kind": "public_game_mechanics_local_fixture_benchmark",
        "official_testing": False, "showdown_simulation": False,
        "winner_claim": False,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "n_scenarios": len(records), "correct_target_counts": wins,
        "details": records
    }
    out = Path(__file__).with_name("pokemon_target_quality_1012.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="details"}, indent=2))
    print("evidence:", out)

if __name__ == "__main__":
    run()
