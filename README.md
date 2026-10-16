# Super War Dragon V9

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
python -m agent --check-tournament --agent examples.free_multigame_agent_v9
python -m agent --match --agent examples.free_multigame_agent_v9
```

Select Self Hosted in Agent Configuration and use your own Official Agent Key.
The setup script accepts hidden input and saves it only to local `.env`.
Never commit `.env`. Run only one supervisor for this account.
`--match` listens for Testing matches only. The read-only preflight checks
registration and connectivity without playing a game.

Agent factory: `examples.free_multigame_agent_v9:create_agent`.
The current agent imports previous policy modules; keep the complete source tree.
No external model API key is needed by this policy.

## Validation and limits

The development workstation passed 834 tests plus 4 subtests for V9,
including 15 V7, 12 V8 and 8 V9 regression tests. These include 400 synthetic Red Alert observations
and 18 Pokemon target scenarios. This is not a competitive win-rate estimate.
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