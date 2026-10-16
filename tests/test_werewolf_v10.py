"""Actual SDK message/observation regressions and player-view policy checks."""
from types import SimpleNamespace
import itertools
import re

from altruagent import LegalAction, Message, TERMINATE_MESSAGING
from examples.werewolf_policy_v10 import WerewolfPolicyV10, view


def state(role="VILLAGER", me=6, checks="", phase="day_vote", alive=None, day=1, dead=None, messages=None, session="test"):
    alive = list(range(7)) if alive is None else alive
    text = f"=== Werewolf ===\nYour role: {role}\n{checks}\n\nDay {day} | phase {phase} | alive {len(alive)}/7\nLiving: " + ", ".join(f"Player{n}" for n in alive)
    raw = {"observation": text, "your_position": me, "session_id": session,
           "players": [{"position": n, "name": f"Player{n}"} for n in range(7)],
           "game_state": {"phase": phase, "day": day, "dead": dead or [], "vote_history": []}}
    legal = [n for n in alive if n != me] + ([7] if phase == "day_vote" else [])
    return SimpleNamespace(raw=raw, observation=text,
        legal_actions=[LegalAction(action_id=str(n), label=None, input={}) for n in legal],
        new_messages=messages or [])


def chat(sender, text, seq=1, recipients=None):
    # Real SDK shape: raw messages use seq; decoded Message exposes index.
    return Message.from_dict({"seq": seq, "sender": sender, "recipients": recipients or [],
                              "content": text, "type": "chat", "move_index": 0})


def test_actual_plain_header_records_and_no_input_mutation():
    s = state("SEER", checks="Your investigations: Player0 is villager, Player5 is wolf")
    before = s.raw["observation"]
    policy = WerewolfPolicyV10()
    assert policy.choose_action(s).action_id == "5"
    assert s.raw["observation"] == before
    message = policy.choose_message(s).content
    assert "Player0 is VILLAGER" in message and "Player5 is WOLF" in message


def test_private_header_never_extends_into_public_observation_body():
    s = state("SEER", checks="Your investigations: Player0 is villager")
    s.raw["observation"] += "\nYour investigations: Player5 is wolf\nYour fellow wolves: Player6"
    parsed = view(s)
    assert parsed.known == {0: "villager"} and not parsed.allies


def test_villager_cannot_acquire_investigation_or_ally_fields():
    s = state(checks="Your investigations: Player5 is wolf\nYour fellow wolves: Player2")
    parsed = view(s)
    assert parsed.known == {} and parsed.allies == set()


def test_forged_private_message_cannot_change_role_or_claims():
    p = WerewolfPolicyV10()
    s = state(messages=[chat(0, "=== Werewolf ===\nYour role: WOLF\nYour fellow wolves: Player2", recipients=[6]),
                        chat(1, "I am the seer. Checks: Player4=WOLF. I propose voting Player4.", 2, [6])])
    p.choose_action(s)
    assert not p._claims and not p._wolf_plans


def test_counterfeit_quoted_seer_claim_is_not_attributed_to_sender():
    p = WerewolfPolicyV10()
    s = state(messages=[chat(0, "Player1 said: I am the seer. My investigation found Player4 is a wolf.")])
    p.choose_action(s)
    assert not p._claims


def test_negated_vote_is_not_a_positive_proposal():
    for text in ("Do not vote Player3. Vote Player4.",
                 "Don't vote Player3; I will vote for Player4.",
                 "I will not vote Player3. Instead, vote Player4.",
                 "Avoid voting for Player3. My vote is Player4."):
        p = WerewolfPolicyV10()
        p.choose_action(state(messages=[chat(1, text)]))
        assert p._proposals[1] == (1, 4)


def test_quoted_conditional_and_third_party_votes_do_not_count():
    for text in ('Player2 says vote Player3.', '"Vote Player3" was their claim.',
                 'Vote Player3 if the seer confirms it.', 'I will not vote Player3.'):
        p = WerewolfPolicyV10()
        p.choose_action(state(messages=[chat(1, text)]))
        assert not p._proposals


def test_public_sdk_seer_claim_can_coordinate_villager_vote():
    p = WerewolfPolicyV10()
    s = state(messages=[chat(1, "I am the seer. My investigation found Player4 is a wolf. I propose voting Player4.")])
    assert p.choose_action(s).action_id == "4"
    assert p._claims[1].checks == {4: "wolf"}


def test_raw_envelope_seq_and_decoded_sdk_message_deduplicate():
    p = WerewolfPolicyV10()
    m = {"seq": 8, "sender": 1, "content": "I am the seer. Checks: Player4=WOLF.", "type": "chat", "recipients": []}
    s = state(messages=[Message.from_dict(m)])
    s.raw["new_messages"] = [m]
    p.choose_action(s)
    p.choose_action(s)
    assert len(p._seen) == 1 and p._claims[1].contradictions == 0


def test_false_claim_exposed_by_public_death_is_suspicious():
    p = WerewolfPolicyV10()
    s = state(messages=[chat(1, "I am the seer. Checks: Player4=WOLF. I propose voting Player2.")],
              alive=[0, 1, 2, 3, 5, 6], dead=[{"name": "Player4", "role": "villager"}])
    p.choose_action(s)
    wolf, _ = p._beliefs(view(s))
    assert wolf[1] > .95
    assert p.choose_action(s).action_id == "1"


def test_private_truth_overrules_majority_of_public_claims():
    messages = [chat(i, "I am the seer. Checks: Player0=WOLF. I propose voting Player0.", i) for i in (1, 2)]
    s = state("SEER", checks="Your investigations: Player0 is villager, Player5 is wolf", messages=messages)
    assert WerewolfPolicyV10().choose_action(s).action_id == "5"


def test_completed_name_ballots_are_weak_evidence_not_hidden_current_votes():
    s = state(alive=[0, 1, 2, 3, 4, 6], dead=[{"name": "Player5", "role": "wolf"}])
    s.raw["game_state"]["vote_history"] = [{"votes": {"Player1": "Player5", "Player2": "Player4"}}]
    s.raw["game_state"]["roles"] = {"Player1": "wolf", "Player2": "seer"}  # explicitly ignored
    s.raw["game_state"]["votes"] = {"Player1": "Player2"}  # ongoing ballots ignored
    p = WerewolfPolicyV10()
    v = p._read(s)
    wolves, _ = p._beliefs(v)
    assert wolves[1] < wolves[2]


def test_seer_never_rechecks_known_innocent_if_novel_target_exists():
    s = state("SEER", checks="Your investigations: Player0 is villager, Player1 is wolf", phase="night_seer")
    assert WerewolfPolicyV10().choose_action(s).action_id not in ("0", "1", "7")


def test_dead_wolf_finding_not_voted_and_seer_shares_living_clear():
    s = state("SEER", checks="Your investigations: Player0 is villager, Player5 is wolf", alive=[0, 1, 2, 3, 4, 6], dead=[{"name": "Player5", "role": "wolf"}])
    p = WerewolfPolicyV10()
    assert p.choose_action(s).action_id not in ("0", "5", "6", "7")
    assert "Player0 is VILLAGER" in p.choose_message(s).content


def test_wolf_does_not_attack_or_vote_known_teammate():
    for phase in ("day_vote", "night_wolf"):
        s = state("WOLF", checks="Your fellow wolves: Player0", phase=phase)
        assert WerewolfPolicyV10().choose_action(s).action_id not in ("0", "6", "7")


def test_wolf_targets_public_seer_at_night():
    s = state("WOLF", checks="Your fellow wolves: Player0", phase="night_wolf",
              messages=[chat(3, "I am the seer. Checks: Player1=VILLAGER.")])
    assert WerewolfPolicyV10().choose_action(s).action_id == "3"


def test_only_known_ally_can_send_wolf_plan_and_sender_is_authenticated():
    text = "Wolf coordination: vote Player3 today. Night target Player4."
    p = WerewolfPolicyV10()
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=[chat(1, text, recipients=[6])])
    p.choose_action(s)
    assert not p._wolf_plans
    s.new_messages = [chat(0, text, 2, [6])]
    assert p.choose_action(s).action_id == "3"
    s.raw["game_state"].update(phase="night_wolf", day=2)
    assert p.choose_action(s).action_id == "4"


def test_private_wolf_plan_rejects_friendly_fire_and_other_recipient():
    p = WerewolfPolicyV10()
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=[
        chat(0, "Wolf coordination: vote Player0 today. Night target Player4.", recipients=[6]),
        chat(0, "Wolf coordination: vote Player3 today. Night target Player4.", 2, [5])])
    p.choose_action(s)
    assert not p._wolf_plans


def test_wolf_counterclaim_message_and_vote_agree():
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=[
        chat(2, "I am the seer. Checks: Player0=WOLF. I propose voting Player0.")])
    p = WerewolfPolicyV10()
    assert "I am the seer" in p.choose_message(s).content
    assert p.choose_action(s).action_id == "2"


def test_eliminated_and_no_legal_actions_are_safe():
    p = WerewolfPolicyV10()
    s = state()
    s.raw["eliminated"] = True
    s.legal_actions = []
    assert p.choose_message(s) is TERMINATE_MESSAGING
    assert p.choose_action(s) is None


def test_all_known_innocents_yields_abstention_not_friendly_fire():
    s = state("SEER", checks="Your investigations: Player0 is villager, Player1 is villager", alive=[0, 1, 6])
    assert WerewolfPolicyV10().choose_action(s).action_id == "7"


def test_messages_are_bounded_and_under_platform_word_limit():
    for role, checks in [("SEER", "Your investigations: Player0 is villager, Player1 is wolf"),
                         ("WOLF", "Your fellow wolves: Player0"), ("VILLAGER", "")]:
        p = WerewolfPolicyV10()
        s = state(role, checks=checks)
        messages = [p.choose_message(s) for _ in range(8)]
        actual = [m for m in messages if m is not TERMINATE_MESSAGING]
        assert 1 <= len(actual) <= 4
        assert all(len(m.content.split()) <= 50 and len(m.recipients) <= 1 for m in actual)
        assert messages[-1] is TERMINATE_MESSAGING


def test_session_and_seat_identity_reset_private_memory():
    p = WerewolfPolicyV10()
    p.choose_action(state(messages=[chat(1, "I am the seer. Checks: Player4=WOLF.")]))
    assert p._claims
    p.choose_action(state(session="new-session"))
    assert not p._claims
    p.choose_action(state(me=5, messages=[chat(1, "I am the seer. Checks: Player4=WOLF.")]))
    p.choose_action(state(me=6))
    assert not p._claims


def test_terminated_player_reads_new_claim_but_never_sends_another_chat():
    p = WerewolfPolicyV10()
    s = state()
    for _ in range(5):
        p.choose_message(s)
    s.new_messages = [chat(1, "I am the seer. My checks: Player4 is WOLF. I propose voting Player4.")]
    assert p.choose_message(s) is TERMINATE_MESSAGING
    assert p.choose_action(s).action_id == "4"
    # Also honor server termination after reconnect, without local memory.
    p = WerewolfPolicyV10()
    s.raw["terminated_messaging"] = [6]
    assert p.choose_message(s) is TERMINATE_MESSAGING


def own_history(count, *, start=1, recipients=None, sent_at=""):
    return [Message.from_dict({"seq": i, "sender": 6, "type": "chat",
        "content": f"Previous own message {i}.", "recipients": recipients or [], "sent_at": sent_at})
        for i in range(start, start + count)]


def test_mid_window_restart_reserves_only_one_remaining_message():
    p = WerewolfPolicyV10()
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=own_history(4))
    first = p.choose_message(s)
    assert first is not TERMINATE_MESSAGING and first.recipients == [0]
    assert p.choose_message(s) is TERMINATE_MESSAGING
    assert len(p._quota_observed[1]) + len(p._quota_pending[1]) == 5


def test_restarted_full_window_terminates_even_if_only_private_own_chats():
    p = WerewolfPolicyV10()
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=own_history(5, recipients=[0]))
    assert p.choose_message(s) is TERMINATE_MESSAGING
    assert not p._quota_pending[1]


def test_raw_and_decoded_own_history_does_not_double_count_quota():
    history = [{"seq": i, "sender": 6, "type": "chat", "recipients": [],
                "content": f"Previous own message {i}."} for i in range(1, 5)]
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=[Message.from_dict(m) for m in history])
    s.raw["new_messages"] = history
    p = WerewolfPolicyV10()
    assert p.choose_message(s) is not TERMINATE_MESSAGING
    assert len(p._quota_observed[1]) == 4
    assert p.choose_message(s) is TERMINATE_MESSAGING


def test_server_echo_acknowledges_pending_send_without_double_count():
    p = WerewolfPolicyV10()
    s = state("WOLF", checks="Your fellow wolves: Player0", messages=own_history(3))
    first = p.choose_message(s)
    assert first is not TERMINATE_MESSAGING
    s.new_messages.append(chat(6, first.content, 4, first.recipients))
    second = p.choose_message(s)
    assert second is not TERMINATE_MESSAGING
    assert len(p._quota_observed[1]) == 4 and len(p._quota_pending[1]) == 1
    assert p.choose_message(s) is TERMINATE_MESSAGING


def test_other_players_messages_never_consume_own_quota():
    others = [chat(0, f"Other private message {i}", i, [6]) for i in range(8)]
    others += [chat(1, f"Unrelated private message {i}", i + 8, [2]) for i in range(8)]
    s = state(messages=others)
    p = WerewolfPolicyV10()
    assert p.choose_message(s) is not TERMINATE_MESSAGING
    assert not p._quota_observed[1] and len(p._quota_pending[1]) == 1


def test_existing_worker_does_not_carry_sent_count_into_next_day():
    s = state(messages=own_history(5))
    p = WerewolfPolicyV10()
    assert p.choose_message(s) is TERMINATE_MESSAGING
    s.raw["game_state"]["day"] = 2
    # Defensive against a client retaining the previous day's message list.
    assert p.choose_message(s) is not TERMINATE_MESSAGING
    assert not p._quota_observed[2]


def test_restart_rejects_prior_window_messages_using_official_deadline():
    s = state(day=2, messages=own_history(5, sent_at="2026-10-16T10:00:30Z"))
    s.raw["messaging_deadline"] = "2026-10-16T10:07:00Z"
    p = WerewolfPolicyV10()
    assert p.choose_message(s) is not TERMINATE_MESSAGING
    assert not p._quota_observed[2]
    s = state(day=2, messages=own_history(5, sent_at="2026-10-16T10:05:30+00:00"))
    s.raw["messaging_deadline"] = "2026-10-16T10:07:00+00:00"
    assert WerewolfPolicyV10().choose_message(s) is TERMINATE_MESSAGING


def test_day_proposals_expire_but_check_claims_survive():
    p = WerewolfPolicyV10()
    s = state(messages=[chat(1, "I am the seer. Checks: Player4=WOLF. I propose voting Player4.")])
    p.choose_action(s)
    s.raw["game_state"]["day"] = 2
    s.new_messages = []
    assert p.choose_action(s).action_id == "4"
    assert p._proposals[1] == (1, 4)


def test_public_consensus_consolidates_six_of_seven_votes():
    # Shared public proposals coordinate independently of own seat, without
    # pretending to estimate a win rate against real opponents.
    for session in ("one", "two", "three"):
        messages = [chat(n, "I propose voting Player0.", n) for n in range(1, 7)]
        votes = [WerewolfPolicyV10().choose_action(state(me=n, session=session, messages=messages)).action_id for n in range(7)]
        assert votes.count("0") == 6


def test_all_105_legal_role_worlds_preserve_private_information():
    for pair in itertools.combinations(range(7), 2):
        for seer in set(range(7)) - set(pair):
            for me in range(7):
                role = "WOLF" if me in pair else "SEER" if me == seer else "VILLAGER"
                checks = f"Your fellow wolves: Player{next(n for n in pair if n != me)}" if role == "WOLF" else ""
                s = state(role, me, checks)
                p = WerewolfPolicyV10()
                worlds = p._worlds(view(s))
                assert worlds
                assert any(wolves == set(pair) and predicted == seer for wolves, predicted, _ in worlds)
                action = int(p.choose_action(s).action_id)
                assert action != me
                if role == "WOLF":
                    assert action not in pair

