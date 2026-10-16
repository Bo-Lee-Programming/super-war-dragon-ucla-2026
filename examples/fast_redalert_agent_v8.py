"""Super War Dragon V8: deterministic, player-view Red Alert controller.

This is a LOCAL SELF-HOSTED CANDIDATE. It is NOT the deployed AWS Markdown.
Its action scheduler has explicit economy, building, production, defense and
attack phases. Never reads spectator views, opponent-private state or external
game logs. It consumes only the seat's game observation and legal hints.

The official runtime serializes play_action; this policy produces a bounded
batch in milliseconds and accepts feedback through on_action_result.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from altruagent import WAIT, WithReasoning

FALLBACK_COST = {
    "powr": 300, "proc": 1400, "tent": 500, "tenf": 500,
    "barr": 500, "weap": 2000, "fix": 1200,
    "harv": 1100, "e1": 100, "e2": 160, "e3": 250,
    "1tnk": 700, "2tnk": 900, "3tnk": 1100,
    "apc": 850, "jeep": 500, "ftrk": 600,
}
NONCOMBAT = {"harv", "harvester", "miner", "mcv", "medi", "mechanic", "engineer", "e6", "truk"}
CONSTRUCTION = {"fact", "powr", "proc", "tent", "tenf", "barr", "weap", "fix"}
EXCLUDED_BUILD = {"fenc", "brik", "silo", "spen", "syrd", "hpad", "afld"}


def d(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def rows(value: Any) -> list[dict]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def names(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(x).casefold() for x in value if isinstance(x, str)}


def actor_type(actor: dict) -> str:
    return str(actor.get("type", "")).casefold()


def actor_id(actor: dict) -> int | None:
    n = actor.get("id")
    return n if type(n) is int and n >= 0 else None


def int0(value: Any, default: int = 0) -> int:
    return int(value) if isinstance(value, (float, int)) and not isinstance(value, bool) else default


class FastRedAlertV8:
    """A single match's memory; official starter creates an independent instance for each seat."""

    def __init__(self):
        self.cooldowns: dict[str, int] = {}
        self.last_tick = -1
        self.last_trace = ""
        self.metrics = Counter()
        self.last_military = {}
        self.last_economy = {}
        self.last_building_count = 0
        self.last_orders: list[dict] = []

    def _ready(self, label: str, tick: int, every: int) -> bool:
        prev = self.cooldowns.get(label)
        return prev is None or tick < prev or tick - prev >= every

    def _mark(self, label: str, tick: int) -> None:
        self.cooldowns[label] = tick

    def _cost(self, name: str, context) -> int:
        # The game config is authoritative if the official SDK exposed actor metadata.
        config = d(getattr(context, "game_config", None))
        rules = d(config.get("rules"))
        actors = d(rules.get("actors", rules.get("units", {})))
        info = d(actors.get(name, {}))
        if info.get("cost") is not None:
            return int0(info["cost"], FALLBACK_COST.get(name, 1000))
        return FALLBACK_COST.get(name, 1000)

    def _send(self, orders: list[dict], reason: str):
        if not orders:
            return WAIT
        safe = [x for x in orders[:20] if isinstance(x, dict) and x.get("cmd")]
        if not safe:
            return WAIT
        # No more than 200 expanded unit-commands, 50 units per order.
        commands = 0
        output = []
        for o in safe:
            qty = len(o.get("units", [])) if isinstance(o.get("units"), list) else 1
            qty = max(1, qty)
            if commands + qty > 195:
                continue
            commands += qty
            output.append(o)
        if not output:
            return WAIT
        self.last_orders = output
        self.last_trace = reason
        self.metrics["batches"] += 1
        self.metrics["orders"] += len(output)
        return WithReasoning({"type": "orders", "orders": output}, reason[:190])

    def choose_action(self, state, context):
        if str(getattr(context, "game_type", "")) != "red_alert":
            return WAIT
        raw = d(getattr(state, "raw", None))
        obs = d(raw.get("observation"))
        if not obs or raw.get("phase") not in ("playing", None):
            return WAIT

        tick = int0(obs.get("tick"), int0(raw.get("state_version"), 0))
        if tick < self.last_tick:
            self.cooldowns.clear()
        self.last_tick = tick

        legal = d(raw.get("legal_actions"))
        if not legal and getattr(state, "legal_actions", []):
            legal = d(getattr(state, "legal_actions", []))
        building_options = names(legal.get("build"))
        train_options = names(legal.get("train"))
        place_options = names(legal.get("place"))
        deploy_ids = legal.get("deploy")
        own_units = [u for u in rows(obs.get("units")) if actor_id(u) is not None and not u.get("wreck")]
        buildings = [b for b in rows(obs.get("buildings")) if actor_id(b) is not None]
        queues = rows(obs.get("production"))
        queued = Counter(actor_type({"type": x.get("item")}) for x in queues)
        built = Counter(actor_type(b) for b in buildings)
        unit_counts = Counter(actor_type(u) for u in own_units)
        econ = d(obs.get("economy"))
        cash = int0(econ.get("cash"))
        ore = int0(econ.get("ore"))
        provided = int0(econ.get("power_provided"))
        drained = int0(econ.get("power_drained"))
        harvesters = [u for u in own_units if actor_type(u) in {"harv", "harvester", "miner"}]
        army = [u for u in own_units if actor_type(u) not in NONCOMBAT]
        idle = [u for u in army if u.get("idle") is True or
                str(u.get("act", "")).casefold() in ("idle", "none", "")]
        enemy = [e for e in rows(obs.get("visible_enemies")) if not e.get("wreck")]
        enemy_buildings = [e for e in rows(obs.get("visible_enemy_buildings")) if not e.get("wreck")]
        bounds = d(raw.get("map"))
        legal_bounds = bounds.get("bounds", [0, 0, 96, 96])
        def in_bounds(point):
            return (isinstance(point, (list, tuple)) and len(point) == 2
                    and all(type(v) is int for v in point)
                    and isinstance(legal_bounds, (list, tuple)) and len(legal_bounds) == 4
                    and legal_bounds[0] <= point[0] < legal_bounds[0]+legal_bounds[2]
                    and legal_bounds[1] <= point[1] < legal_bounds[1]+legal_bounds[3])

        # Architecture: each subsystem proposes orders; a single scheduler
        # arbitrates resource use, production queues and troop ownership.
        candidates: list[dict] = []
        consumed_unit_ids: set[int] = set()
        notes = []
        cash_budget = cash + ore
        used_building_queue = False
        used_infantry_queue = False
        used_vehicle_queue = False

        def propose(order: dict, *, tag: str, interval: int, cost: int = 0,
                    queue: str = "", note: str = "") -> bool:
            nonlocal cash_budget, used_building_queue, used_infantry_queue, used_vehicle_queue
            if not self._ready(tag, tick, interval):
                return False
            if cash_budget < cost:
                return False
            if queue == "building" and used_building_queue:
                return False
            if queue == "infantry" and used_infantry_queue:
                return False
            if queue == "vehicle" and used_vehicle_queue:
                return False
            if len(candidates) >= 12:
                return False
            ids = order.get("units", [])
            if ids:
                if not isinstance(ids, list):
                    return False
                ids = [n for n in ids if type(n) is int and n not in consumed_unit_ids][:50]
                if not ids:
                    return False
                order = {**order, "units": ids}
                consumed_unit_ids.update(ids)
            candidates.append(order)
            self._mark(tag, tick)
            cash_budget -= cost
            if queue == "building": used_building_queue = True
            if queue == "infantry": used_infantry_queue = True
            if queue == "vehicle": used_vehicle_queue = True
            if note: notes.append(note)
            return True

        # A deployed MCV changes ID: never reuse the old unit ID.
        if not built["fact"]:
            mcvs = [actor_id(u) for u in own_units if actor_type(u) == "mcv"]
            allowed = (set(deploy_ids) if isinstance(deploy_ids, list) else set())
            mcvs = [x for x in mcvs if not allowed or x in allowed]
            if mcvs:
                propose({"cmd": "deploy", "units": [mcvs[0]]},
                        tag="deploy", interval=35, note="deploy MCV")
                return self._send(candidates, "; ".join(notes))
            # Losing the construction yard must not disable surviving factories,
            # harvesters or defenders. Continue controlling the remaining assets.

        # Highest priority: completed buildings are useless until PLACED.
        for x in queues:
            item = str(x.get("item", "")).casefold()
            queue_kind = str(x.get("queue", "")).casefold()
            can_place = (item in place_options if "place" in legal else
                         queue_kind in ("building", "defense"))
            if x.get("ready") is True and item and can_place:
                propose({"cmd": "place", "item": item},
                        tag="place:"+item, interval=30, note="place "+item)
                break

        # If a harvester becomes idle, restart mining. Do not send miners to fight.
        idle_harvesters = [actor_id(u) for u in harvesters if
                           u.get("idle") is True or
                           str(u.get("act", "")).casefold() in ("idle", "none", "")]
        if idle_harvesters:
            propose({"cmd": "harvest", "units": idle_harvesters[:8]},
                    tag="harvest", interval=100, note="recover mining")

        # Local threat response: guard important nearby assets; use ONLY visible targets.
        center = obs.get("base_center")
        if not in_bounds(center) and buildings:
            center = [int0(buildings[0].get("x")), int0(buildings[0].get("y"))]
        threats = []
        if in_bounds(center):
            for e in enemy + enemy_buildings:
                p = [e.get("x"), e.get("y")]
                if in_bounds(p):
                    dist = abs(p[0]-center[0]) + abs(p[1]-center[1])
                    if dist <= 21:
                        threats.append((dist, p, e))
        if threats and army:
            threats.sort(key=lambda x:x[0])
            t = threats[0]
            # Defensive troops must not simultaneously be assigned an offensive order.
            defense_ids = [actor_id(u) for u in army[:50] if actor_id(u) is not None]
            propose({"cmd": "attack_move", "units": defense_ids, "to": t[1]},
                    tag="defend", interval=40, note="defend visible base threat")

        # Critical base repairs use official own-building IDs and legal hints.
        repairable = legal.get("repair", [])
        repair_ids = set()
        if isinstance(repairable, list):
            for r in repairable:
                if type(r) is int: repair_ids.add(r)
                elif isinstance(r, dict) and type(r.get("id")) is int: repair_ids.add(r["id"])
        for b in buildings:
            ident = actor_id(b)
            hp = int0(b.get("hp"), 100)
            if (ident is not None and hp < 55 and not b.get("repairing")
                    and cash_budget >= 350 and (not repair_ids or ident in repair_ids)):
                if propose({"cmd":"repair", "building":ident, "on":True},
                           tag="repair:"+str(ident),interval=150,
                           note="repair critical building"):
                    break

        # A *single* building queue, with a strict priority order and no duplicate.
        # Never queue walls / naval buildings on these land-focused maps.
        desired = []
        if built["powr"] + queued["powr"] == 0:
            desired.append("powr")
        # Build economy and a working barracks before expensive options.
        if sum(built[x]+queued[x] for x in ("tent","tenf","barr")) == 0:
            desired.extend(("tent", "barr"))
        if built["proc"]+queued["proc"] == 0:
            desired.append("proc")
        # Avoid both electric overload and unnecessary power spam.
        if provided > 0 and drained + 35 >= provided and queued["powr"] == 0:
            desired.append("powr")
        if built["proc"] >= 1 and built["weap"] + queued["weap"] == 0:
            desired.append("weap")
        # Expand income BEFORE tech. The previous live agent starved the mine
        # economy by buying endless infantry after it built a factory.
        if built["proc"] >= 1 and built["proc"] + queued["proc"] < 2 and cash + ore >= 1900:
            desired.append("proc")
        if built["weap"] >= 1 and built["fix"] + queued["fix"] == 0 and cash + ore >= 1900:
            desired.append("fix")
        if (built["proc"] >= 2 and built["weap"] >= 1 and cash + ore >= 4800
                and built["weap"] + queued["weap"] < 2):
            desired.append("weap")
        # A replacement miner takes precedence over optional expansion/tech.
        miner_cost = self._cost("harv", context)
        miner_missing = not harvesters and not queued["harv"]
        refinery_incoming = bool(queued["proc"])
        if (miner_missing and not refinery_incoming and built["weap"]
                and "harv" in train_options and not any(
                    str(q.get("queue", "")).casefold() == "vehicle" for q in queues)):
            propose({"cmd": "train", "item": "harv", "count": 1},
                    tag="vehicle-harv", interval=80, cost=miner_cost,
                    queue="vehicle", note="restore sole income source")
        for item in desired:
            if miner_missing and not refinery_incoming and item not in ("proc", "powr"):
                continue
            if item in EXCLUDED_BUILD or item not in building_options or queued[item]:
                continue
            # If the Building queue is occupied, don't add many duplicate future structures.
            if any(str(q.get("queue", "")).casefold() in ("building","defense")
                   for q in queues):
                break
            cost = self._cost(item, context)
            if propose({"cmd": "build", "item": item},
                       tag="build:"+item, interval=70,
                       cost=cost, queue="building", note="build "+item):
                break

        # Expand harvesting when possible; it raises long-run production capacity.
        vehicle_q = [q for q in queues if str(q.get("queue", "")).casefold() == "vehicle"]
        infantry_q = [q for q in queues if str(q.get("queue", "")).casefold() == "infantry"]
        # Reserve cash for a first harvester only if affordable; don't drain urgent economy.
        harv_count = len(harvesters) + sum(1 for x in vehicle_q if str(x.get("item", "")).casefold()=="harv")
        if (built["weap"] >= 1 and "harv" in train_options and harv_count < 2
                and len(vehicle_q) < 2 and cash_budget >= self._cost("harv", context)+250):
            propose({"cmd": "train", "item": "harv", "count": 1},
                    tag="vehicle-harv", interval=80,
                    cost=self._cost("harv", context),queue="vehicle",note="restore/expand harvesters")

        # Visible opponent composition biases combat production.
        visible_types = Counter(actor_type(e) for e in enemy)
        has_vehicle_enemy = any("tnk" in t or t in {"apc","harv","jeep","ftrk"} for t in visible_types)
        want_infantry = "e3" if has_vehicle_enemy and "e3" in train_options else (
            "e1" if "e1" in train_options else ("e3" if "e3" in train_options else ""))
        reserved = 250 if (built["proc"] > 0 and harvesters) else 0
        # The failed live match spent every new credit on riflemen and NEVER
        # accumulated enough for a second refinery or harvester. Enforce an
        # investment savings floor until the economic backbone is healthy.
        economy_incomplete = (built["weap"] >= 1 and
                              (built["proc"] + queued["proc"] < 2 or harv_count < 2))
        if economy_incomplete and not threats:
            reserved = max(reserved, 1650)
        # Protect the opening refinery/factory savings as well as expansion.
        if not threats:
            if not built["proc"] and not queued["proc"]:
                reserved = max(reserved, self._cost("proc", context))
            elif built["proc"] and not built["weap"] and not queued["weap"]:
                reserved = max(reserved, self._cost("weap", context))
        if (want_infantry and built["barr"]+built["tent"]+built["tenf"] > 0
                and len(infantry_q) <= 2 and cash_budget >= self._cost(want_infantry, context)+reserved):
            count = min(3, max(1, (cash_budget-reserved)//max(1,self._cost(want_infantry, context))))
            count = min(count, max(1, 4-len(infantry_q)))
            propose({"cmd": "train", "item": want_infantry, "count": count},
                    tag="train-inf", interval=65,
                    cost=count*self._cost(want_infantry,context),
                    queue="infantry",note="train "+want_infantry+" x"+str(count))

        # Train appropriate vehicles when cash remains, after ensuring mining health.
        if built["weap"] > 0 and len(vehicle_q) < 2 and cash_budget >= 950:
            candidates_tanks = (
                ("3tnk","2tnk","apc","ftrk") if "russia" in str(obs.get("faction","")).lower()
                else ("2tnk","3tnk","1tnk","apc","jeep","ftrk"))
            vehicle = next((x for x in candidates_tanks if
                            x in train_options and cash_budget >= self._cost(x,context)+max(150,reserved)),"")
            if vehicle:
                propose({"cmd":"train","item":vehicle,"count":1},tag="train-vehicle",
                        interval=80,cost=self._cost(vehicle,context),
                        queue="vehicle",note="train "+vehicle)

        # Battle objective: do not sacrifice one rifleman at a time to the enemy spawn.
        # Only attack with sufficient *idle* army, keep a defensive reserve.
        if not threats and len(army) >= 12 and len(idle) >= 8 and built["proc"] >= 1:
            attack_cell = None
            if enemy_buildings:
                visible_buildings = [e for e in enemy_buildings if in_bounds([e.get("x"),e.get("y")])]
                if visible_buildings:
                    target = min(visible_buildings,
                                 key=lambda e: 0 if actor_type(e) in ("proc","weap","fact","powr") else 1)
                    attack_cell = [target["x"],target["y"]]
            if attack_cell is None:
                legal_base=legal.get("enemy_base")
                if in_bounds(legal_base): attack_cell=list(legal_base)
            if attack_cell:
                assault_ids = [actor_id(u) for u in idle[:50] if actor_id(u) not in consumed_unit_ids]
                reserve = max(3, len(army)//5)
                if len(assault_ids) > reserve+3:
                    propose({"cmd":"attack_move","units":assault_ids[:-reserve],
                             "to":attack_cell},
                            tag="main-assault",interval=180,
                            note="launch cohesive assault; keep reserve")

        # Detect economic collapse, keep a breadcrumb for deterministic diagnostics.
        self.last_economy = {"cash":cash,"ore":ore,"harvesters":len(harvesters),
                             "power_margin":provided-drained}
        self.last_military = {"army":len(army),"visible_enemies":len(enemy)}
        self.last_building_count = len(buildings)
        if cash + ore < 200 and not harvesters:
            self.metrics["economy_red_alert"] += 1
        if not candidates:
            self.metrics["waits"] += 1
        return self._send(candidates,"; ".join(notes) or "waiting for actionable state")

    def on_action_result(self,result,context):
        info=d(result)
        if info.get("accepted") is False:
            self.metrics["batch_refused"] += 1
        for row in rows(info.get("results")):
            if row.get("status") in ("rejected","lost","partial"):
                self.metrics["order_problem"] += 1


def create_agent():
    return FastRedAlertV8()
