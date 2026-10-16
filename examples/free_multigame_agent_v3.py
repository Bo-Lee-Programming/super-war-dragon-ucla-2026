"""Super War Dragon V3: free, player-view Pokemon draft/team-preview policy.

The V2 battle policy, Red Alert and Werewolf remain unchanged.  Uses only
public/static Pokemon type data and the player's observation and legal actions.
No opponent hidden team, model API, spectator view or external match feed.
All selectors fall back to V2 when the public template is insufficient.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

from examples.free_multigame_agent import _dict, _observation, _template
from examples.free_multigame_agent_v2 import (
    SuperWarDragonV2, _SPECIES, _norm, type_effect,
)

# Coarse pre-match role priors; these are public species knowledge, not
# information about any unobserved opponent selections or moves.
_SUPPORT = {
    "incineroar": 1.8, "amoonguss": 1.7, "rillaboom": 1.3,
    "tornadus": 1.3, "whimsicott": 1.3, "grimmsnarl": 1.2,
    "indeedeef": 1.0, "cresselia": 1.0, "pelipper": 0.8,
}
_TYPES = (
    "normal", "fire", "water", "electric", "grass", "ice", "fighting",
    "poison", "ground", "flying", "psychic", "bug", "rock", "ghost",
    "dragon", "dark", "steel", "fairy",
)


def _species_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        return []
    answer = []
    for item in value:
        if isinstance(item, str):
            answer.append(item)
        elif isinstance(item, dict):
            species = item.get("species")
            if isinstance(species, str):
                answer.append(species)
    return answer


def _visible_rosters(observation: dict, our_position: Any) -> tuple[list[str], list[str]]:
    # The observation, rather than state.raw["game_state"], is the source:
    # game_state may contain fields not intended for the current player.
    ours = _species_list(observation.get("my_roster") or observation.get("your_roster"))
    theirs = _species_list(observation.get("opponent_roster"))
    rosters = observation.get("rosters")
    if isinstance(rosters, dict):
        for key, data in rosters.items():
            species = _species_list(data)
            if not species:
                continue
            own = str(key).lower() in (
                "me", "mine", "self", "you", str(our_position),
                f"player{our_position}", f"player_{our_position}",
            )
            if own and not ours:
                ours = species
            elif not own and not theirs and ours:
                theirs = species
    return ours, theirs


def _types(species: str) -> tuple[str, ...]:
    return _SPECIES.get(_norm(species), ())


def _attack_matchup(attack_species: str, defender_species: str) -> float:
    att, defense = _types(attack_species), _types(defender_species)
    if not att or not defense:
        return 1.0
    # Type-only upper bound: the species may not possess a move of this type.
    return max(type_effect(t, defense) for t in att)


def _coverage_team_quality(team: list[str], opponent: list[str]) -> float:
    """Type coverage plus unique role utility, NEVER an estimated match win."""
    if not team:
        return 0.
    known = [s for s in team if _types(s)]
    if not known:
        return 0.
    # Broad type matchup coverage prevents all-fire/all-water lineups.
    all_type_coverage = sum(
        min(4., max(type_effect(att, (defense,))
                    for member in known for att in _types(member)))
        for defense in _TYPES
    )
    diversity = len(set(t for s in known for t in _types(s)))
    support = sum(_SUPPORT.get(_norm(s), 0.) for s in known)
    redundancy = sum(max(0, sum(t in _types(s) for s in known) - 2)
                     for t in _TYPES)
    opponent_pressure = 0.
    for foe in opponent:
        if _types(foe):
            offensive = max(_attack_matchup(s, foe) for s in known)
            defensive = max(_attack_matchup(foe, s) for s in known)
            opponent_pressure += min(offensive, 4.) - 0.22 * min(defensive, 4.)
    return (all_type_coverage + diversity * 0.75 + support * 1.3
            + opponent_pressure * 2.0 - redundancy * 1.4)


def _draft_pick(state):
    actions = getattr(state, "legal_actions", [])
    legal = [a for a in actions if str(a.action_id).startswith("draft_pick:")]
    if not legal:
        return None
    observation = _observation(_dict(getattr(state, "raw", None)))
    cards = observation.get("available_cards")
    if not isinstance(cards, list):
        return legal[0]
    by_id = {str(c.get("card_id")): c for c in cards
             if isinstance(c, dict) and c.get("card_id") is not None}
    raw = _dict(getattr(state, "raw", None))
    own, opponent = _visible_rosters(observation, raw.get("your_position"))
    choices = []
    baseline = _coverage_team_quality(own, opponent)
    for index, action in enumerate(legal):
        card_id = str(action.action_id).split(":", 1)[-1]
        species = by_id.get(card_id, {}).get("species")
        if not isinstance(species, str) or not species:
            continue
        # Use only identities in the public available cards/roster.
        improvement = _coverage_team_quality(own + [species], opponent) - baseline
        choices.append((improvement, -index, action))
    return max(choices, key=lambda c: (c[0], c[1]))[2] if choices else legal[0]


def _lineup_v3(state):
    template = _template(state, "select_lineup")
    roster = template.get("roster")
    if (not isinstance(roster, list) or len(set(roster)) < 4 or
        any(not isinstance(s, str) or not s for s in roster)):
        return None
    observed = _observation(_dict(getattr(state, "raw", None)))
    raw = _dict(getattr(state, "raw", None))
    _, opponent = _visible_rosters(observed, raw.get("your_position"))
    # At most 6 choose 4 = 15 combinations, so exhaustive search is cheap.
    valid = list(dict.fromkeys(roster))
    if len(valid) > 12:
        return None
    best_four = max(
        combinations(valid, 4),
        key=lambda t: _coverage_team_quality(list(t), opponent)
    )
    # For leads, favor a support plus immediate favorable type matchups.
    def lead_score(pair):
        priors = sum(_SUPPORT.get(_norm(s), 0) for s in pair)
        direct = sum(max(_attack_matchup(s, foe) for s in pair)
                     for foe in opponent if _types(foe))
        concentration = 0.7 if _types(pair[0]) == _types(pair[1]) else 0.
        return priors + 1.2 * direct - concentration
    leads = max(combinations(best_four, 2), key=lead_score)
    return {"type": "select_lineup", "bring": list(best_four),
            "leads": list(leads)}


class SuperWarDragonV3(SuperWarDragonV2):
    def choose_action(self, state, context):
        game = str(getattr(context, "game_type", "") or "")
        if game == "pokemon_vgc_doubles_draft" and state.legal_actions:
            action_id = state.legal_actions[0].action_id
            if str(action_id).startswith("draft_pick:"):
                candidate = _draft_pick(state)
                if candidate is not None:
                    return candidate
            if action_id == "select_lineup":
                candidate = _lineup_v3(state)
                if candidate is not None:
                    return candidate
        return super().choose_action(state, context)


def create_agent():
    return SuperWarDragonV3()
