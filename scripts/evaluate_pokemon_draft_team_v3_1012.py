"""Paired local synthetic draft A/B; not a Pokémon battle or official match.

Replays a public 18-card pool and snake-draft from starter GAMES.md.
Independent type-based matchup proxy on drafted 4v4 squads; no server,
real-game outcomes, account access, secrets or opponent hidden information.
"""
from __future__ import annotations
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from altruagent import LegalAction
from examples.free_multigame_agent_v2 import create_agent as make_v2
from examples.free_multigame_agent_v3 import create_agent as make_v3, _types
from examples.free_multigame_agent_v2 import type_effect

CTX = SimpleNamespace(game_type="pokemon_vgc_doubles_draft")
DRAFT_ORDER = (0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0)
SPECIES = (
    "Gyarados", "Garchomp", "Ferrothorn", "Heatran", "Amoonguss", "Incineroar",
    "Rillaboom", "Flutter Mane", "Iron Hands", "Regieleki", "Landorus-Therian",
    "Tornadus", "Whimsicott", "Grimmsnarl", "Dialga", "Palkia", "Zacian",
    "Kyogre", "Groudon", "Calyrex-Shadow", "Miraidon", "Koraidon",
    "Ogerpon-Wellspring", "Ursaluna-Bloodmoon", "Kingambit", "Gholdengo",
    "Dragonite", "Archaludon", "Pelipper", "Palafin", "Tyranitar",
    "Excadrill", "Torkoal", "Venusaur", "Charizard", "Blastoise",
    "Pikachu", "Raichu", "Rotom-Wash", "Sylveon", "Cresselia",
)


def state_pick(available: list[dict], ours: list[str], rivals: list[str]):
    acts = [
        LegalAction(action_id=f"draft_pick:{c['card_id']}", label="Draft "+c["card_id"],
                    input={"action": {"type": "draft_pick", "card_id": c["card_id"]}})
        for c in available
    ]
    return SimpleNamespace(
        legal_actions=acts,
        raw={"your_position": 0, "observation": {
            "phase": "draft", "available_cards": available,
            "my_roster": ours, "opponent_roster": rivals,
        }},
    )


def state_lineup(ours, rivals):
    template = {"type": "select_lineup", "roster": ours, "bring_count": 4,
                "lead_count": 2}
    action = LegalAction(action_id="select_lineup", label="Team preview",
                         input={"action": template})
    return SimpleNamespace(legal_actions=[action], raw={"observation": {
        "phase": "team_preview", "my_roster": ours, "opponent_roster": rivals,
    }})


def run_draft(seed: int, agents):
    rng = random.Random(seed)
    pool = rng.sample(SPECIES, 18)
    rng.shuffle(pool)
    available = [{"card_id": f"c{i:02d}", "species": s} for i, s in enumerate(pool)]
    rosters = [[], []]
    for seat in DRAFT_ORDER:
        agent = agents[seat]
        act = agent.choose_action(state_pick(available, rosters[seat],
                                               rosters[1-seat]), CTX)
        chosen = str(act.action_id).split(":", 1)[-1]
        card = next(c for c in available if c["card_id"] == chosen)
        rosters[seat].append(card["species"])
        available.remove(card)
    return rosters


def choose_four(agent, ours, rivals):
    result = agent.choose_action(state_lineup(ours, rivals), CTX)
    assert len(set(result["bring"])) == 4
    assert set(result["bring"]) <= set(ours)
    assert len(set(result["leads"])) == 2
    assert set(result["leads"]) <= set(result["bring"])
    return result["bring"]


def offense(team, foes):
    # Held-out metric: average best hypothetical STAB type effectiveness of
    # each active Pokemon vs each foe, not V3's lineup objective function.
    vals = []
    for member in team:
        for foe in foes:
            attack, defending = _types(member), _types(foe)
            if attack and defending:
                vals.append(max(type_effect(t, defending) for t in attack))
    return sum(vals) / len(vals) if vals else 0.


def matchup_advantage(a, b):
    return offense(a, b) - offense(b, a)


def simulate_pair(seed: int, strong_is_seat: int):
    versions = [make_v2(), make_v2()]
    baseline_draft = run_draft(seed, versions)
    baseline_bring = [choose_four(make_v2(), baseline_draft[i],
                                  baseline_draft[1-i]) for i in (0, 1)]
    versions = [make_v2(), make_v2()]
    versions[strong_is_seat] = make_v3()
    novel_draft = run_draft(seed, versions)
    novel_bring = [choose_four(versions[i], novel_draft[i],
                               novel_draft[1-i]) for i in (0, 1)]
    sign = 1 if strong_is_seat == 0 else -1
    return (
        sign * matchup_advantage(*baseline_bring),
        sign * matchup_advantage(*novel_bring),
        sum(_types(s) != () for s in novel_draft[strong_is_seat]),
    )


def main():
    samples = []
    for i in range(500):
        for seat in (0, 1):
            base, new, known = simulate_pair(9102026+i, seat)
            samples.append((base, new, known))
    bavg = sum(x[0] for x in samples)/len(samples)
    navg = sum(x[1] for x in samples)/len(samples)
    gains = sum(x[1] > x[0] for x in samples)
    ties = sum(abs(x[1]-x[0]) < 1e-9 for x in samples)
    outcome = {
        "kind": "local_public_type_matchup_proxy_paired_draft_fixture",
        "official_testing": False, "showdown_engine": False,
        "no_inferred_match_wins": True, "scenarios": len(samples),
        "seeds": 500, "seat_assignments_each": 2,
        "baseline_v2_matchup_advantage": round(bavg, 6),
        "candidate_v3_matchup_advantage": round(navg, 6),
        "delta": round(navg-bavg, 6),
        "candidate_improved_cases": gains,
        "candidate_tied_cases": ties,
        "cards_selected": 6, "team_preview_bring": 4,
        "bench_warning": "This ignores actual moves, items, abilities, speed, terrain and Showdown game mechanics. It is NOT win-rate.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    target = Path(__file__).with_name("pokemon_draft_team_v3_1012.json")
    target.write_text(json.dumps(outcome, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
