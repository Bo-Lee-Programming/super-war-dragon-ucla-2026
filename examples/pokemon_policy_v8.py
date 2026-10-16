"""Local candidate: legal joint choices and public roster weakness coverage.

Scores are heuristics, not damage estimates or competitive win probabilities.
Only legal templates and participant-visible metadata are consumed.
"""
from itertools import combinations, product

from examples.free_multigame_agent import _dict, _observation, _template
from examples.free_multigame_agent_v2 import (
    _SPECIES, _norm, _target_score, _move_type_power, type_effect,
)
from examples.free_multigame_agent_v3 import (
    _coverage_team_quality, _visible_rosters, _SUPPORT,
)

SPECIES = {**_SPECIES, "ironbundle": ("ice", "water"),
           "thundurus": ("electric", "flying"), "klefki": ("steel", "fairy"),
           "ironvaliant": ("fairy", "fighting"), "salamence": ("dragon", "flying"),
           "toxapex": ("water", "poison"), "porygon2": ("normal",)}


def types(descriptor):
    exposed = descriptor.get("types")
    if isinstance(exposed, list) and exposed and all(isinstance(t, str) for t in exposed):
        return tuple(t.lower() for t in exposed)
    return SPECIES.get(_norm(descriptor.get("species")), ())


def exposure(team, opponents):
    # Consider publicly drafted STAB types as potential threats, never assume
    # an opponent's unobserved moves, ability or final four have been revealed.
    threats = {t for s in opponents for t in types({"species": s})}
    penalty = 0.0
    for t in threats:
        factors = [type_effect(t, types({"species": s})) for s in team]
        weak = sum(f > 1 for f in factors)
        if weak >= 2:
            penalty += 12 * (weak - 1) + 4 * sum(max(0, f - 2) for f in factors)
            if min(factors, default=1) >= 1:
                penalty += 10  # no resistant or immune pivot in the chosen group
    return penalty


def lineup(state):
    roster = _template(state, "select_lineup").get("roster")
    if (not isinstance(roster, list) or not all(isinstance(s, str) and s for s in roster)
            or not 4 <= len(set(roster)) <= 12):
        return None
    raw = _dict(state.raw)
    _, opponents = _visible_rosters(_observation(raw), raw.get("your_position"))
    four = max(combinations(dict.fromkeys(roster), 4), key=lambda team:
               _coverage_team_quality(list(team), opponents) - exposure(team, opponents))
    def lead_score(pair):
        pressure = sum(max((type_effect(t, types({"species": foe}))
                           for s in pair for t in types({"species": s})), default=1)
                       for foe in opponents)
        return pressure + sum(_SUPPORT.get(_norm(s), 0) for s in pair) - exposure(pair, opponents)
    leads = max(combinations(four, 2), key=lead_score)
    return {"type": "select_lineup", "bring": list(four), "leads": list(leads)}


def doubles(state):
    slots = _template(state, "doubles_turn").get("slots")
    if not isinstance(slots, list) or len(slots) != 2:
        return None
    by_slot = {s.get("slot"): s for s in slots if isinstance(s, dict)}
    if set(by_slot) != {0, 1}:
        return None
    visible_foes = {}
    for slot in by_slot.values():
        for option in slot.get("options", []):
            for descriptor in option.get("target_options", []) if isinstance(option, dict) else []:
                if isinstance(descriptor, dict) and descriptor.get("target") in (1, 2) and descriptor.get("species"):
                    visible_foes[descriptor["target"]] = descriptor
    candidates = []
    for number in (0, 1):
        slot = by_slot[number]
        active = _dict(slot.get("active"))
        choices = []
        for opt in slot.get("options", []):
            if not isinstance(opt, dict):
                continue
            kind = opt.get("type")
            if kind == "switch" and isinstance(opt.get("species"), str):
                choices.append((7., {"type": "switch", "species": opt["species"]}))
            elif kind == "pass":
                choices.append((-100., {"type": "pass"}))
            elif kind == "move" and isinstance(opt.get("move_id"), str):
                targets = opt.get("targets", [])
                if not isinstance(targets, list) or not all(type(t) is int for t in targets):
                    continue
                descriptions = {d.get("target"): d for d in opt.get("target_options", [])
                                if isinstance(d, dict)}
                for target in targets or [None]:
                    descriptor = dict(descriptions.get(target, {}))
                    if types(descriptor):
                        descriptor["types"] = list(types(descriptor))
                    score = _target_score(opt, target or 0, descriptor, types(active))
                    name = _norm(opt["move_id"])
                    move_type, _ = _move_type_power(opt)
                    # Icy Wind deals damage; V2 accidentally gave it zero because
                    # it also appears in the status utility lookup.
                    if name == "icywind":
                        base = dict(opt, move_id="icebeam", base_power=55, move_type="ice")
                        score = _target_score(base, target or 0, descriptor, types(active))
                    elif name in ("freezedry", "waterfall"):
                        mt, power = ("ice", 70) if name == "freezedry" else ("water", 80)
                        base = dict(opt, move_id="icebeam" if mt == "ice" else "liquidation",
                                    base_power=power, move_type=mt)
                        score = _target_score(base, target or 0, descriptor, types(active))
                        move_type = mt
                        if name == "freezedry" and "water" in types(descriptor):
                            score *= 4  # its Water interaction is 2x instead of Ice's 0.5x
                    known_ability = _norm(descriptor.get("ability"))
                    immunities = {"levitate": "ground", "flashfire": "fire",
                                  "waterabsorb": "water", "stormdrain": "water",
                                  "voltabsorb": "electric", "lightningrod": "electric",
                                  "motordrive": "electric", "sapsipper": "grass"}
                    if target in (1, 2) and immunities.get(known_ability) == move_type:
                        score = -1000.
                    if target in (1, 2) and name in ("thunderwave", "spore", "sleeppowder"):
                        if ((name == "thunderwave" and any(t in ("ground", "electric") for t in types(descriptor)))
                                or (name != "thunderwave" and "grass" in types(descriptor))
                                or descriptor.get("status")):
                            score = -1000.
                    action = {"type": "move", "move_id": opt["move_id"]}
                    if target is not None:
                        action["target"] = target
                    choices.append((score, action))
        if not choices:
            return None
        candidates.append(choices)
    # A greedy slot-0 switch can steal slot 1's only legal replacement.
    # Search pairs before choosing, so both slots remain executable.
    best = None
    for a, b in product(*candidates):
        if (a[1]["type"] == b[1]["type"] == "switch"
                and _norm(a[1]["species"]) == _norm(b[1]["species"])):
            continue
        value = a[0] + b[0]
        for number, own, partner in ((0, a, b), (1, b, a)):
            action = own[1]
            if action.get("type") != "move" or action.get("target", 0) != 0:
                continue
            name = _norm(action.get("move_id"))
            friendly = name in ("earthquake", "surf", "discharge", "boomburst")
            if not friendly and name not in ("rockslide", "heatwave", "icywind", "dazzlinggleam", "hypervoice", "blizzard", "muddywater", "makeitrain", "electroweb"):
                continue
            option = next((o for o in by_slot[number].get("options", [])
                           if o.get("type") == "move" and o.get("move_id") == action["move_id"]), {})
            attacker = _dict(by_slot[number].get("active"))
            move_type, power = _move_type_power(option)
            if power <= 0:
                continue
            # Score each actual visible opponent; a spread move's target=0
            # is a field selector, not a neutral-typed Pokemon.
            def impact(descriptor):
                ability = _norm(descriptor.get("ability"))
                blocked = {"levitate":"ground", "flashfire":"fire", "waterabsorb":"water",
                           "stormdrain":"water", "voltabsorb":"electric", "lightningrod":"electric",
                           "motordrive":"electric", "sapsipper":"grass"}
                if blocked.get(ability) == move_type:
                    return 0.
                accuracy = option.get("accuracy", 100)
                accuracy = accuracy if type(accuracy) in (int, float) else 100
                accuracy = accuracy / 100 if accuracy > 1 else accuracy
                return power * type_effect(move_type, types(descriptor)) * accuracy * (1.5 if move_type in types(attacker) else 1)
            foes = list(visible_foes.values())
            total = sum(impact(foe) for foe in foes) if foes else impact({})
            ally = _dict(by_slot[1-number].get("active"))
            if partner[1].get("type") == "switch":
                ally = {"species": partner[1]["species"]}
            protected = partner[1].get("type") == "move" and _norm(partner[1].get("move_id")) in ("protect", "detect", "spikyshield", "banefulbunker", "silktrap")
            ally_hit = friendly and bool(ally.get("species")) and not protected
            spread = 0.75 if len(foes) + int(ally_hit) > 1 else 1.
            total *= spread
            if ally_hit:
                total -= 1.15 * spread * impact(ally)
            value += total - own[0]
        if best is None or value > best[0]:
            best = (value, a[1], b[1])
    if best is None:
        return None
    return {"type": "doubles_turn", "slot_0": best[1], "slot_1": best[2]}
