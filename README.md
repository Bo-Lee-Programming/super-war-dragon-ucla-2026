# Super War Dragon V10.3

Self-hosted Python agent for Werewolf, Red Alert, and Pokemon VGC Doubles Draft
on the UCLA AltruAgent platform. Development used AI assistance.

## Setup and testing

Requires Python 3.11 or newer. From this repository root:

```sh
python -m venv .venv
# Activate the environment using the command for your operating system.
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/configure_official_key_v7.py
python -m agent --check-tournament --agent examples.free_multigame_agent_v10
python scripts/competition_watchdog.py --module examples.free_multigame_agent_v10 --mode both
```

Select Self Hosted in Agent Configuration and use your own Official Agent Key.
The setup script accepts hidden input and saves it only to local `.env`.
Never commit `.env`. Run only one supervisor for this account.
The watchdog's `--mode both` listens for Testing and registered tournament
games; `--mode testing` listens for Testing only. It restarts the same fixed
version after a supervisor exit. The read-only preflight checks registration
and connectivity without playing a game. Keep the computer awake and online.

Agent factory: `examples.free_multigame_agent_v10:create_agent`.
The current agent imports previous policy modules; keep the complete source tree.
No external model API key is needed by this policy.

## Validation and limits

The V10.3 candidate contains 47 Pokemon, 41 Werewolf, 23 Red Alert, and 9
audit/watchdog regression tests. Full-suite results are recorded with releases.
The complete V10.3 suite passed 954 tests and 4 subtests.
The earlier V9 suite passed 834 tests plus 4 subtests. This is not a
competitive win-rate estimate.
V7 completed self-play in all three games and one external Pokemon match (a loss). V8 completed Werewolf and Red Alert self-play; the V8 external Pokemon match was a loss.

The code uses heuristic scoring, not a solved game strategy. V7 addresses
economy reserve handling, recovery after losing a construction yard, joint
forced Pokemon switches, visible immunities, roster weakness and living seer
findings. The older Werewolf simulator reads the wrong message field; its old
simulation outputs must not be treated as platform performance evidence.

## Upstream and scope

The SDK, runtime, baseline examples and tests derive from the official
[UCLA AltruAgent starter](https://github.com/UCLA-Trustworthy-AI-Lab/altruagent-starter).
See `STARTER_README.md` and `GAMES.md` for upstream documentation. Existing
source notices are retained. No additional license grant is declared here.

This repository contains participant code and development tests only. It
does not contain credentials, private configuration, match records, or
opponents' private observations. Each seat uses only its own game information.
Publishing this source does not itself register or start a tournament entry.

## V8 corrections from platform testing

- Parse the official Werewolf plain-text private header, including role,
  fellow wolves and investigations. Public discussion is never parsed as
  private evidence. Earlier V7 tests used JSON-shaped observations and missed
  this integration bug.
- Score spread Pokemon attacks against visible opponents and the actual
  partner, including a selected protective move or switch. Preserve known
  type and ability immunities. These remain heuristics, not exact damage.
- Treat an explicitly empty Red Alert placement list as no available placement;
  do not try placing a completed infantry unit as a building.
- Twelve targeted V8 regression cases cover these changes. Original V7 source
  and its tests remain available for comparison.
## V9 Pokemon metadata correction

The live draft roster dictionary is keyed by agent IDs; V9 uses the SDK's
own agent ID to identify its public draft roster. Battle targeting now joins
legal target labels to the participant-visible current opponent Pokemon.
It uses exposed type/ability, stat boosts, base stats, rain/sun and Grassy
Terrain when ranking damaging actions. It avoids explicitly empty targets.
The stat ratio is a heuristic (not a full damage calculator); hidden opponent
sets are never inferred as certain facts. Eight additional regressions cover
these cases and replay the V8 spread checks. Werewolf and Red Alert remain V8.
V8's external Pokemon test was a loss in six turns (opponent 2/4 remaining).
V9 completed an external Pokemon test: loss after eight turns, opponent 1/4 remaining. Across V7-V9, ten self-hosted tests completed (seven self-play, three external Pokemon losses). No competitive advantage is established.

## V10 candidate and runtime

Pokemon uses a match-local cache of cards exposed during the public draft,
approximate damage/speed and joint action scoring, first-turn Fake Out,
weather-dependent moves, and balanced team selection. The bundled static
`pokemon_public_data_v10.json` is required; it includes Pokemon Showdown's
upstream source identifiers, data hashes and MIT license text. It is loaded
locally and never queries the network during play.

Werewolf uses the seat's private header and permitted public messages to
interpret claims and coordinate votes. Claims remain fallible. It preserves
the older fallback when discussion gives no usable evidence. In an independent
1,000-seed synthetic mixed-opponent evaluation, one V10 seat won 516 games
versus V8's 324. Against six non-chat-reading V8 seats, V10 won 122/240 versus
127/240. These artificial populations do not establish platform win rates.

Red Alert reads the official building-cost schema, reserves funds for tank
infrastructure, chooses attacks by army value, assigns bounded defensive
forces, and retains counterattack capability after losing a refinery.
The V9 baseline (V8 Red Alert policy) won one external Sidestep match in 7:33
against Abu Bakar Siddik. V10 still requires external comparison.

Each SDK seat has a fresh policy instance. `decision_audit.py` writes only
that seat's delivered observations, proposed decisions and action results to
`.local_runtime/records`, with credential fields redacted. WAIT records are
sampled. These files are private, ignored by Git, and never read by policies.
This is not a complete MCP trace: the SDK's standard log records final results.
The watchdog's health files and logs also stay under `.local_runtime`.

Run only one watchdog for the account. Use one shared `--state-dir` when
changing release directories; its OS lock prevents duplicate watchdogs.
Stop/redeploy only between matches and before the applicable version freeze.
After freeze, preserve source/configuration and restart the identical version
only as permitted by the tournament rules. Record the full release commit
with `git rev-parse HEAD`; the published release tag identifies that commit.

## V10.1 corrections

Pokemon now reads the actual stat announced by public Quark Drive and
Protosynthesis activation events and clears it on end or replacement.
Werewolf ignores negated, quoted and conditional vote proposals, restores
its own current discussion message allowance after reconnect, and deduplicates
server echoes. The watchdog retries temporary log-open and process-launch
failures without changing the selected source or starting a duplicate process.
These fixes passed 932 tests plus 4 subtests. V10.1 subsequently completed
self-play in all three games, an external Red Alert win (7:55, opponent
Abu Bakar Siddik), and an external Pokemon loss (9 turns, opponent one
Pokemon remaining). These small samples do not establish a win rate.

## V10.2 corrections from completed tests

Pokemon joint forced switches now use every available legal replacement.
An unrevealed opponent ability can use the same match's public draft card;
an explicitly revealed ability takes precedence. Consumed or unknown items
are not restored from draft cards. Rage Powder and Follow Me receive no
protection benefit when there is no living partner.

Werewolf coordination expires stale or deceased allies' plans. Current-day
public proposals and announced counterclaims take precedence over opening
private plans. A previous discussion's night plan cannot override stronger
current seer evidence. The completed-game replays validate the changed
decisions, not counterfactual wins.

The previous immutable V10.1 policy won 16 of 24 paired offline games against
V9 using Pokemon Showdown 0.11.10, with 446 decisions and no engine errors.
This used three fixed roster pairs, two seeds and swapped sides under
gen9vgc2025regg, without the platform's draft. The custom observation adapter,
weak baseline and limited scenarios mean this is not a platform win-rate
estimate. V10.2 subsequently won an external Pokemon test against preskai
(AWS-hosted, runtime alias Baymax) in six turns, with three Pokemon remaining.
All 14 actions were accepted. Its Werewolf self-play completed with 15 accepted
actions and 21 messages; per-seat replay reproduced the chosen decisions.
Across self-hosted versions, Pokemon external results are one win and four
losses; Red Alert has two wins. Werewolf still lacks an external completed
game. Opponents, drafts and versions differ, so these are not controlled
strength or win-probability estimates.

## V10.3 sleep timing correction

The policy previously credited a slow sleep move with preventing damage from
a faster attack in the same turn. Immediate prevention now depends on move
priority, current estimated speed, Tailwind and already active Trick Room;
future sleep value is retained. Speed ties are treated conservatively. This
is an approximation against ordinary-priority threats, not knowledge of an
opponent's hidden move.

Six regressions cover full action choices and timing boundaries. In three
paired real-engine tactical scenarios, the correction preserved a threatened
Pelipper with Protect instead of relying on slower Spore. The public initial
HP was deliberately constructed for this diagnostic. A separate 24-game
paired test finished 12-12 against V10.2 with no engine errors; it does not
establish an overall strength increase. The completed V10.2 winning trajectory
retained all 14 decisions under same-state replay. V10.3 online testing is
pending.
