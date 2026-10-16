"""Super War Dragon V2: local, free, player-visible Pokemon decisions.

Revision is deliberately a separate candidate from v1. Never reads a
spectator state, live web feed, private opponent roles, or paid model.
GameAPI's legal action template is the authority. If metadata is missing,
the original verified v1 decision is used.
"""
from __future__ import annotations

from typing import Any
from examples.free_multigame_agent import SuperWarDragonFree, _template, _dict, _pokemon_doubles as _v1_doubles

# Static, public pre-match game knowledge. Unknown species remain neutral.
_SPECIES = {
    "gyarados": ("water", "flying"), "garchomp": ("dragon", "ground"),
    "ferrothorn": ("grass", "steel"), "heatran": ("fire", "steel"),
    "amoonguss": ("grass", "poison"), "incineroar": ("fire", "dark"),
    "rillaboom": ("grass",), "urshifurapidstrike": ("fighting", "water"),
    "urshifusinglestrike": ("fighting", "dark"),
    "fluttermane": ("ghost", "fairy"),
    "ironhands": ("fighting", "electric"), "regieleki": ("electric",),
    "landorustherian": ("ground", "flying"), "tornadus": ("flying",),
    "whimsicott": ("grass", "fairy"), "grimmsnarl": ("dark", "fairy"),
    "dialga": ("steel", "dragon"), "palkia": ("water", "dragon"),
    "zacian": ("fairy", "steel"), "zamazenta": ("fighting", "steel"),
    "kyogre": ("water",), "groudon": ("ground",),
    "calyrexshadow": ("psychic", "ghost"), "calyrexice": ("psychic", "ice"),
    "miraidon": ("electric", "dragon"), "koraidon": ("fighting", "dragon"),
    "ogerponwellspring": ("grass", "water"), "ogerponhearthflame": ("grass", "fire"),
    "ogerponcornerstone": ("grass", "rock"), "ogerpon": ("grass",),
    "ursalunabloodmoon": ("ground", "normal"), "ursaluna": ("ground", "normal"),
    "kingambit": ("dark", "steel"), "gholdengo": ("steel", "ghost"),
    "dragonite": ("dragon", "flying"), "archaludon": ("steel", "dragon"),
    "pelipper": ("water", "flying"), "palafin": ("water",),
    "tyranitar": ("rock", "dark"), "excadrill": ("ground", "steel"),
    "torkoal": ("fire",), "venusaur": ("grass", "poison"),
    "charizard": ("fire", "flying"), "blastoise": ("water",),
    "pikachu": ("electric",), "raichu": ("electric",),
    "rotomwash": ("electric", "water"), "rotomheat": ("electric", "fire"),
    "sylveon": ("fairy",), "indeedeef": ("psychic", "normal"),
    "indeedeem": ("psychic", "normal"), "arcanine": ("fire",),
    "hisuianarcanine": ("fire", "rock"), "annihilape": ("fighting", "ghost"),
    "dondozo": ("water",), "tatsugiri": ("dragon", "water"),
    "chienpao": ("dark", "ice"), "tinglu": ("dark", "ground"),
    "wochien": ("dark", "grass"), "chiyu": ("dark", "fire"),
    "metagross": ("steel", "psychic"), "cresselia": ("psychic",),
    "dialgaorigin": ("steel", "dragon"),
}
# attack type => (2x defending types, 0.5x types, 0x types)
_CHART = {
    "normal": ((), ("rock", "steel"), ("ghost",)),
    "fire": (("grass", "ice", "bug", "steel"), ("fire", "water", "rock", "dragon"), ()),
    "water": (("fire", "ground", "rock"), ("water", "grass", "dragon"), ()),
    "electric": (("water", "flying"), ("electric", "grass", "dragon"), ("ground",)),
    "grass": (("water", "ground", "rock"), ("fire", "grass", "poison", "flying", "bug", "dragon", "steel"), ()),
    "ice": (("grass", "ground", "flying", "dragon"), ("fire", "water", "ice", "steel"), ()),
    "fighting": (("normal", "ice", "rock", "dark", "steel"), ("poison", "flying", "psychic", "bug", "fairy"), ("ghost",)),
    "poison": (("grass", "fairy"), ("poison", "ground", "rock", "ghost"), ("steel",)),
    "ground": (("fire", "electric", "poison", "rock", "steel"), ("grass", "bug"), ("flying",)),
    "flying": (("grass", "fighting", "bug"), ("electric", "rock", "steel"), ()),
    "psychic": (("fighting", "poison"), ("psychic", "steel"), ("dark",)),
    "bug": (("grass", "psychic", "dark"), ("fire", "fighting", "poison", "flying", "ghost", "steel", "fairy"), ()),
    "rock": (("fire", "ice", "flying", "bug"), ("fighting", "ground", "steel"), ()),
    "ghost": (("psychic", "ghost"), ("dark",), ("normal",)),
    "dragon": (("dragon",), ("steel",), ("fairy",)),
    "dark": (("psychic", "ghost"), ("fighting", "dark", "fairy"), ()),
    "steel": (("ice", "rock", "fairy"), ("fire", "water", "electric", "steel"), ()),
    "fairy": (("fighting", "dragon", "dark"), ("fire", "poison", "steel"), ()),
}
# Widely used attack moves, for when the platform exposes only move_id.
_MOVE = {
    "thunderbolt": ("electric", 90), "wildcharge": ("electric", 90),
    "voltswitch": ("electric", 70), "electroweb": ("electric", 55),
    "discharge": ("electric", 80), "electrodrift": ("electric", 100),
    "flamethrower": ("fire", 90), "heatwave": ("fire", 95),
    "flareblitz": ("fire", 120), "overheat": ("fire", 130),
    "eruption": ("fire", 150), "fireblast": ("fire", 110),
    "watergun": ("water", 40), "hydropump": ("water", 110),
    "waterspout": ("water", 150), "surgingstrikes": ("water", 25),
    "liquidation": ("water", 85), "muddywater": ("water", 90),
    "earthquake": ("ground", 100), "earthpower": ("ground", 90),
    "stompingtantrum": ("ground", 75), "highhorsepower": ("ground", 95),
    "grassyglide": ("grass", 55), "energyball": ("grass", 90),
    "leafstorm": ("grass", 130), "woodhammer": ("grass", 120),
    "icebeam": ("ice", 90), "icywind": ("ice", 55),
    "blizzard": ("ice", 110), "iciclecrash": ("ice", 85),
    "closecombat": ("fighting", 120), "drainpunch": ("fighting", 75),
    "bodypress": ("fighting", 80), "sacredsword": ("fighting", 90),
    "sludgebomb": ("poison", 90), "poisonjab": ("poison", 80),
    "airslash": ("flying", 75), "bravebird": ("flying", 120),
    "hurricane": ("flying", 110), "bleakwindstorm": ("flying", 100),
    "psychic": ("psychic", 90), "psyshock": ("psychic", 80),
    "expandingforce": ("psychic", 80), "bugbuzz": ("bug", 90),
    "rockslide": ("rock", 75), "stoneedge": ("rock", 100),
    "shadowball": ("ghost", 80), "astralbarrage": ("ghost", 120),
    "dragonclaw": ("dragon", 80), "dracometeor": ("dragon", 130),
    "dragonpulse": ("dragon", 85), "darkpulse": ("dark", 80),
    "knockoff": ("dark", 65), "suckerpunch": ("dark", 70),
    "ironhead": ("steel", 80), "flashcannon": ("steel", 80),
    "makeitrain": ("steel", 120), "moonblast": ("fairy", 95),
    "dazzlinggleam": ("fairy", 80), "playrough": ("fairy", 90),
    "hypervoice": ("normal", 90), "facade": ("normal", 70),
    "tackle": ("normal", 40), "quickattack": ("normal", 40),
    "fakeout": ("normal", 40), "pollenpuff": ("bug", 90),
}
_STATUS = {
    "protect": 18, "detect": 18, "spikyshield": 18,
    "wideguard": 15, "quickguard": 11, "sleeppowder": 54,
    "spore": 64, "thunderwave": 41, "willowisp": 38,
    "tailwind": 46, "trickroom": 35, "icywind": 0,
    "helpinghand": 19, "followme": 18, "ragepowder": 18,
    "recover": 35, "roost": 35, "synthesis": 34,
    "swordsdance": 24, "nastyplot": 24, "calmmind": 23,
    "substitute": 12, "reflect": 26, "lightscreen": 26,
    "taunt": 20, "encore": 20, "haze": 18,
}
_FRIEND_SUPPORT = {"helpinghand", "healpulse", "pollenpuff", "coaching", "floralhealing"}
_SELF_STATUS = {"protect", "detect", "spikyshield", "recover", "roost", "synthesis",
                "swordsdance", "nastyplot", "calmmind", "substitute", "endure"}
_SPREAD_FRIENDLY_DAMAGE = {"earthquake", "surf", "discharge", "boomburst"}


def _norm(value: Any) -> str:
    return "".join(c for c in str(value or "").lower() if c.isalnum())


def type_effect(move_type: str, defending: tuple[str, ...]) -> float:
    weak, resist, immune = _CHART.get(move_type, ((), (), ()))
    factor = 1.0
    for defense in defending:
        if defense in immune:
            return 0.0
        if defense in weak:
            factor *= 2
        if defense in resist:
            factor *= 0.5
    return factor


def _defender_types(descriptor: dict) -> tuple[str, ...]:
    raw = descriptor.get("types")
    if isinstance(raw, list) and raw and all(isinstance(t, str) for t in raw):
        return tuple(t.lower() for t in raw)
    return _SPECIES.get(_norm(descriptor.get("species")), ())


def _move_type_power(option: dict) -> tuple[str, float]:
    name = _norm(option.get("move_id"))
    fallback_type, fallback_power = _MOVE.get(name, ("", 0))
    mt = option.get("move_type", option.get("element", fallback_type))
    mt = str(mt).lower() if isinstance(mt, str) else fallback_type
    power = option.get("base_power", option.get("power", fallback_power))
    if isinstance(power, bool) or not isinstance(power, (float, int)):
        power = fallback_power
    # 0 can be a server-known status move or variable-power move.
    return mt, max(0, min(float(power), 200))


def _target_score(option: dict, target: int, descriptor: dict,
                  our_types: tuple[str, ...]) -> float:
    move_name = _norm(option.get("move_id"))
    side = str(descriptor.get("side", "")).lower()
    if target in (1, 2):
        side = "opponent" if not side else side
    elif target < 0:
        side = "ally" if not side else side
    elif target == 0:
        side = "none" if not side else side

    if side in ("ally", "self"):
        if move_name in _FRIEND_SUPPORT or move_name in _SELF_STATUS:
            return 34 if move_name in _FRIEND_SUPPORT else float(_STATUS.get(move_name, 24))
        return float("-inf")

    if move_name in _STATUS:
        return float(_STATUS[move_name])
    mt, power = _move_type_power(option)
    if power == 0:
        # A move whose damage we cannot determine is not automatically useless.
        power = 55
    efficacy = type_effect(mt, _defender_types(descriptor))
    if efficacy == 0:
        return -30
    accuracy = option.get("accuracy")
    acc = float(accuracy) if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool) else 100
    if acc > 1:
        acc /= 100
    acc = max(0.1, min(1.0, acc))
    # Known same-type attack bonus; otherwise conservative neutrality.
    stab = 1.5 if mt and mt in our_types else 1
    score = power * efficacy * acc * stab
    # Spread moves such as earthquake might also damage an ally.
    if move_name in _SPREAD_FRIENDLY_DAMAGE and target == 0:
        score *= 0.72
    return score


def _pokemon_doubles_v2(state):
    template = _template(state, "doubles_turn")
    slots = template.get("slots")
    if not isinstance(slots, list) or len(slots) != 2:
        return _v1_doubles(state)
    by_slot = {s.get("slot"): s for s in slots if isinstance(s, dict) and type(s.get("slot")) is int}
    if set(by_slot) != {0, 1}:
        return _v1_doubles(state)
    choices = []
    switched = set()
    for number in (0, 1):
        slot = by_slot[number]
        options = slot.get("options")
        if not isinstance(options, list) or not options:
            return _v1_doubles(state)
        active = slot.get("active")
        active = _dict(active)
        our_types = _defender_types(active)
        candidates = []
        for opt in options:
            if not isinstance(opt, dict):
                continue
            if opt.get("type") == "move" and isinstance(opt.get("move_id"), str):
                target_ids = opt.get("targets", [])
                if not isinstance(target_ids, list) or not all(type(t) is int for t in target_ids):
                    continue
                descriptions = {}
                for d in opt.get("target_options", []):
                    if isinstance(d, dict) and type(d.get("target")) is int:
                        descriptions[d["target"]] = d
                if not target_ids:
                    target_ids = [None]
                for target in target_ids:
                    effective_target = 0 if target is None else target
                    descriptor = descriptions.get(effective_target, {})
                    score = _target_score(opt, effective_target, descriptor, our_types)
                    if score == float("-inf"):
                        continue
                    action = {"type": "move", "move_id": opt["move_id"]}
                    if target is not None:
                        action["target"] = target
                    candidates.append((score, action))
            elif opt.get("type") == "switch":
                species = opt.get("species")
                if isinstance(species, str) and species not in switched:
                    candidates.append((7.0, {"type": "switch", "species": species}))
            elif opt.get("type") == "pass":
                candidates.append((-100, {"type": "pass"}))
        if not candidates:
            return _v1_doubles(state)
        # Stable choices on ties, no randomized hidden inputs or network calls.
        best = max(candidates, key=lambda x: x[0])[1]
        if best["type"] == "switch":
            switched.add(best["species"])
        choices.append(best)
    if all(c["type"] == "pass" for c in choices):
        return _v1_doubles(state)
    return {"type": "doubles_turn", "slot_0": choices[0], "slot_1": choices[1]}



class SuperWarDragonV2(SuperWarDragonFree):
    """Same Red Alert/Werewolf decisions; swap Pokémon battle target evaluator."""

    def choose_action(self, state, context):
        game = str(getattr(context, "game_type", "") or "")
        if game == "pokemon_vgc_doubles_draft" and state.legal_actions:
            if state.legal_actions[0].action_id == "doubles_turn":
                return _pokemon_doubles_v2(state)
        return super().choose_action(state, context)



def create_agent():
    return SuperWarDragonV2()
