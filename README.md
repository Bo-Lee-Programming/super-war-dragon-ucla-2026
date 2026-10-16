# Super War Dragon V7

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
python -m agent --check-tournament --agent examples.free_multigame_agent_v7
python -m agent --match --agent examples.free_multigame_agent_v7
```

Select Self Hosted in Agent Configuration and use your own Official Agent Key.
The setup script accepts hidden input and saves it only to local `.env`.
Never commit `.env`. Run only one supervisor for this account.
`--match` listens for Testing matches only. The read-only preflight checks
registration and connectivity without playing a game.

Agent factory: `examples.free_multigame_agent_v7:create_agent`.
V7 imports previous policy modules; keep the complete source tree.
No external model API key is needed by this policy.

## Validation and limits

The development workstation passed 814 tests plus 4 subtests before publication,
including 15 V7 regressions. These include 400 synthetic Red Alert observations
and 18 Pokemon target scenarios. This is not a competitive win-rate estimate.
Platform testing of this self-hosted version is still pending.

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
