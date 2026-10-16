# Super War Dragon V10.7

Self-hosted Python agent for Werewolf, Red Alert and Pokemon VGC Doubles Draft
on the UCLA AltruAgent platform. Development used AI assistance.
This is a candidate for platform validation; its tag identifies fixed source.

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

Select Self Hosted in Agent Configuration, bind this public repository, and
register for the desired tournaments. Use your own Official Agent Key. The
setup script accepts hidden input and saves it only to local `.env`.
Never commit `.env`. No external model API key or paid inference is required.

Factory: `examples.free_multigame_agent_v10:create_agent`. Keep the complete
source tree: the current policy imports previous modules. The watchdog's
`--mode both` discovers both Testing and registered tournament assignments.
Run one watchdog for the account, keep the computer awake and online, and use
one shared `--state-dir` when changing release directories. The OS lock avoids
duplicate watchdogs. Its recovery restarts the same fixed version.

## Current behavior

- Pokemon builds on V10.3: match-local public draft cards,
  approximate joint damage/speed, legal forced replacements, type/ability
  checks and priority-aware sleep scoring. It remains a heuristic, with known
  limits in draft, support timing and damage estimates. V10.7 corrects normal
  multi-hit damage against an explicitly observed full-HP Multiscale or Shadow
  Shield, and gives conservative conditional credit when a prior ally hit can
  break the shield. This bonus never certifies a KO. Draft estimates remain
  unchanged, and unknown abilities are not filled from public-card fallback.
- Werewolf preserves V10.2: private role/header parsing, fallible public
  claims, living seer evidence and current-day vote coordination. Prior-day
  plans expire. Each seat has its own policy instance.
- Red Alert preserves V10.5: economy and infrastructure reserves, legal tank
  production, bounded local defense and army-value attacks. When a tank is
  unlocked and its queue is empty without a visible base threat, reserve its
  cost before infantry; preserve harvester recovery and emergency defense.
- V10.6 replaces repeated MCP handshakes with the platform's documented
  [stateless JSON-RPC mode](https://api.altruagent-game.com/skill/mcp.md).
  Offline probes reduced each tool call from four POSTs to one. The same
  seat authentication, one HTTP401 refresh, 10/40/45-second connect/read/total
  timeouts, TLS verification and no redirects remain. Fresh TCP/TLS setup
  still occurs. Typed MCP validation remains; dynamic output-schema fetching
  is removed. The official endpoint must return plain JSON.

## Validation and limits

The complete V10.7 suite passed **1034 tests and 4 subtests in 93.18 seconds**.
The public checkout passed **266 focused checks**, covering current policies,
audit, watchdog, transport, MCP adapter and authentication. Local tests and reduced request count
do not establish real-platform speed or tournament win probability.

At 05:12 PDT on October 16, completed external self-hosted tests total:

| Game | Wins | Losses | Limits |
| --- | ---: | ---: | --- |
| Red Alert | 3 | 1 | Different versions/maps; V10.6 external test running |
| Pokemon | 1 | 6 | Different drafts/opponents; lone win against AWS agent |
| Werewolf | 0 | 0 | Self-play completed, no external completed game yet |

V10.4 was rejected after a 24-game paired offline comparison lost 6-18 to
V10.3. Keeping old selection with its new battle scoring still lost 8-16.
Neither experiment is active here. V10.3 had previously tied V10.2 12-12 in
another limited offline matrix. Fixed public rosters, custom observations,
no platform draft and small samples prevent any high-probability win claim.
V10.7's minimal Pokemon correction passed 33 controlled official-engine rule
and action probes. A fixed 48-game holdout against V10.3 ended 24-24 with zero
errors (724 decisions, 244 turns). All 96 worker identities and source hashes
were verified; all paired actions and normalized transcripts were identical.
This holdout therefore supports behavior equivalence on its samples, not a
measured improvement. It uses fixed rosters and a custom adapter, without the
platform draft. All prior candidate tags remain available for review.

Completed Red Alert records showed idle tank production while infantry
consumed income. Historical costs were missing, so replay validates the
savings mechanism, not counterfactual build time or victory. V10.5 added one
private cost-only snapshot from each seat's delivered static configuration;
missing prices remain unknown. V10.5 won its next external Red Alert test
against Quicksilver in 7:31 with assets 17850 versus 0. All 46 decisions were
reproduced from the completed own-seat records, and 49 commands were accepted.
The observed tank savings mechanism worked; one game is not causal win proof.

V10.6's transport completed Werewolf and Pokemon self-play with 16 and 38
accepted game actions and no rejected actions. The Red Alert external test is
still running. Measured self-play action/result latency did not establish a
speed improvement. V10.7 keeps that transport unchanged; platform validation
of the new Pokemon policy is pending.

## Data, operation and provenance

Policies consume only their seat's delivered state and permitted messages.
The write-only audit stores local decisions/results and redacted own-seat
observations under `.local_runtime/records`. Policies never read these files.
Logs, credentials, private configuration and match records are not published.

Deploy between games before the applicable freeze. After freeze preserve the
submitted source/configuration; only recover the identical version as allowed
by tournament rules. Publishing source alone does not register or start an
entry. Record the full commit and immutable release tag used by the runtime.

The SDK, runtime, baseline examples and tests derive from the official
[UCLA AltruAgent starter](https://github.com/UCLA-Trustworthy-AI-Lab/altruagent-starter).
See `STARTER_README.md` and `GAMES.md`. Source notices are retained; no additional
license grant is declared here. `pokemon_public_data_v10.json` includes
Pokemon Showdown source identifiers, hashes and its MIT license text.
