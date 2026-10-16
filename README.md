# Super War Dragon V10

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

The V10 candidate contains 28 Pokemon, 25 Werewolf, 23 Red Alert, and 6
audit/watchdog regression tests. Full-suite results are recorded with releases.
The complete V10 suite passed 916 tests and 4 subtests; the public checkout
also passed 90 focused regression checks before publication.
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
