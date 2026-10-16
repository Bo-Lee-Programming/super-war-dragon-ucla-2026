"""Local contract scenarios only. NO official Testing or win-rate claim."""
import unittest
from types import SimpleNamespace
from altruagent import LegalAction, WAIT, TERMINATE_MESSAGING, SendMessage
from examples.free_multigame_agent import create_agent

def action(action_id, template=None):
    return LegalAction(action_id=action_id, label=action_id,
                       input={"action": template} if template else {})

def state(actions, *, raw=None, version=1):
    return SimpleNamespace(legal_actions=actions, raw=raw or {},
                           state_version=version, new_messages=[])

def context(game):
    return SimpleNamespace(game_type=game)

class FreeMultigameContract(unittest.TestCase):
    def test_redalert_actual_order_shape(self):
        a=create_agent()
        s=state([],raw={"phase":"playing","observation":{"tick":1,
                 "units":[{"type":"mcv","id":81}],"buildings":[],"production":[],
                 "economy":{"cash":5000,"power_provided":0,"power_drained":0}},
                 "legal_actions":{"build":[]}})
        d=a.choose_action(s,context("red_alert"))
        self.assertEqual(d.action,{"type":"orders","orders":[{"cmd":"deploy","units":[81]}]})

    def test_pokemon_draft_returns_existing_card(self):
        a=create_agent()
        choices=[action("draft_pick:card_11"),action("draft_pick:card_12")]
        self.assertIs(a.choose_action(state(choices),context("pokemon_vgc_doubles_draft")),choices[0])

    def test_pokemon_lineup_is_real_structured_action(self):
        a=create_agent()
        roster=["a","b","c","d","e","f"]
        result=a.choose_action(state([action("select_lineup",
                   {"type":"select_lineup","roster":roster})]),
                   context("pokemon_vgc_doubles_draft"))
        self.assertEqual(result,{"type":"select_lineup","bring":roster[:4],"leads":roster[:2]})

    def test_pokemon_doubles_prefers_attacks_not_pass_switch_or_ally(self):
        a=create_agent()
        slots=[{"slot":0,"options":[
             {"type":"pass"},{"type":"move","move_id":"tackle","targets":[-2]},
             {"type":"move","move_id":"thunderbolt","targets":[1,2],"base_power":90}]},
            {"slot":1,"options":[{"type":"switch","species":"x"},
                {"type":"move","move_id":"watergun","targets":[1,2],"base_power":40}]}]
        result=a.choose_action(state([action("doubles_turn",
                    {"type":"doubles_turn","slots":slots})]),context("pokemon_vgc_doubles_draft"))
        self.assertEqual(result["slot_0"],{"type":"move","move_id":"thunderbolt","target":1})
        self.assertEqual(result["slot_1"],{"type":"move","move_id":"watergun","target":1})

    def test_forced_switch_two_distinct_species(self):
        a=create_agent()
        slots=[{"slot":0,"options":[{"type":"switch","species":"x"},
                                    {"type":"switch","species":"y"}]},
               {"slot":1,"options":[{"type":"switch","species":"x"},
                                    {"type":"switch","species":"z"}]}]
        result=a.choose_action(state([action("doubles_turn",{"type":"doubles_turn","slots":slots})]),
                  context("pokemon_vgc_doubles_draft"))
        self.assertEqual(result["slot_0"],{"type":"switch","species":"x"})
        self.assertEqual(result["slot_1"],{"type":"switch","species":"z"})

    def test_bad_pokemon_template_fails_with_contract_error_not_typeerror(self):
        from examples.smoke_agent import SmokeAgentError
        a = create_agent()
        invalid_lineup = action("select_lineup",
                {"type":"select_lineup","roster":[{"species":"a"}, "b", "c", "d"]})
        with self.assertRaises(SmokeAgentError):
            a.choose_action(state([invalid_lineup]), context("pokemon_vgc_doubles_draft"))
        invalid_turn = action("doubles_turn", {"type":"doubles_turn",
                 "slots":[{"slot":[], "options":[{"type":"pass"}]},
                          {"slot":1, "options":[{"type":"pass"}]}]})
        with self.assertRaises(SmokeAgentError):
            a.choose_action(state([invalid_turn]), context("pokemon_vgc_doubles_draft"))

    def test_werewolf_villager_votes_not_abstain(self):
        a=create_agent()
        choices=[action(str(i)) for i in [0,1,2,7]]
        got=a.choose_action(state(choices,raw={"game_state":{"phase":"day_vote"},
                   "observation":{"role":"villager"},"your_position":3}),context("werewolf"))
        self.assertEqual(got.action_id,"0")

    def test_werewolf_seer_uses_private_confirmed_information(self):
        a=create_agent()
        choices=[action(str(i)) for i in [0,1,2,7]]
        got=a.choose_action(state(choices,raw={"game_state":{"phase":"day_vote"},
                   "observation":{"role":"seer",
                     "investigations":[{"player":2,"role":"wolf"}]},
                   "your_position":3}),context("werewolf"))
        self.assertEqual(got.action_id,"2")

    def test_werewolf_seer_checks_unknown(self):
        a=create_agent()
        choices=[action(str(i)) for i in [0,1,2]]
        got=a.choose_action(state(choices,raw={"game_state":{"phase":"night_seer"},
                   "observation":{"role":"seer",
                       "investigations":[{"player":0,"role":"villager"}]}}),context("werewolf"))
        self.assertEqual(got.action_id,"1")

    def test_werewolf_message_once(self):
        a=create_agent()
        s=state([],raw={"observation":{"role":"villager"}},version=31)
        self.assertIsInstance(a.choose_message(s,context("werewolf")), SendMessage)
        self.assertIs(a.choose_message(s,context("werewolf")), TERMINATE_MESSAGING)

if __name__=="__main__":
    unittest.main()
