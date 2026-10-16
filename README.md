# Super War Dragon V10.8

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
- **Pokemon:** retains V10.7's V10.3-based draft and battle policy, including
  priority-aware sleep, legal forced replacements and the minimal full-HP
  Multiscale/Shadow Shield correction. Ordinary multi-hit damage halves only
  its first hit. Earlier ally hits receive conservative conditional credit,
  which never certifies a KO. Draft estimates stay unchanged; unknown abilities
  are not filled through public-card fallback. Damage, support timing and
  drafting remain approximate.
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

The V10.8 full suite passed **1050 tests and 4 subtests in 83.49 seconds**, with
no warnings. The public checkout passed **282 focused checks in 10.28 seconds**.

The assembly candidate passed 49 focused checks, including 16 new regressions.
An offline replay of 229 completed own-seat inputs kept all 46 decisions from
one recorded win unchanged. Main assaults in two recorded losses changed from
3 to 2 and from 22 to 5; every non-assault command remained identical. This
checks the assembly mechanism on fixed historical inputs. It cannot show
counterfactual battle outcomes or a win-rate improvement, and an active mining
activity does not guarantee future income.

The retained Pokemon correction passed 33 controlled official-engine cases.
A fixed 48-game holdout against V10.3 ended 24–24 with zero errors across
724 decisions and 244 turns. All 96 worker identities and source hashes were
verified. Paired actions and normalized transcripts were identical, so this
supports behavior equivalence on those samples. Fixed rosters, a custom
adapter and the absence of platform drafting limit the comparison.

V10.7 Pokemon self-play completed with 32 accepted actions and no rejections;
all decisions reproduced from each seat's own inputs. This confirmed platform
compatibility, but did not exercise the new multi-hit shield scoring case.

Completed external self-hosted tests through the latest V10.6 Red Alert result:

| Game | Wins | Losses | Limits |
| --- | ---: | ---: | --- |
| Red Alert | 3 | 2 | Mixed versions/maps; latest V10.6 test was a loss |
| Pokemon | 1 | 6 | Mixed drafts/opponents; not a V10.8 estimate |
| Werewolf | 0 | 0 | Self-play completed; no completed external game |

These small, mixed-version samples do not support a high-probability win claim.
V10.8's new assembly rule has not yet completed platform validation.

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
