"""Offline contract tests for the zero-token tournament Red Alert agent.

These mocked states check only our logic and order syntax. They are not live
OpenRA matches, tournament scores, or evidence of competitive wins.
"""
from __future__ import annotations
import unittest
from types import SimpleNamespace
from altruagent import WAIT, WithReasoning
from examples.free_rule_agent import create_agent

CONTEXT = SimpleNamespace(game_type="red_alert")

def state(tick=100, units=None, buildings=None, production=None,
          legal=None, cash=5000, power=100, used_power=20, phase="playing"):
    raw = {
        "phase": phase,
        "observation": {
            "tick": tick, "units": units or [], "buildings": buildings or [],
            "production": production or [],
            "available_production": [],
            "economy": {"cash":cash, "power_provided":power,
                        "power_drained":used_power},
        },
        "legal_actions": legal or {},
    }
    return SimpleNamespace(raw=raw, legal_actions=[])

def orders(answer):
    assert isinstance(answer, WithReasoning), answer
    result=answer.action
    assert result["type"]=="orders"
    assert 1 <= len(result["orders"]) <= 20
    return result["orders"]

class RuleAgentContractTests(unittest.TestCase):
    def test_first_action_deploys_mcv(self):
        agent=create_agent()
        setup=state(units=[{"id":77,"type":"mcv"}],legal={"build":[]})
        self.assertEqual(orders(agent.choose_action(setup,CONTEXT)),
                         [{"cmd":"deploy","units":[77]}])
        self.assertIs(agent.choose_action(state(tick=101,units=[{"id":77,"type":"mcv"}]),CONTEXT),WAIT)
        self.assertEqual(orders(agent.choose_action(state(tick=147,units=[{"id":77,"type":"mcv"}]),CONTEXT)),
                         [{"cmd":"deploy","units":[77]}])

    def test_build_and_place_without_duplicate_queue(self):
        agent=create_agent()
        base=[{"id":4,"type":"fact"}]
        a=state(buildings=base,legal={"build":["powr","proc"]},power=0,used_power=20)
        self.assertEqual(orders(agent.choose_action(a,CONTEXT)),
                         [{"cmd":"build","item":"powr"}])
        later=state(tick=190,buildings=base,production=[
            {"item":"powr","queue":"Building","ready":True},
        ],legal={"build":["powr","proc"]},power=0)
        self.assertEqual(orders(agent.choose_action(later,CONTEXT)),
                         [{"cmd":"place","item":"powr"}])
        not_again=state(tick=191,buildings=base,production=[
            {"item":"powr","queue":"Building","ready":False},
            {"item":"proc","queue":"Building","ready":False},
        ],legal={"build":["powr","proc"]},power=0)
        self.assertIs(agent.choose_action(not_again,CONTEXT),WAIT)

    def test_server_supplied_attack_and_training(self):
        base=[{"type":t,"id":i} for i,t in enumerate(["fact","powr","proc","tent","weap"],1)]
        infantry=[{"type":"e1","id":100+i} for i in range(6)]
        action={"cmd":"attack_move","units":[100,101,102,103,104,105],"to":[95,11]}
        agent=create_agent()
        a=state(tick=200,buildings=base,units=infantry,cash=1000,
                legal={"attack_now":action,"train":["e1"]})
        self.assertEqual(orders(agent.choose_action(a,CONTEXT)),[action])
        self.assertEqual(orders(agent.choose_action(state(
            tick=201,buildings=base,units=infantry[:2],cash=1000,
            legal={"train":["e1"]}),CONTEXT)),
            [{"cmd":"train","item":"e1","count":3}])
        next_state=state(tick=202,buildings=base,units=infantry[:2],cash=1000,
                         legal={"train":["e1"]})
        self.assertIs(agent.choose_action(next_state,CONTEXT),WAIT)

    def test_non_playing_is_idle(self):
        agent=create_agent()
        self.assertIs(agent.choose_action(state(phase="waiting_for_agents"),CONTEXT),WAIT)

if __name__ == "__main__":
    unittest.main()
