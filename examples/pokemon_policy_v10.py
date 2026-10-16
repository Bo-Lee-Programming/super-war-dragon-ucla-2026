"""Participant-view doubles policy with public static Pokemon Showdown facts.

All evaluations are approximate and intentionally make no exact KO/win claim.
Legal templates remain authoritative. There is no network, cross-seat state,
opponent private data, or dependency on the offline diagnostic recordings.
"""
from itertools import combinations, product
from copy import copy, deepcopy
import json
from pathlib import Path

from examples.free_multigame_agent import _dict, _observation, _template
from examples.free_multigame_agent_v2 import _norm, type_effect
from examples.free_multigame_agent_v3 import _visible_rosters
from examples.pokemon_policy_v9 import stage_factor

_DATA = json.loads(Path(__file__).with_name("pokemon_public_data_v10.json").read_text(encoding="utf8"))
_DEX, _MOVES = _DATA["species"], _DATA["moves"]
_PROTECT = {"protect", "detect", "spikyshield", "banefulbunker", "silktrap", "burningbulwark"}
_FRIENDLY = {"earthquake", "surf", "discharge", "boomburst", "bulldoze", "lavaplume"}
_BLOCK = {"levitate":"ground", "flashfire":"fire", "waterabsorb":"water", "stormdrain":"water",
          "dryskin":"water", "voltabsorb":"electric", "lightningrod":"electric",
          "motordrive":"electric", "sapsipper":"grass", "eartheater":"ground"}


def number(value, default=0):
    return float(value) if type(value) in (int, float) else float(default)


def types(mon):
    return tuple(str(t).lower() for t in (mon.get("types") or _DEX.get(_norm(mon.get("species")), {}).get("types", [])))


def stats(mon):
    return _dict(mon.get("base_stats")) or _DEX.get(_norm(mon.get("species")), {}).get("baseStats", {})


def hp(mon):
    if "current_hp_fraction" in mon:
        return max(0., min(1., number(mon["current_hp_fraction"], 1)))
    if number(mon.get("max_hp")) > 0:
        return max(0., min(1., number(mon.get("current_hp"), mon["max_hp"]) / mon["max_hp"]))
    return 0. if mon.get("fainted") else 1.


def present(mon):
    return bool(mon.get("species")) and not mon.get("fainted") and hp(mon) > 0


def flags(observation, key):
    value = observation.get(key, {})
    return {_norm(k) for k in value} if isinstance(value, (dict, list)) else set()


def move(option, observation=None, attacker=None):
    name = _norm(option.get("move_id", option.get("id", "")))
    data = _MOVES.get(name, {})
    result = {"name":name, "type":str(option.get("move_type", data.get("type", ""))).lower(),
              "power":number(option.get("base_power", data.get("basePower", 0))),
              "category":str(option.get("category", data.get("category", "Status"))).lower(),
              "priority":number(option.get("priority", data.get("priority", 0))),
              "target":data.get("target", "normal")}
    accuracy = option.get("accuracy", data.get("accuracy", 100))
    result["accuracy"] = 1. if accuracy is True else max(0., min(1., number(accuracy, 100) / (100 if number(accuracy, 100) > 1 else 1)))
    if result["category"] == "status" and _norm((attacker or {}).get("ability")) == "prankster":
        result["priority"] += 1
    weather = flags(observation or {}, "weather")
    if name == "weatherball" and weather:
        for keys, element in (({"raindance", "primordialsea"}, "water"), ({"sunnyday", "desolateland"}, "fire"),
                              ({"sandstorm"}, "rock"), ({"snow", "hail"}, "ice")):
            if weather & keys:
                result.update(type=element, power=100)
                break
    if name in {"thunder", "hurricane", "bleakwindstorm", "wildboltstorm", "sandsearstorm"} and weather & {"raindance", "primordialsea"}:
        result["accuracy"] = 1.
    if name in {"thunder", "hurricane"} and weather & {"sunnyday", "desolateland"}:
        result["accuracy"] = .5
    if name == "blizzard" and weather & {"snow", "hail"}:
        result["accuracy"] = 1.
    multihit = data.get("multihit")
    if isinstance(multihit, int):
        result["power"] *= multihit
    elif isinstance(multihit, list) and len(multihit) == 2:
        hits = 4.5 if _norm((attacker or {}).get("item")) == "loadeddice" else 3.
        if _norm((attacker or {}).get("ability")) == "skilllink":
            hits = multihit[1]
        result["power"] *= hits
    if name in {"waterspout", "eruption", "dragonenergy"}:
        result["power"] *= hp(attacker or {})
    if name == "facade" and (attacker or {}).get("status"):
        result["power"] *= 2
    return result


def stat(mon, name):
    value = number(stats(mon).get(name), 85) + 36
    ev = _dict(mon.get("evs") or _dict(mon.get("public_set")).get("evs")).get(name)
    if type(ev) in (int, float):
        value = number(stats(mon).get(name), 85) + 20 + ev / 8
    nature = _norm(mon.get("nature") or _dict(mon.get("public_set")).get("nature"))
    nature_effects = {"adamant":("atk","spa"),"jolly":("spe","spa"),"modest":("spa","atk"),
                      "timid":("spe","atk"),"bold":("def","atk"),"careful":("spd","spa"),
                      "calm":("spd","atk"),"brave":("atk","spe"),"quiet":("spa","spe"),
                      "relaxed":("def","spe"),"sassy":("spd","spe")}
    up, down = nature_effects.get(nature,(None,None))
    value *= 1.1 if name == up else .9 if name == down else 1
    value *= stage_factor(_dict(mon.get("boosts")).get(name))
    # This marker is derived only from observed public protocol -start/-end
    # events in prepare(), not inferred from a Booster Energy item or species.
    value *= number(_dict(mon.get("_public_stat_boosts")).get(name), 1)
    if name == "spe" and _norm(mon.get("status")) in {"par", "paralysis"}:
        value *= .5
    return value


def speed(mon, observation, own=True):
    result = stat(mon, "spe")
    if "tailwind" in flags(observation, "side_conditions" if own else "opponent_side_conditions"):
        result *= 2
    if _norm(mon.get("item")) == "choicescarf":
        result *= 1.5
    weather = flags(observation, "weather")
    ability = _norm(mon.get("ability"))
    if (ability == "swiftswim" and weather & {"raindance", "primordialsea"}
            or ability == "chlorophyll" and weather & {"sunnyday", "desolateland"}
            or ability == "sandrush" and "sandstorm" in weather
            or ability == "slushrush" and weather & {"snow", "hail"}):
        result *= 2
    return result


def grounded(mon):
    return ("flying" not in types(mon) and _norm(mon.get("ability")) != "levitate"
            and _norm(mon.get("item")) != "airballoon")


def damage(option, attacker, defender, observation=None, spread=False):
    """Expected HP fraction proxy, using only current exposed information."""
    observation = observation or {}
    m = move(option, observation, attacker)
    if m["category"] not in {"physical", "special"} or m["power"] <= 0:
        return 0.
    element, name = m["type"], m["name"]
    ability = _norm(defender.get("ability"))
    if (_BLOCK.get(ability) == element
            or element == "ground" and _norm(defender.get("item")) == "airballoon"):
        return 0.
    effectiveness = type_effect(element, types(defender))
    if name == "freezedry" and "water" in types(defender):
        effectiveness *= 4
    if ability == "wonderguard" and effectiveness <= 1:
        return 0.
    if effectiveness <= 0:
        return 0.
    physical = m["category"] == "physical"
    attack_stat, defense_stat = ("atk", "def") if physical else ("spa", "spd")
    if name == "bodypress":
        attack_stat = "def"
    if name in {"psyshock", "psystrike"}:
        defense_stat = "def"
    offense = stat(defender if name == "foulplay" else attacker, attack_stat)
    defense = stat(defender, defense_stat)
    if _norm(defender.get("item")) == "assaultvest" and defense_stat == "spd":
        defense *= 1.5
    if _norm(defender.get("item")) == "eviolite":
        defense *= 1.5
    value = (.44 * m["power"] * offense / max(1, defense) + 2) * effectiveness
    value *= 1.5 if element in types(attacker) else 1.
    if element in types(attacker) and _norm(attacker.get("ability")) == "adaptability":
        value *= 4/3
    item = _norm(attacker.get("item"))
    if item == "lifeorb":
        value *= 1.3
    if item == ("choiceband" if physical else "choicespecs"):
        value *= 1.5
    if physical and _norm(attacker.get("status")) in {"brn", "burn"} and name != "facade":
        value *= 1.5 if _norm(attacker.get("ability")) == "guts" else .5
    weather = flags(observation, "weather")
    if weather & {"raindance", "primordialsea"}:
        value *= 1.5 if element == "water" else .5 if element == "fire" else 1
    if weather & {"sunnyday", "desolateland"}:
        value *= 1.5 if element == "fire" else .5 if element == "water" else 1
    fields = flags(observation, "fields")
    if "grassyterrain" in fields and grounded(defender) and name in {"earthquake", "bulldoze", "magnitude"}:
        value *= .5
    if grounded(attacker):
        if (element == "grass" and "grassyterrain" in fields or element == "electric" and "electricterrain" in fields
                or element == "psychic" and "psychicterrain" in fields):
            value *= 1.3
    if "mistyterrain" in fields and grounded(defender) and element == "dragon":
        value *= .5
    if ability in {"multiscale", "shadowshield"} and hp(defender) == 1:
        value *= .5
    if ability in {"filter", "solidrock", "prismarmor"} and effectiveness > 1:
        value *= .75
    if ability == "thickfat" and element in {"fire", "ice"}:
        value *= .5
    if name == "knockoff" and defender.get("item") not in (None, "", "unknown_item"):
        value *= 1.5
    value *= m["accuracy"] * (.75 if spread else 1) * .925
    # Opponent HP in the API is often 100/100 (percentage), not real max HP.
    maximum = number(stats(defender).get("hp"), 85) + 90
    return value / max(80, maximum)


def _mon(value):
    return value if isinstance(value, dict) else {"species":str(value)}


def attacks(mon):
    result = []
    for value in list(mon.get("moves", [])) + list(_dict(mon.get("public_set")).get("moves", [])):
        option = {"move_id":value} if isinstance(value, str) else {**_dict(value), "move_id":_dict(value).get("id")}
        if move(option)["category"] in {"physical", "special"}:
            result.append(option)
    return result


def pressure(attacker, defender, observation=None):
    known = attacks(attacker)
    if known:
        return max(damage(o, attacker, defender, observation) for o in known)
    # A threat prior from public species STAB is not a claim of a revealed move.
    category = "physical" if stat(attacker, "atk") > stat(attacker, "spa") else "special"
    return max((damage({"move_type":t, "base_power":80, "category":category}, attacker, defender, observation)
                for t in types(attacker)), default=.2)


def _support(mon):
    moves = {_norm(m) for m in mon.get("moves", []) if isinstance(m, str)}
    species = _norm(mon.get("species"))
    # The penalty applies to overloaded teams, not to useful control itself.
    return species in {"amoonguss", "cresselia", "grimmsnarl", "klefki", "toxapex", "indeedeef", "whimsicott"} or len(moves & {"reflect", "lightscreen", "ragepowder", "spore", "healpulse"}) >= 2


def _team_value(team, foes):
    if not team:
        return 0.
    foes = foes or [{"species":"Arcanine"}, {"species":"Gyarados"}, {"species":"Rillaboom"}, {"species":"Iron Hands"}]
    total = 0.
    for foe in foes:
        offense = sorted((pressure(mon, foe) for mon in team), reverse=True)
        total += 30 * min(1., offense[0]) + (12 * min(.8, offense[1]) if len(offense) > 1 else 0)
        total -= 10 * min(pressure(foe, mon) for mon in team)
    total /= len(foes)
    total += sum(min(1., max(stat(mon,"atk"),stat(mon,"spa"))/170) * 7 for mon in team)
    support = sum(_support(mon) for mon in team)
    total += 5 * min(support, 1) - 14 * max(0, support - 2)
    moves = {_norm(m) for mon in team for m in mon.get("moves", []) if isinstance(m, str)}
    total += 6 * bool(moves & {"tailwind", "icywind", "trickroom", "electroweb"})
    total += 5 * ("fakeout" in moves)
    for attack_type in {t for foe in foes for t in types(foe)}:
        weak = sum(type_effect(attack_type, types(mon)) > 1 for mon in team)
        total -= 4 * max(0, weak - 2)
    return total


def draft_pick(state):
    legal = [a for a in getattr(state, "legal_actions", []) if str(a.action_id).startswith("draft_pick:")]
    if not legal:
        return None
    observation = _observation(_dict(state.raw))
    cards = observation.get("available_cards", [])
    by_id = {str(c.get("card_id")):c for c in cards if isinstance(c, dict)}
    own, enemy = _visible_rosters(observation, _dict(state.raw).get("your_position"))
    # Full public cards may be gone after drafting; species priors remain valid.
    ours, foes = [_mon(x) for x in own], [_mon(x) for x in enemy]
    scored = []
    for index, action in enumerate(legal):
        candidate = by_id.get(str(action.action_id).split(":", 1)[1])
        if candidate:
            team = ours + [candidate]
            value = max((_team_value(list(t), foes) for t in combinations(team, min(4,len(team)))), default=0)
            # Preserve broad bench options without preferring a seventh support.
            value += .8 * len({t for mon in team for t in types(mon)})
            scored.append((value, -index, action))
    return max(scored, key=lambda x:x[:2])[2] if scored else legal[0]


def lineup(state):
    roster = _template(state,"select_lineup").get("roster")
    if not isinstance(roster,list) or not all(isinstance(s,str) and s for s in roster) or not 4 <= len(set(roster)) <= 12:
        return None
    observation = _observation(_dict(state.raw))
    mine = {_norm(m.get("species")):m for m in observation.get("your_roster", []) if isinstance(m,dict)}
    foe_data = observation.get("opponent_roster", [])
    foes = [_mon(m) for m in foe_data] if isinstance(foe_data,list) else []
    best = max(combinations(dict.fromkeys(roster),4), key=lambda team:_team_value([mine.get(_norm(s),{"species":s}) for s in team],foes))
    def leads_value(pair):
        team = [mine.get(_norm(s),{"species":s}) for s in pair]
        movesets = [{_norm(m) for m in mon.get("moves",[]) if isinstance(m,str)} for mon in team]
        value = _team_value(team,foes) - 14 * max(0,sum(_support(m) for m in team)-1)
        value += 7 * any("fakeout" in moves for moves in movesets)
        value += 5 * any("tailwind" in moves for moves in movesets)
        return value
    leads = max(combinations(best,2),key=leads_value)
    return {"type":"select_lineup", "bring":list(best), "leads":list(leads)}


def _own_history(observation, slot):
    """Read only our board's public protocol to establish entry/previous move."""
    team = observation.get("team", {})
    side = next((str(k).split(":",1)[0] for k in team if str(k).startswith(("p1:","p2:"))), None) if isinstance(team,dict) else None
    if not side:
        return observation.get("turn") == 1, None
    actor = side + ("a" if slot == 0 else "b") + ":"
    entered, last, acted = False, None, False
    for line in observation.get("protocol_log", []):
        if not isinstance(line,str):
            continue
        parts = line.split("|")
        if len(parts) >= 4 and parts[1] in {"switch","drag","replace"} and parts[2].startswith(actor):
            entered, acted, last = True, False, None
        elif len(parts) >= 4 and parts[1] == "move" and parts[2].startswith(actor):
            acted, last = True, _norm(parts[3])
        elif len(parts) >= 4 and parts[1] == "cant" and parts[2].startswith(actor):
            acted = True
        elif parts[:2] == ["", "turn"] and entered:
            # Entry at the preceding turn followed by a new turn consumes Fake Out,
            # even if the Pokemon was asleep/flinched and did not execute a move.
            if len(parts) > 2 and parts[2].isdigit() and int(parts[2]) < number(observation.get("turn")):
                acted = True
    return (entered and not acted) or observation.get("turn") == 1, last


def _public_stat_effects(observation):
    """Current publicly announced paradox boosts, keyed by exact board slot.

    Pokemon Showdown announces the actual boosted stat (e.g. quarkdrivespe).
    A replacement Pokemon never inherits the departing occupant's effect.
    Missing or truncated evidence remains unknown rather than guessed.
    """
    effects = {}
    for line in observation.get("protocol_log", []):
        if not isinstance(line, str):
            continue
        parts = line.split("|")
        if len(parts) < 3 or ":" not in parts[2]:
            continue
        board, label = parts[2].split(":", 1)
        if board not in {"p1a", "p1b", "p2a", "p2b"}:
            continue
        event = parts[1]
        if event in {"switch", "drag", "replace", "faint"}:
            effects.pop(board, None)
        elif event == "-start" and len(parts) >= 4:
            effect = _norm(parts[3])
            for ability in ("quarkdrive", "protosynthesis"):
                stat_name = effect[len(ability):] if effect.startswith(ability) else ""
                if stat_name in {"atk", "def", "spa", "spd", "spe"}:
                    effects[board] = {"label":_norm(label), "ability":ability, "stat":stat_name}
                    break
        elif event == "-end" and len(parts) >= 4 and board in effects:
            ended = _norm(parts[3]).removeprefix("ability")
            if ended.startswith(effects[board]["ability"]):
                effects.pop(board, None)
    return effects


def _apply_public_stat_effects(observation, legal_actions):
    effects = _public_stat_effects(observation)
    own_side = next((str(k).split(":", 1)[0] for k in _dict(observation.get("team"))
                     if str(k).startswith(("p1:", "p2:"))), None)
    if own_side is None:
        return
    def mark(mon, board):
        if not isinstance(mon, dict):
            return
        mon.pop("_public_stat_boosts", None)
        effect = effects.get(board)
        if effect and effect["label"] in {_norm(mon.get("name")), _norm(mon.get("species"))}:
            mon["_public_stat_boosts"] = {effect["stat"]:1.5 if effect["stat"] == "spe" else 1.3}
    for own, active_key, team_key in ((True, "active_pokemon", "team"), (False, "opponent_active_pokemon", "opponent_team")):
        side = own_side if own else "p2" if own_side == "p1" else "p1"
        active = observation.get(active_key, [])
        if not isinstance(active, list):
            continue
        for i, mon in enumerate(active[:2]):
            board = side + ("a" if i == 0 else "b")
            mark(mon, board)
            if isinstance(mon, dict):
                for member in _dict(observation.get(team_key)).values():
                    if isinstance(member, dict) and member.get("active") and _norm(member.get("species")) == _norm(mon.get("species")):
                        mark(member, board)
    for action in legal_actions:
        template = _dict(_dict(action.input).get("action"))
        for slot in template.get("slots", []):
            if isinstance(slot, dict) and slot.get("slot") in (0, 1):
                mark(slot.get("active"), own_side + ("a" if slot["slot"] == 0 else "b"))


def _priority_blocked(mon, foe, observation, m, foes):
    if m["priority"] <= 0:
        return False
    return (_norm(mon.get("ability")) == "prankster" and m["category"] == "status" and "dark" in types(foe)
            or "psychicterrain" in flags(observation,"fields") and grounded(foe)
            or any(_norm(f.get("ability")) in {"dazzling","queenlymajesty","armortail"} for f in foes))


def _status_ok(name, foe, attacker, observation):
    # The platform hides an unrevealed ability as None even when the same
    # match's public draft card already disclosed it. A current revealed
    # ability overrides that original set. Do not revive consumed items from
    # the draft: item=None is meaningful and unknown_item is still unknown.
    ability = _norm(foe.get("ability") or _dict(foe.get("public_set")).get("ability"))
    item = _norm(foe.get("item"))
    if ability in {"goodasgold", "magicbounce"}:
        return False
    if name in {"spore","sleeppowder","hypnosis","thunderwave","willowisp","toxic"} and foe.get("status"):
        return False
    if "mistyterrain" in flags(observation,"fields") and grounded(foe):
        return False
    if name in {"spore","sleeppowder","hypnosis"}:
        if ability in {"insomnia","vitalspirit","sweetveil"} or ("electricterrain" in flags(observation,"fields") and grounded(foe)):
            return False
        # Hypnosis is not a powder move: Grass, Goggles and Overcoat do not
        # block it, while all three sleep moves fail on existing major status.
        return name == "hypnosis" or ("grass" not in types(foe) and ability != "overcoat" and item != "safetygoggles")
    if name == "thunderwave":
        return not any(t in {"ground","electric"} for t in types(foe)) and ability not in {"limber","voltabsorb","lightningrod","motordrive"}
    if name == "willowisp":
        return "fire" not in types(foe) and ability not in {"waterveil","waterbubble","thermalexchange","flashfire"}
    if name == "toxic":
        return not any(t in {"steel","poison"} for t in types(foe))
    return True


def doubles(state):
    slots = _template(state,"doubles_turn").get("slots")
    if not isinstance(slots,list) or len(slots) != 2:
        return None
    by_slot = {s.get("slot"):s for s in slots if isinstance(s,dict)}
    if set(by_slot) != {0,1}:
        return None
    observation = _observation(_dict(state.raw))
    active = [_dict(by_slot[i].get("active")) for i in (0,1)]
    foes = {}
    for slot in slots:
        for option in slot.get("options",[]):
            for d in option.get("target_options",[]) if isinstance(option,dict) else []:
                if isinstance(d,dict) and d.get("target") in (1,2) and d.get("species"):
                    foes[d["target"]] = dict(d)
    shown = observation.get("opponent_active_pokemon")
    if isinstance(shown,list):
        foes = {i+1:{**foes.get(i+1,{}),**m} for i,m in enumerate(shown[:2]) if isinstance(m,dict) and present(m)}
    candidates = []
    for i in (0,1):
        choices = []
        fresh, previous = _own_history(observation,i)
        for option in by_slot[i].get("options",[]):
            if not isinstance(option,dict):
                continue
            kind = option.get("type")
            if kind == "switch" and isinstance(option.get("species"),str):
                choices.append(({"type":"switch","species":option["species"]}, option, {}))
            elif kind == "pass":
                choices.append(({"type":"pass"}, option, {}))
            elif kind == "move" and isinstance(option.get("move_id"),str):
                targets = option.get("targets",[])
                if not isinstance(targets,list) or not all(type(t) is int for t in targets):
                    continue
                m = move(option,observation,active[i])
                if number(option.get("current_pp"),1) <= 0:
                    continue
                if m["name"] == "fakeout" and not fresh:
                    continue
                for target in targets or [None]:
                    if target in (1,2) and target not in foes and isinstance(shown,list):
                        continue
                    if target is not None and target < 0 and m["name"] not in {"pollenpuff","healpulse","floralhealing","helpinghand","coaching"}:
                        continue
                    if target in foes and (_priority_blocked(active[i],foes[target],observation,m,list(foes.values()))
                        or m["category"] == "status" and not _status_ok(m["name"],foes[target],active[i],observation)):
                        continue
                    if target in foes and m["type"] in {"water","electric"} and any(
                            _norm(f.get("ability")) == ("stormdrain" if m["type"] == "water" else "lightningrod")
                            for f in foes.values()):
                        continue
                    action = {"type":"move","move_id":option["move_id"]}
                    if target is not None:
                        action["target"] = target
                    choices.append((action,option,{**m,"previous":previous}))
        if not choices:
            return None
        candidates.append(choices)

    # A pass can be legal for either forced slot when only one reserve remains,
    # but passing both slots is not a legal joint choice. Require every available
    # replacement before comparing matchup scores, using only listed switches.
    forced_slots = [i for i in (0,1) if by_slot[i].get("force_switch")]
    reserve_species = {_norm(choice[0]["species"]) for i in forced_slots
                       for choice in candidates[i] if choice[0]["type"] == "switch"}
    required_replacements = min(len(forced_slots), len(reserve_species))

    team = { _norm(m.get("species")):m for m in _dict(observation.get("team")).values() if isinstance(m,dict)}
    for mons in observation.get("available_switches",[]):
        if isinstance(mons,list):
            team.update({_norm(m.get("species")):m for m in mons if isinstance(m,dict)})
    incoming = {(i,t):pressure(foe,active[i],observation) for i in (0,1) for t,foe in foes.items()}
    best = None
    for pair in product(*candidates):
        if pair[0][0]["type"] == pair[1][0]["type"] == "switch" and _norm(pair[0][0]["species"]) == _norm(pair[1][0]["species"]):
            continue
        if sum(pair[i][0]["type"] == "switch" for i in forced_slots) != required_replacements:
            continue
        score, damage_to, disabled = 0.,{t:0. for t in foes},{}
        fast_damage, contribution = {t:0. for t in foes}, [0.,0.]
        switched = [team.get(_norm(c[0].get("species")),{"species":c[0].get("species")}) if c[0]["type"] == "switch" else active[i] for i,c in enumerate(pair)]
        protect = [c[2].get("name") in _PROTECT and c[2].get("previous") not in _PROTECT for c in pair]
        offensive = [False,False]
        order = sorted((0,1),key=lambda i:(pair[i][2].get("priority",0), speed(active[i],observation)*(-1 if "trickroom" in flags(observation,"fields") else 1)),reverse=True)
        for i in order:
            action,option,m = pair[i]
            partner = pair[1-i]
            if action["type"] == "pass":
                continue
            if action["type"] == "switch":
                target = switched[i]
                forced = bool(by_slot[i].get("force_switch")) or not present(active[i])
                improvement = sum(incoming[i,t] - pressure(foe,target,observation) for t,foe in foes.items())
                score += 30 * improvement - (0 if forced else 23)
                score += 18 * max((pressure(target,foe,observation) for foe in foes.values()),default=0) + 5*hp(target)
                if _norm(active[i].get("ability")) == "regenerator" and hp(active[i]) < .7 and not forced:
                    score += 8
                continue
            name, target = m["name"], action.get("target",0)
            spread = target == 0 and (m["target"] in {"allAdjacent","allAdjacentFoes","all"} or name in _FRIENDLY)
            targets = list(foes) if spread else [target] if target in foes else []
            for t in targets:
                foe = foes[t]
                dealt = damage(option,active[i],foe,observation,spread and len(foes)+int(name in _FRIENDLY)>1)
                if dealt > 0:
                    offensive[i] = True
                    remaining = max(0.,hp(foe)-damage_to[t])
                    useful = min(remaining,dealt)
                    score += 100 * useful
                    contribution[i] += 100*useful
                    if remaining > .01 and dealt >= remaining:
                        score += 32 + 12 * min(1.,max(incoming[j,t] for j in (0,1)))
                        contribution[i] += 32
                    damage_to[t] += dealt
                    if m["priority"] > 0 or ((speed(active[i],observation)>speed(foe,observation,False)) != ("trickroom" in flags(observation,"fields"))):
                        fast_damage[t] += dealt
                    if name in {"icywind","electroweb","bulldoze"}:
                        score += 5 * (stat(foe,"spe") > max(stat(mon,"spe") for mon in active))
                    if name in {"drainpunch","gigadrain","drainingkiss"}:
                        score += 15 * min(1-hp(active[i]),dealt*.5)
                    if name in {"dracometeor","overheat","leafstorm","makeitrain"} and dealt < remaining:
                        score -= 7
                if name == "fakeout" and dealt > 0 and _norm(foe.get("ability")) not in {"innerfocus","shielddust"} and _norm(foe.get("item")) != "covertcloak":
                    disabled[t] = max(disabled.get(t,0),.95)
                if m["category"] == "status":
                    if name in {"spore","sleeppowder","hypnosis"}:
                        score += 26*m["accuracy"]
                        disabled[t] = max(disabled.get(t,0),.7*m["accuracy"])
                    elif name == "thunderwave":
                        score += 18 + 8*(speed(foe,observation,False)>speed(active[1-i],observation))
                    elif name == "willowisp":
                        score += 26 if stat(foe,"atk") > stat(foe,"spa") else 7
                    elif name == "partingshot":
                        score += 18 + 6*max(stage_factor(_dict(foe.get("boosts")).get("atk")),stage_factor(_dict(foe.get("boosts")).get("spa")))
                    elif name in {"taunt","encore"}:
                        score += 16 if _support(foe) else 2
                    elif name in {"toxic","leechseed"}:
                        score += 16 if hp(foe) > .6 else 4
            if name in _FRIENDLY and not protect[1-i] and present(switched[1-i]):
                harm = damage(option,active[i],switched[1-i],observation,True)
                score -= 125*min(hp(switched[1-i]),harm) + 35*(harm>=hp(switched[1-i]))
            if target is not None and target < 0 and name in {"pollenpuff","healpulse","floralhealing"}:
                healed = active[0 if target == -1 else 1]
                score += 75*min(.5,1-hp(healed))
            if name in _PROTECT:
                risk = sum(incoming[i,t] for t in foes)*.55
                score += min(35.,risk*35) - 23
                if m.get("previous") in _PROTECT:
                    score -= 28
            elif name == "tailwind":
                if "tailwind" in flags(observation,"side_conditions") or "trickroom" in flags(observation,"fields"):
                    score -= 35
                else:
                    crossings = sum(speed(mon,observation) < speed(foe,observation,False) < speed(mon,observation)*2 for mon in active for foe in foes.values())
                    score += 13 + 10*crossings
            elif name == "trickroom":
                slower = sum(speed(mon,observation)<speed(foe,observation,False) for mon in active for foe in foes.values())
                score += (slower-2)*16 * (-1 if "trickroom" in flags(observation,"fields") else 1)
            elif name in {"reflect","lightscreen","auroraveil"}:
                if name in flags(observation,"side_conditions"):
                    score -= 35
                else:
                    physical = name == "reflect"
                    score += 10 + 12*sum((stat(f,"atk")>=stat(f,"spa")) == physical for f in foes.values())
            elif name in {"recover","roost","synthesis","moonlight","slackoff"}:
                score += 80*min(.5,1-hp(active[i]))-8
            elif name == "helpinghand":
                if partner[0]["type"] == "move":
                    pt = partner[0].get("target")
                    score += 45*max((damage(partner[1],active[1-i],foes[t],observation) for t in foes if pt in (0,t)),default=0)
            elif name in {"ragepowder","followme"}:
                # A vacant/fainted board slot is not a vulnerable teammate.
                # Its placeholder stats otherwise create fictitious savings.
                if present(switched[1-i]):
                    partner_risk = sum(incoming[1-i,t] for t in foes)
                    self_risk = sum(incoming[i,t] for t in foes)
                    score += 15*(partner_risk-self_risk) + 7
            elif m["category"] == "status" and target not in foes and name not in _PROTECT:
                score += 2
        # Value preventing enemy actions; a fast KO is better than a slow trade.
        for t,foe in foes.items():
            neutralized = disabled.get(t,0.)
            if damage_to[t] >= hp(foe):
                faster = fast_damage[t] >= hp(foe)
                neutralized = max(neutralized,.9 if faster else .15)
            threat = max(incoming[i,t] for i in (0,1))
            score += 48*min(1.3,threat)*neutralized
        for i in (0,1):
            if contribution[i] <= 0 or pair[i][2].get("priority",0)>0:
                continue
            # Discount a slow attack likely to be stopped by an earlier KO.
            early = [incoming[i,t]*(1-disabled.get(t,0)) for t,foe in foes.items()
                     if fast_damage[t] < hp(foe) and ((speed(active[i],observation)<speed(foe,observation,False)) != ("trickroom" in flags(observation,"fields")))]
            danger = max(early,default=0) + .3*max(0,sum(early)-max(early,default=0))
            if danger > hp(active[i])*.75:
                score -= contribution[i] * min(.8,.65*danger/max(.1,hp(active[i])))
        if all(protect):
            score -= 60
        if best is None or score > best[0]:
            best = score,pair
    if best is None:
        return None
    return {"type":"doubles_turn", "slot_0":best[1][0][0], "slot_1":best[1][1][0]}


class PokemonPolicyV10:
    """Per-instance memory of publicly shown draft cards, scoped by match/seat."""
    def __init__(self):
        self._cards = {}

    def prepare(self, state, context):
        session = getattr(context,"session_id",None) or _dict(state.raw).get("session_id")
        agent = getattr(context,"agent_id",None)
        catalog = {}
        if session and agent:
            key = (session,agent)
            if key not in self._cards:
                if len(self._cards) >= 4:
                    self._cards.pop(next(iter(self._cards)))
                self._cards[key] = {}
            catalog = self._cards[key]
        original = _observation(_dict(state.raw))
        for card in original.get("available_cards",[]):
            if isinstance(card,dict) and card.get("species"):
                catalog[_norm(card["species"])] = deepcopy(card)
        if not catalog and not original.get("protocol_log"):
            return state
        observation = deepcopy(original)
        def annotate(value):
            if isinstance(value,dict):
                species = _norm(value.get("species"))
                if species in catalog:
                    value["public_set"] = catalog[species]
                for k,v in list(value.items()):
                    if k != "public_set":
                        annotate(v)
            elif isinstance(value,list):
                for v in value:
                    annotate(v)
        annotate(observation)
        changed = copy(state)
        changed.raw = {**_dict(state.raw),"observation":observation}
        # Active descriptors in legal templates also need the public set; never
        # change legal targets, IDs, move availability, or the caller's state.
        changed.legal_actions = deepcopy(state.legal_actions)
        for action in changed.legal_actions:
            annotate(action.input)
        _apply_public_stat_effects(observation, changed.legal_actions)
        return changed

    def choose_action(self,state,context):
        state = self.prepare(state,context)
        if not state.legal_actions:
            return None
        kind = str(state.legal_actions[0].action_id)
        return (draft_pick(state) if kind.startswith("draft_pick:") else lineup(state) if kind == "select_lineup"
                else doubles(state) if kind == "doubles_turn" else None)
