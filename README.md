# Super War Dragon V10.9

Self-hosted Python agent for Werewolf, Red Alert and Pokemon VGC Doubles Draft
on the UCLA AltruAgent platform. Development used AI assistance. Each release
tag identifies fixed source; local validation does not establish tournament
win probability.

## Run

Requires Python 3.11 or newer. From the repository root:

```sh
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/configure_official_key_v7.py
python -m agent --check-tournament --agent examples.free_multigame_agent_v10
python scripts/competition_watchdog.py --module examples.free_multigame_agent_v10 --mode both
```

Select Self Hosted in Agent Configuration, bind this repository and register
for the desired tournaments. Use your own Official Agent Key. The setup script
accepts hidden input and saves it only to local `.env`; never commit that file.
No external model API key or paid inference is required.

Factory: `examples.free_multigame_agent_v10:create_agent`. Keep the complete
source tree because current policies import earlier modules. Run one watchdog
for the account, keep the computer awake and online, and use one shared
`--state-dir` when changing release directories. `--mode both` discovers Testing
and registered tournament assignments. The OS lock prevents duplicate
watchdogs; recovery restarts the same fixed version.

## Current behavior

- **Red Alert:** V10.8 adds a limited assembly rule to V10.5's economy reserves,
  tank savings, local defense and army-value attacks. After losing material
  trades, a blind assault waits for two healthy departing tanks or equivalent
  material when a refinery, factory, active harvesting and a legal tank option
  remain available. The calculation excludes the reserved defenders. Visible
  enemy buildings, base emergencies, unavailable economic prerequisites and
  the existing late desperation rule bypass this additional hold. Production,
  defense, mining recovery and retreat behavior are unchanged.
- **Pokemon:** V10.9 adds a limited correction for currently visible Unaware
  to the V10.7 policy. Battle damage ignores the appropriate opposing stat
  stages, including Body Press and Foul Play, while preserving other stat
  modifiers. Known ability suppression, ability-bypassing attacks and Ability
  Shield are handled within this correction. Draft and lineup estimates stay
  unchanged; no ability is inferred from species or public-card fallback.
  Priority-aware sleep, legal forced replacements and the earlier conservative
  Multiscale/Shadow Shield correction remain. Damage, timing and drafting are
  still approximate.
- **Werewolf:** retains V10.2's private role/header parsing, fallible public
  claims, living seer evidence and current-day vote coordination. Prior-day
  plans expire, and every seat has its own policy instance.
- **Transport:** retains V10.6's documented
  [stateless JSON-RPC mode](https://api.altruagent-game.com/skill/mcp.md), reducing
  offline tool-call probes from four POSTs to one. Authentication, typed MCP
  validation, bounded timeouts, TLS verification and no redirects remain.
  Fresh TCP/TLS setup still occurs; the endpoint must return plain JSON.
  The request-count reduction is not a measured platform speed improvement.

## Validation and limits

V10.9 passed **1084 tests and 4 subtests** in 103.61 seconds with no warnings.
The public checkout passed **316 focused tests** in 12.52 seconds.

The Unaware correction passed **127 related checks**, including **34 new
regressions**. Twenty paired official-engine damage cases confirmed the stage,
ability suppression and bypass boundaries. Replaying all 17 own-seat inputs
from one completed V10.8 external loss produced the same legal actions as the
original. This establishes a mechanical correction without showing a different
battle outcome or improved win rate.

The assembly candidate passed 49 focused checks, including 16 new regressions.
An offline replay of 229 completed own-seat inputs kept all 46 decisions from
one recorded win unchanged. Main assaults in two recorded losses changed from
3 to 2 and from 22 to 5; every non-assault command remained identical. This
checks the assembly mechanism on fixed historical inputs. It cannot show
counterfactual battle outcomes or a win-rate improvement, and an active mining
activity does not guarantee future income.

The earlier V10.7 shield correction passed 33 controlled official-engine cases.
A fixed 48-game holdout against V10.3 ended 24–24 with zero errors across
724 decisions and 244 turns. All 96 worker identities and source hashes were
verified. Paired actions and normalized transcripts were identical, so this
supports behavior equivalence for that earlier version on those samples.
The holdout has not been rerun or used to tune V10.9. Fixed rosters, a custom
adapter and the absence of platform drafting limit the comparison.

V10.7 Pokemon self-play completed with 32 accepted actions and no rejections;
all decisions reproduced from each seat's own inputs. This confirmed platform
compatibility, but did not exercise the new multi-hit shield scoring case.

Completed external self-hosted tests through the latest V10.8 Pokemon result:

| Game | Wins | Losses | Limits |
| --- | ---: | ---: | --- |
| Red Alert | 3 | 3 | Mixed versions/maps; latest V10.8 Trapped test was a time-limit loss |
| Pokemon | 1 | 7 | Mixed drafts/opponents; latest V10.8 test was a loss |
| Werewolf | 0 | 0 | Self-play completed; no completed external game |

These small, mixed-version samples do not support a high-probability win claim.
One Red Alert external test remains in progress and is excluded. V10.9's
Unaware correction has not completed a platform game.

## Data, operation and provenance

Policies consume only their seat's delivered state and permitted messages.
The write-only audit stores redacted own-seat observations, decisions and
results locally under `.local_runtime/records`; policies never read these
files. Red Alert records one cost-only snapshot from the delivered static
configuration. The audit leaves missing prices unknown. Logs, credentials, private
configuration and match records are not published.

Deploy between games before the applicable freeze. After freeze, preserve the
submitted source and configuration; only recover the identical version as
allowed by tournament rules. Publishing source alone does not register or
start an entry. Record the full commit and immutable release tag in use.

The SDK, runtime, baseline examples and tests derive from the official
[UCLA AltruAgent starter](https://github.com/UCLA-Trustworthy-AI-Lab/altruagent-starter).
See `STARTER_README.md` and `GAMES.md`. Source notices are retained; no additional
license grant is declared here. `pokemon_public_data_v10.json` includes Pokemon
Showdown source identifiers, hashes and its MIT license text.
