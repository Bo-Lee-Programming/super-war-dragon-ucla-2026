"""Paired independent full-match Werewolf rules simulation.

DOES NOT call tournament Testing/server or use private competitive data.
Simulates documented 7-player 2-wolf/1-seer/4-villager game including
night1 no kill, first-night seer look, night kills, plurality voting,
3 no-elimination days, living/dead true roles, private seer checks.
All automated opponents are explicitly SYNTHETIC heuristic bots.
Reports wins, ties, terminal reasons and invalid actions.
"""
from __future__ import annotations
import json
import random
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from altruagent import LegalAction, TERMINATE_MESSAGING
from examples.free_multigame_agent_v3 import create_agent as v3
from examples.free_multigame_agent_v4 import create_agent as v4


def legal_action(seat):
    return LegalAction(action_id=str(seat), label=f"Player{seat}", input={})


def player_state(phase, seat, alive, roles, dead, votes, inspections, version):
    if phase == "night_wolf":
        permitted = [i for i in alive if i != seat and roles[i] != "wolf"]
    elif phase == "night_seer":
        permitted = [i for i in alive if i != seat]
    else:
        permitted = [i for i in alive if i != seat] + [7]
    observation = {"role": roles[seat]}
    if roles[seat] == "seer":
        observation["investigations"] = [
            {"seat": i, "role": ("wolf" if roles[i] == "wolf" else "villager")}
            for i in sorted(inspections.get(seat, set()))
        ]
    if roles[seat] == "wolf":
        others = [i for i in range(7) if roles[i] == "wolf" and i != seat]
        if others:
            observation["wolf_teammate"] = others[0]
    return SimpleNamespace(
        legal_actions=[legal_action(i) for i in permitted],
        raw={
            "your_position": seat,
            "observation": observation,
            "game_state": {
                "phase": phase,
                "dead": list(dead),
                "vote_history": list(votes),
            },
        },
        state_version=version,
        new_messages=[],
    )


def heuristic_action(seed, day, seat, phase, state, roles, inspections, claims):
    legal = [int(a.action_id) for a in state.legal_actions if str(a.action_id).isdigit()]
    if phase == "night_seer":
        options = [n for n in legal if n not in inspections.get(seat, set())]
        return min(options or legal)
    if phase == "night_wolf":
        return legal[random.Random(seed * 6781 + day * 137 + seat * 911).randrange(len(legal))]
    confirmed = [n for n in claims if n in legal]
    # Baselines only use public statements and their own seer private checks.
    if roles[seat] == "seer":
        for n in inspections.get(seat, set()):
            if roles[n] == "wolf" and n in legal:
                return n
    if confirmed and roles[seat] != "wolf":
        # The model does not know whether a public claim is true. In this
        # simplified baseline, claims are accepted with 70% probability.
        if random.Random(seed * 37 + day * 433 + seat).random() < 0.7:
            return min(confirmed)
    options = [n for n in legal if n != 7 and (roles[seat] != "wolf" or roles[n] != "wolf")]
    return options[random.Random(seed * 3011 + day * 577 + seat * 41).randrange(len(options))]


def run_match(seed, factory):
    rng = random.Random(seed)
    seats = list(range(7))
    rng.shuffle(seats)
    roles = ["villager"] * 7
    for s in seats[:2]:
        roles[s] = "wolf"
    roles[seats[2]] = "seer"
    ours = seed % 7
    our_role = roles[ours]
    bot = factory()
    ctx = SimpleNamespace(game_type="werewolf")
    alive = set(range(7))
    dead, votes = [], []
    inspections = {}
    day = 1
    no_elimination = 0
    invalid = 0
    night_index = 1
    pending_claims = set()

    def decision(seat, phase):
        nonlocal invalid
        state = player_state(
            phase, seat, sorted(alive), roles, dead, votes,
            inspections, version=day*100 + len(votes))
        if not state.legal_actions:
            return None
        if seat == ours:
            try:
                action = bot.choose_action(state, ctx)
                number = int(action.action_id)
            except Exception:
                invalid += 1
                number = int(state.legal_actions[0].action_id)
        else:
            number = heuristic_action(seed, day, seat, phase, state, roles, inspections, pending_claims)
        allowed = {int(a.action_id) for a in state.legal_actions}
        if number not in allowed:
            invalid += 1
            number = min(allowed)
        return number

    def eliminate(seat, cause):
        if seat not in alive:
            return
        alive.remove(seat)
        dead.append({"position": seat, "name": f"Player{seat}",
                     "role": roles[seat], "cause": cause})

    def terminal():
        wolves = sum(roles[i] == "wolf" for i in alive)
        good = len(alive) - wolves
        if wolves == 0:
            return "villager"
        if wolves >= good:
            return "wolf"
        return None

    for _ in range(18):  # finite runtime guard
        # Seer gets investigation on NIGHT 1, but nobody dies on that night.
        if any(roles[i] == "seer" for i in alive):
            seer = next(i for i in alive if roles[i] == "seer")
            inspected = decision(seer, "night_seer")
            if inspected is not None:
                inspections.setdefault(seer, set()).add(inspected)
        if night_index > 1:
            attacks = []
            for s in sorted(i for i in alive if roles[i] == "wolf"):
                v = decision(s, "night_wolf")
                if v is not None:
                    attacks.append(v)
            if attacks:
                tally = Counter(attacks)
                maxv = max(tally.values())
                target = min(k for k, v in tally.items() if v == maxv)
                eliminate(target, "night_kill")
                if terminal():
                    return dict(win=terminal()==("wolf" if our_role == "wolf" else "villager"),
                                role=our_role, reason="night_parity", days=day, invalid=invalid)
        # DAY: public evidence from an actual seer must be communicated to
        # listeners; for our agent call choose_message, other seers also speak.
        pending_claims.clear()
        for seat in sorted(alive):
            known = [n for n in inspections.get(seat, set())
                     if roles[seat] == "seer" and roles[n] == "wolf" and n in alive]
            if seat == ours:
                state = player_state("day_vote", seat, sorted(alive), roles,
                                     dead, votes, inspections, day * 1000)
                try:
                    msg = bot.choose_message(state, ctx)
                    value = str(getattr(msg, "text", getattr(msg, "message", "")))
                    # This detects ONLY claims that were actually sent; it
                    # does not publish observations from hidden role state.
                    for n in known:
                        if f"Player{n}" in value and ("wolf" in value.lower()):
                            pending_claims.add(n)
                except Exception:
                    invalid += 1
            elif known:
                pending_claims.update(known)

        choices = {}
        for seat in sorted(alive):
            choices[seat] = decision(seat, "day_vote")
        ballot = {f"Player{s}": f"Player{v}" if v != 7 else "abstain"
                  for s, v in choices.items()}
        votes.append({"day": day, "votes": ballot})
        counted = Counter(v for v in choices.values() if v != 7 and v in alive)
        victim = None
        if counted:
            high = max(counted.values())
            leaders = [k for k, v in counted.items() if v == high]
            if len(leaders) == 1:
                victim = leaders[0]
        if victim is not None:
            eliminate(victim, "vote")
            no_elimination = 0
        else:
            no_elimination += 1
        outcome = terminal()
        if outcome or no_elimination >= 3:
            winner = outcome or "wolf"
            return dict(win=winner==("wolf" if our_role == "wolf" else "villager"),
                        role=our_role, reason="parity" if outcome else "three_stalls",
                        days=day, invalid=invalid)
        day += 1
        night_index += 1
    return dict(win=False, role=our_role, reason="guard", days=day, invalid=invalid)


def main():
    samples = 1600
    results = {}
    diffs = Counter()
    for label, factory in (("V3", v3), ("V4", v4)):
        matches = [run_match(seed, factory) for seed in range(samples)]
        results[label] = dict(
            samples=len(matches),
            win=sum(m["win"] for m in matches),
            win_rate=round(sum(m["win"] for m in matches)/samples, 5),
            role_results={
                role: {"matches": sum(m["role"] == role for m in matches),
                       "win": sum(m["win"] for m in matches if m["role"] == role)}
                for role in ("wolf", "seer", "villager")
            },
            reasons=dict(Counter(m["reason"] for m in matches)),
            invalid=sum(m["invalid"] for m in matches),
            mean_days=round(sum(m["days"] for m in matches)/samples, 3),
        )
        if label == "V3":
            old = matches
        else:
            for a, b in zip(old, matches):
                diffs["V4_win_V3_lose" if b["win"] and not a["win"]
                      else "V3_win_V4_lose" if a["win"] and not b["win"]
                      else "both_win" if a["win"] else "both_lose"] += 1
    results["paired"] = dict(diffs)
    results["limitations"] = (
        "Independent, simplified, 7-player seeded rules simulator with 6 "
        "synthetic heuristic opponents; NOT platform engine, official "
        "Testing, real agents, or competitive win rate. "
        "Public claims are naive; no full natural-language persuasion. "
        "Role-sensitive baseline sees only own role and private seer result."
    )
    out = Path(__file__).with_name("werewolf_fullgame_v4_1012.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
