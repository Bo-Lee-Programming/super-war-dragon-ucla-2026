"""Official *starter SDK* local action contract, not a server match."""
from altruagent import DecisionContext
from altruagent.models import GameState
from altruagent.runner import _validate_decision
from examples.free_multigame_agent_v3 import create_agent

context = DecisionContext(session_id="local", tournament_id=None,
                          game_type="pokemon_vgc_doubles_draft", agent_id="local")
agent = create_agent()


def state(obs, actions):
    return GameState.from_mcp_state({
        "session_id": "local", "status": "in_progress",
        "state_version": 3, "is_current_actor": True,
        "observation": obs,
        "legal_actions": {"session_id": "local", "state_version": 3, "actions": actions},
    })


cards = [{"card_id": "a", "species": "Pikachu"},
         {"card_id": "b", "species": "Garchomp"},
         {"card_id": "c", "species": "Incineroar"}]
draft_legal = [
    {"action_id": f"draft_pick:{c['card_id']}",
     "label": "draft", "input": {"action": {"type": "draft_pick", "card_id": c["card_id"]}}}
    for c in cards
]
s = state({"phase": "draft", "available_cards": cards,
           "my_roster": ["Ferrothorn"], "opponent_roster": ["Gyarados"]}, draft_legal)
d = agent.choose_action(s, context)
assert _validate_decision(d, s.legal_actions) is not None
assert d.action_id in {a["action_id"] for a in draft_legal}

lineup = {"type": "select_lineup", "roster": [
    "Pikachu", "Garchomp", "Incineroar", "Ferrothorn", "Gyarados", "Amoonguss"
], "bring_count": 4, "lead_count": 2}
s = state({"phase": "team_preview", "opponent_roster": ["Kyogre", "Dialga"]}, [
    {"action_id": "select_lineup", "label": "Team preview", "input": {"action": lineup}}
])
d = agent.choose_action(s, context)
assert _validate_decision(d, s.legal_actions).action == d
assert len(d["bring"]) == 4 and len(d["leads"]) == 2

doubles = {"type": "doubles_turn", "slots": [
    {"slot": 0, "active": {"species": "Raichu"}, "options": [
        {"type": "move", "move_id": "thunderbolt", "base_power": 90,
         "targets": [1, 2], "target_options": [
            {"target": 1, "species": "Garchomp", "side": "opponent"},
            {"target": 2, "species": "Gyarados", "side": "opponent"},
         ]},
    ]},
    {"slot": 1, "active": None, "options": [{"type": "pass"}]},
]}
s = state({"phase": "moving"}, [
    {"action_id": "doubles_turn", "label": "Play", "input": {"action": doubles}}
])
d = agent.choose_action(s, context)
assert _validate_decision(d, s.legal_actions).action == d
assert d["slot_0"]["target"] == 2
print("SDK_CONTRACT_PASS 3/3: draft, lineup, V2 doubles; no game server contacted.")
