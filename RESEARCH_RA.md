# Red Alert composition memory pilot

This branch preserves the V10.9 baseline policies and SDK at commit
8b9971bd33301f8738ee36191eb42ba2bd8a5825. It is an optional Testing experiment,
not a promoted tournament strategy or evidence of a win-rate improvement.

The candidate remembers whether its own delivered view has ever shown an
enemy vehicle, including V2 launchers. When the existing infantry scheduler
would otherwise forget that evidence through fog, it retains the rocket
infantry preference. A tick rollback clears this memory. Economy reserves,
prices, attacks, defense and all other policies remain unchanged. Permanent
memory may overproduce rockets after an opponent changes composition.

## Isolation

The optional factory is `examples.testing_composition_wrapper:create_agent`.
Its startup environment `RA_COMPOSITION_TEST_SEATS` must be a JSON object of
exact canonical game-session UUIDs to integer candidate seat 0 or 1. There is
no wildcard. The operator must first verify official assignment metadata
explicitly says Testing and Red Alert for those selected rooms and seats.
The SDK's `tournament_id=None` alone is not proof of a Testing assignment.
Do not acquire an extra seat lease to inspect a session. If a new session UUID
does not equal the verified room UUID, the experiment falls back to baseline;
do not modify routing during an active game.

Other sessions, seats, games and any non-None tournament ID use V10.9. Each
route has separate policy state. The optional candidate is checked against a
fixed SHA256 after CRLF/LF normalization; unavailable or changed source uses
baseline. Only safe PID/session/seat routing metadata is printed. Policies do
not inspect logs, spectator views, other seats, credentials or external data.

Use one listener. Keep startup routing fixed for every spawned worker. Stop or
switch only with zero active assignments. Freeze at the actual formal start
or the organizer submission deadline, whichever comes first. Baseline routing
does not defend against a server reusing or reclassifying a verified test UUID.

## Preregistered pilot

Two official Testing self-play games on Trapped, 10 minutes each, with candidate
seat 0 in the first and seat 1 in the second. Opposite seats use V10.9. Record
official outcomes, accepted/rejected actions and, after completion only, each
seat's own observations and exact offline reproduction. Confirm the candidate
route and actual composition-memory branch were exercised. A fallback or no
coverage game is not evidence for the candidate. Restarts must be reported.

No policy, roster or parameter tuning is allowed between these two games.
Two games cannot estimate tournament win probability; favorable outcomes only
justify considering further validation. Critical legality or routing failures
reject promotion. Baseline V10.9 remains the formal version throughout.
