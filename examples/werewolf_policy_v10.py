"""Seven-seat Werewolf: private-view inference and bounded vote coordination.

No files, network calls, shared seat state, spectator data, or hidden engine
roles are used. Public claims are fallible evidence; only the platform's own
private header and published deaths constrain the enumerated role worlds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import combinations
import math
import re
from typing import Any

from altruagent import SendMessage, TERMINATE_MESSAGING


def _dict(value):
    return value if isinstance(value, dict) else {}


def _seat(value, lookup=None):
    if isinstance(value, dict):
        for name in ("position", "seat", "player", "name"):
            if name in value:
                return _seat(value[name], lookup)
        return None
    if type(value) is int:
        return value if 0 <= value < 7 else None
    if isinstance(value, str):
        match = re.fullmatch(r"(?:Player)?([0-6])", value.strip(), re.I)
        return int(match[1]) if match else (lookup or {}).get(value.strip().casefold())
    return None


def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _proposal(content):
    """Read affirmative first-person proposals, not a vote word in a warning.

    Separate sentences let "Do not vote Player3. Vote Player4." retain the
    positive recommendation. Quoted/third-party and conditional statements
    are deliberately not interpreted as the sender committing a vote.
    """
    result = None
    for clause in re.split(r"[.!?;\n]+", content):
        match = re.match(r"^\s*(?:(?:please|instead|therefore|so|actually)[,:]?\s+)*"
                         r"(?:I propose voting(?: for)?|I (?:will )?vote(?: for)?|"
                         r"(?:My )?vote(?: is| for)?|Voting for)\s*:?\s+Player([0-6])\b", clause, re.I)
        if match and not re.search(r"\b(?:if|unless|maybe|perhaps)\b", clause, re.I):
            result = int(match[1])
    return result


def _message_key(message):
    return (_get(message, "seq", _get(message, "index", None)),
            _get(message, "sender"), tuple(_get(message, "recipients", []) or []),
            _get(message, "content", ""))


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


@dataclass
class View:
    raw: dict
    game: dict
    me: int | None
    role: str
    allies: set[int]
    known: dict[int, str]
    dead: dict[int, str]
    alive: set[int]
    lookup: dict[str, int]
    day: int
    phase: str
    session: str


def view(state, context=None):
    raw = _dict(getattr(state, "raw", None))
    game = _dict(raw.get("game_state"))
    lookup = {f"player{i}": i for i in range(7)}
    for player in raw.get("players", []) or []:
        if not isinstance(player, dict):
            continue
        seat = _seat(player.get("position"))
        if seat is not None:
            for name in ("name", "display_name"):
                if isinstance(player.get(name), str):
                    lookup[player[name].strip().casefold()] = seat
    me = _seat(raw.get("your_position", getattr(context, "seat_position", None)), lookup)
    observation = raw.get("observation", getattr(state, "observation", None))
    obs = _dict(observation)
    text = observation if isinstance(observation, str) else ""
    if text.startswith("=== Werewolf ===\n"):
        header = text.split("\n\n", 1)[0].splitlines()
        match = re.fullmatch(r"Your role: (WOLF|SEER|VILLAGER)", header[1]) if len(header) > 1 else None
        if match:
            obs = {"role": match[1].lower()}
            for line in header[2:]:
                if obs["role"] == "wolf" and line.startswith("Your fellow wolves: "):
                    obs["wolf_teammates"] = [int(x) for x in re.findall(r"\bPlayer([0-6])\b", line)]
                if obs["role"] == "seer" and line.startswith("Your investigations: "):
                    obs["investigations"] = [{"seat": int(n), "role": role.lower()}
                        for n, role in re.findall(r"\bPlayer([0-6]) is (wolf|villager)\b", line, re.I)]
    role = str(obs.get("role", obs.get("your_role", ""))).lower()
    role = "wolf" if role == "werewolf" else role
    allies, known = set(), {}
    if role == "wolf":
        for key in ("wolf_teammates", "wolf_allies", "wolf_teammate", "wolf_ally", "teammate"):
            val = obs.get(key, [])
            vals = list(val.values()) if isinstance(val, dict) else val if isinstance(val, (list, tuple)) else [val]
            allies.update(n for item in vals if (n := _seat(item, lookup)) is not None and n != me)
    if role == "seer":
        for key in ("investigations", "seer_results", "checks", "results"):
            records = obs.get(key, [])
            if isinstance(records, dict):
                records = [{"player": k, "role": v} for k, v in records.items()]
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                n = _seat(record.get("seat", record.get("position", record.get("player", record.get("name")))), lookup)
                found = str(record.get("role", record.get("result", ""))).lower()
                if n is not None and found in ("wolf", "werewolf", "villager", "seer"):
                    known[n] = "wolf" if found == "werewolf" else found
    dead = {}
    records = game.get("dead", [])
    if isinstance(records, dict):
        records = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "role": v} for k, v in records.items()]
    for record in records if isinstance(records, list) else []:
        n = _seat(record, lookup)
        found = str(_get(record, "role", "")).lower()
        if n is not None and found in ("wolf", "werewolf", "villager", "seer"):
            dead[n] = "wolf" if found == "werewolf" else found
    alive = set()
    for item in game.get("alive", []) if isinstance(game.get("alive"), list) else []:
        if (n := _seat(item, lookup)) is not None:
            alive.add(n)
    if not alive and text.startswith("=== Werewolf ===\n"):
        match = re.search(r"^Living: ([^\n]+)$", text, re.M)
        if match:
            alive = {int(n) for n in re.findall(r"\bPlayer([0-6])\b", match[1])}
    alive = (alive or set(range(7))) - set(dead)
    history = game.get("vote_history", [])
    fallback_day = len(history) + 1 if isinstance(history, list) else 1
    try:
        day = int(game.get("day", fallback_day))
    except (TypeError, ValueError):
        day = fallback_day
    session = str(raw.get("session_id", getattr(context, "session_id", "local")))
    return View(raw, game, me, role, allies, known, dead, alive, lookup, day, str(game.get("phase", "")), session)


@dataclass
class Claim:
    checks: dict[int, str] = field(default_factory=dict)
    contradictions: int = 0


class WerewolfPolicyV10:
    def __init__(self):
        self._identity = None
        self._seen = set()
        self._claims: dict[int, Claim] = {}
        self._proposals: dict[int, tuple[int, int]] = {}
        self._wolf_plans: dict[int, tuple[int, int, int]] = {}
        self._sent: dict[int, set[str]] = {}
        self._last_target: dict[int, int] = {}
        self._bluff_targets: dict[int, int] = {}
        self._closed: set[int] = set()
        self._quota_observed: dict[int, set[tuple]] = {}
        self._quota_pending: dict[int, list[tuple]] = {}
        self._quota_message_days: dict[tuple, int] = {}

    def _restore_quota(self, state, v):
        """Count only our own chats in this discussion, including after restart.

        The official SDK's get_state new_messages covers the current phase,
        not a full transcript (altruagent/mcp_game.py). Where timestamps and
        the Werewolf 120-second deadline are present, also reject stale phases.
        Never inspect files or another seat's private transcript to recover it.
        """
        observed = self._quota_observed.setdefault(v.day, set())
        pending = self._quota_pending.setdefault(v.day, [])
        deadline = _timestamp(v.raw.get("messaging_deadline"))
        messages = list(getattr(state, "new_messages", []) or [])
        messages.extend(v.raw.get("new_messages", []) or [])
        for message in messages:
            if _get(message, "type", "chat") != "chat" or _seat(_get(message, "sender"), v.lookup) != v.me:
                continue
            content = _get(message, "content", "")
            recipients = _get(message, "recipients", []) or []
            if not isinstance(content, str) or not isinstance(recipients, (list, tuple)):
                continue
            key = _message_key(message)
            previous_day = self._quota_message_days.get(key)
            if previous_day is not None and previous_day != v.day:
                continue
            sent_at = _timestamp(_get(message, "sent_at"))
            if deadline is not None and sent_at is not None and not deadline - timedelta(seconds=120) <= sent_at <= deadline:
                continue
            self._quota_message_days[key] = v.day
            if key in observed:
                continue
            observed.add(key)
            fingerprint = (content, tuple(recipients))
            # A server echo acknowledges one locally proposed send. Counting
            # both would prematurely consume two slots for the same message.
            if fingerprint in pending:
                pending.remove(fingerprint)
        return len(observed) + len(pending)

    def _message(self, v, content, recipients=None):
        recipients = list(recipients or [])
        self._quota_pending.setdefault(v.day, []).append((content, tuple(recipients)))
        return SendMessage(content, recipients=recipients)

    def _read(self, state, context=None):
        v = view(state, context)
        identity = (v.session, v.me)
        if self._identity != identity:
            self.__init__()
            self._identity = identity
        messages = list(getattr(state, "new_messages", []) or [])
        messages.extend(v.raw.get("new_messages", []) or [])
        for message in messages:
            if _get(message, "type", "chat") != "chat":
                continue
            sender = _seat(_get(message, "sender"), v.lookup)
            content = _get(message, "content", "")
            recipients = _get(message, "recipients", []) or []
            if sender is None or not isinstance(content, str) or len(content) > 5000:
                continue
            key = (_get(message, "seq", _get(message, "index", None)), sender, tuple(recipients), content)
            if key in self._seen:
                continue
            self._seen.add(key)
            if recipients:
                # Private chat is never a platform role assignment. Only our
                # privately known wolf teammate may send a coordination plan.
                if v.role == "wolf" and sender in v.allies and recipients == [v.me]:
                    match = re.fullmatch(r"Wolf coordination: vote Player([0-6]) today\. Night target Player([0-6])\.", content)
                    if match and int(match[1]) not in v.allies | {v.me} and int(match[2]) not in v.allies | {v.me}:
                        self._wolf_plans[sender] = (v.day, int(match[1]), int(match[2]))
                continue
            # Claims are attributed to authenticated message.sender. Quoted
            # headers, someone else's role, and imperative instructions cannot
            # become private knowledge. Natural-language claims remain soft.
            claiming = bool(re.match(r"^\s*I (?:am|'m) (?:the |a )?seer\b", content, re.I))
            if claiming:
                self._claims.setdefault(sender, Claim())
            if sender in self._claims and (claiming or re.match(r"^\s*(?:My (?:investigation|checks)|Checks:|I (?:checked|investigated))", content, re.I)):
                if re.search(r"\b(?:checks|investigation|checked|investigated)\b", content, re.I):
                    checks = re.findall(r"\bPlayer([0-6])\s*(?:=|:|is|was)\s*(?:a\s+)?(wolf|villager|innocent)\b", content, re.I)
                    claim = self._claims[sender]
                    for seat, found in checks:
                        n, found = int(seat), "wolf" if found.lower() == "wolf" else "villager"
                        if n in claim.checks and claim.checks[n] != found:
                            claim.contradictions += 1
                        claim.checks[n] = found
            target = _proposal(content)
            if target is not None:
                if sender in v.alive and target in v.alive and target != sender:
                    self._proposals[sender] = (v.day, target)
        return v

    @staticmethod
    def _rank(v, target):
        # Everyone sees the same session/day. No permanent seat bias and no
        # per-seat cyclic fallback that systematically creates tied votes.
        return int.from_bytes(sha256(f"{v.session}:{v.day}:{target}".encode()).digest()[:8], "big")

    def _worlds(self, v):
        worlds = []
        history = v.game.get("vote_history", [])
        for pair in combinations(range(7), 2):
            wolves = set(pair)
            if v.role == "wolf" and (v.me not in wolves or not v.allies <= wolves):
                continue
            if v.role in ("seer", "villager") and v.me in wolves:
                continue
            if any((n in wolves) != (role == "wolf") for n, role in {**v.dead, **v.known}.items()):
                continue
            for seer in set(range(7)) - wolves:
                if v.role == "seer" and seer != v.me or v.role == "villager" and seer == v.me:
                    continue
                if any((n == seer) != (role == "seer") for n, role in v.dead.items() if role != "wolf"):
                    continue
                # A lone coherent claim is useful but rebuttable. A living
                # seer often answers a competing claim; silence is only a
                # modest likelihood adjustment, never proof of alignment.
                log_weight = math.log(.2) if self._claims and seer not in self._claims and seer in v.alive else 0.0
                for claimant, claim in self._claims.items():
                    if claimant == seer:
                        log_weight += math.log(.94) + claim.contradictions * math.log(.01)
                        for target, found in claim.checks.items():
                            correct = (target in wolves) == (found == "wolf") and target != claimant
                            log_weight += math.log(.99 if correct else .002)
                    elif claimant in wolves:
                        # Bluffing is a normal game action, never a hard role.
                        log_weight += math.log(.28)
                    else:
                        log_weight += math.log(.005)
                # Completed ballots are weak behavioral evidence, not proof.
                for day in history if isinstance(history, list) else []:
                    ballots = _get(day, "votes", _get(day, "ballots", []))
                    pairs = ballots.items() if isinstance(ballots, dict) else [(_get(b, "voter", _get(b, "from")), _get(b, "target", _get(b, "to"))) for b in ballots] if isinstance(ballots, list) else []
                    for voter, target in pairs:
                        voter, target = _seat(voter, v.lookup), _seat(target, v.lookup)
                        if voter in wolves and target in v.dead:
                            log_weight += math.log(.55 if v.dead[target] == "wolf" else 1.1)
                worlds.append((wolves, seer, log_weight))
        return worlds

    def _beliefs(self, v):
        worlds = self._worlds(v)
        wolf = {n: 0.0 for n in range(7)}
        seer = dict(wolf)
        if not worlds:
            # Defensive fallback for incomplete/inconsistent upstream schemas.
            eligible = v.alive - {v.me} - {n for n, r in v.known.items() if r != "wolf"}
            return ({n: (1.0 if v.known.get(n) == "wolf" else 2 / max(2, len(eligible)) if n in eligible else 0.0) for n in range(7)}, seer)
        maximum = max(w[2] for w in worlds)
        weights = [math.exp(w[2] - maximum) for w in worlds]
        total = sum(weights)
        for (wolves, seer_id, _), weight in zip(worlds, weights):
            for n in wolves:
                wolf[n] += weight / total
            seer[seer_id] += weight / total
        return wolf, seer

    def _night_target(self, v, targets):
        wolf, seer = self._beliefs(v)
        return max(targets, key=lambda n: (seer[n], sum(1 for c in self._claims.values() if c.checks.get(n) == "villager"), -n))

    @staticmethod
    def _quiet_table_target(v, targets, investigate=False):
        """Preserve the tested V8 fallback when nobody supplies a usable claim.

        Changing an arbitrary no-information tie-break alone provides no
        evidence of competitive improvement. Public chat overrides this path.
        """
        scores = {n: 0.0 for n in targets}
        history = v.game.get("vote_history", [])
        for day in history if isinstance(history, list) else []:
            ballots = _get(day, "votes", _get(day, "ballots", []))
            pairs = ballots.items() if isinstance(ballots, dict) else [(_get(b, "voter", _get(b, "from")), _get(b, "target", _get(b, "to"))) for b in ballots] if isinstance(ballots, list) else []
            for voter, target in pairs:
                voter, target = _seat(voter, v.lookup), _seat(target, v.lookup)
                if voter in scores and target in v.dead:
                    scores[voter] += -3.0 if v.dead[target] == "wolf" else 1.0
        if investigate or any(abs(s) > 1e-6 for s in scores.values()):
            return max(targets, key=lambda n: (scores[n], -n))
        ordered = sorted(targets)
        completed_days = len(history) if isinstance(history, list) else 0
        return ordered[((v.me or 0) + completed_days) % len(ordered)]

    def _quiet_table(self, v):
        return not any(n != v.me for n in self._claims) and not any(
            who != v.me and who in v.alive and day == v.day
            for who, (day, target) in self._proposals.items())

    def _vote_target(self, v, targets):
        if not targets:
            return None
        wolf, seer = self._beliefs(v)
        if v.role == "wolf":
            safe = set(targets) - v.allies - {v.me}
            if not safe:
                return None
            # A living lower-seat wolf leads. Publicly updated targets and our
            # already announced counterclaim supersede an initial private plan;
            # otherwise an obsolete opening message splits the wolf pair.
            leaders = sorted(n for n in v.allies & v.alive if n < (v.me if v.me is not None else 7))
            for ally in leaders:
                proposal = self._proposals.get(ally)
                if proposal and proposal[0] == v.day and proposal[1] in safe:
                    return proposal[1]
            if self._bluff_targets.get(v.day) in safe:
                return self._bluff_targets[v.day]
            for ally in leaders:
                plan = self._wolf_plans.get(ally)
                if plan and plan[0] == v.day and plan[1] in safe:
                    return plan[1]
            if self._quiet_table(v):
                return self._quiet_table_target(v, safe)
            support = {n: sum(1 for who, (day, target) in self._proposals.items()
                              if day == v.day and target == n and who not in v.allies | {v.me}) for n in safe}
            return max(safe, key=lambda n: (support[n], seer[n], self._rank(v, n)))
        confirmed = set(targets) & {n for n, role in v.known.items() if role == "wolf"}
        if confirmed:
            return max(confirmed, key=lambda n: self._rank(v, n))
        eligible = set(targets) - {n for n, role in v.known.items() if role != "wolf"}
        if not eligible:
            return None
        if self._quiet_table(v):
            return self._quiet_table_target(v, eligible)
        maximum = max(wolf[n] for n in eligible)
        # Coordinate among similarly plausible suspects. A majority of mere
        # proposals cannot outweigh a strong check or clear an accused wolf.
        plausible = {n for n in eligible if wolf[n] >= maximum - .12}
        support = {n: sum((1 - wolf[who]) * (1.8 if who in self._claims else 1.0)
                          for who, (day, target) in self._proposals.items()
                          if who in v.alive and who != v.me and day == v.day and target == n) for n in plausible}
        return max(plausible, key=lambda n: (wolf[n] + min(.16, .075 * support[n]), self._rank(v, n)))

    def choose_action(self, state, context=None):
        v = self._read(state, context)
        actions = getattr(state, "legal_actions", []) or []
        legal = {_seat(a.action_id): a for a in actions if _seat(a.action_id) is not None}
        abstain = next((a for a in actions if str(a.action_id) == "7"), None)
        targets = set(legal) & v.alive - {v.me}
        if v.role == "wolf":
            targets -= v.allies
        if not targets:
            return abstain or (actions[0] if actions else None)
        if v.phase == "night_wolf":
            target = self._night_target(v, targets)
            _, seer = self._beliefs(v)
            for ally in sorted(v.allies & v.alive):
                plan = self._wolf_plans.get(ally)
                # Day N's discussion can coordinate night N+1 only. A dead
                # teammate's plan, or one contradicted by stronger current
                # seer evidence, must not override the surviving wolf's view.
                if (plan and plan[0] == v.day - 1 and ally < (v.me if v.me is not None else 7)
                        and plan[2] in targets and seer[plan[2]] >= seer[target] - 1e-9):
                    target = plan[2]
                    break
        elif v.phase == "night_seer":
            novel = targets - set(v.known)
            wolf, _ = self._beliefs(v)
            # Confirm a counterclaim first; otherwise maximize information.
            target = (self._quiet_table_target(v, novel or targets, investigate=True) if self._quiet_table(v) else
                      max(novel or targets, key=lambda n: (n in self._claims, 4 * wolf[n] * (1 - wolf[n]), self._rank(v, n))))
        else:
            target = self._vote_target(v, targets)
        return legal[target] if target in legal else abstain or legal[max(targets, key=lambda n: self._rank(v, n))]

    def choose_message(self, state, context=None):
        v = self._read(state, context)
        terminated = v.raw.get("terminated_messaging", getattr(state, "terminated_messaging", [])) or []
        if v.raw.get("eliminated") or v.me not in v.alive or v.day in self._closed or v.me in terminated:
            return TERMINATE_MESSAGING
        if self._restore_quota(state, v) >= 5:
            self._closed.add(v.day)
            return TERMINATE_MESSAGING
        sent = self._sent.setdefault(v.day, set())
        if len(sent) >= 4:
            self._closed.add(v.day)
            return TERMINATE_MESSAGING
        targets = v.alive - {v.me}
        if v.role == "wolf":
            targets -= v.allies
        target = self._vote_target(v, targets)
        if target is None:
            self._closed.add(v.day)
            return TERMINATE_MESSAGING
        message = None
        if v.role == "seer" and "seer" not in sent:
            # Seven players allow at most two early mislynches. Publishing the
            # first check narrows day-one candidates and survives our death.
            checks = "; ".join(f"Player{n} is {role.upper()}" for n, role in sorted(v.known.items()))
            message = f"I am the seer. My checks: {checks or 'none yet'}. I propose voting Player{target}. Keep these results after my death."
            sent.add("seer")
        elif v.role == "wolf" and "bluff" not in sent and not any(r == "seer" for r in v.dead.values()):
            threats = [n for n, claim in self._claims.items() if n in targets and any(claim.checks.get(w) == "wolf" for w in v.allies | {v.me})]
            if threats:
                target = max(threats, key=lambda n: self._rank(v, n))
                message = f"I am the seer. My investigation found Player{target} is a wolf. I propose voting Player{target}. The other seer claim is a wolf bluff."
                sent.add("bluff")
                self._bluff_targets[v.day] = target
        if message is None and v.role == "wolf" and "private" not in sent and v.allies & v.alive:
            ally = min(v.allies & v.alive)
            night = self._night_target(v, targets)
            sent.add("private")
            return self._message(v, f"Wolf coordination: vote Player{target} today. Night target Player{night}.", recipients=[ally])
        if message is None and ("proposal" not in sent or self._last_target.get(v.day) != target and "revision" not in sent):
            label = "proposal" if "proposal" not in sent else "revision"
            sent.add(label)
            message = f"I propose voting Player{target}. Seer claims must include exact checks. Compare them with revealed roles; consolidate on one living suspect so a split vote does not protect wolves."
        if message is None:
            self._closed.add(v.day)
            return TERMINATE_MESSAGING
        self._last_target[v.day] = target
        # SDK max is 50 whitespace-delimited words; keep every message below it.
        assert len(message.split()) <= 50
        return self._message(v, message)

