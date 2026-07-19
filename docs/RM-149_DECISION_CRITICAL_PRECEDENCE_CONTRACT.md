# RM-149 decision and critical-precedence contract

## Authoritative inputs

RM-149 presents, but never computes or alters:

- latest persisted `CorterisParticipationScore` from `CollectorStateRepository.get_latest_score()`;
- latest persisted RM-107 decision payload from
  `get_latest_participation_decision_payload()`;
- persisted `StopFactorAssessment`, verification and conflict evidence;
- stored policy/profile/input versions and timestamps.

No card/detail open calls a ranker, decision service, AI provider, document downloader or analyzer.

## Decision summary

The summary preserves total score, recommendation enum/text, hard exclusion, stop-factor status,
score components, positive/negative factors, missing documents, evidence sources, `scored_at`,
profile version, input fingerprint, decision ID/policy version/`decided_at`, evidence and action plan.
Malformed/future/incompatible payload is `UNAVAILABLE` or `STALE`; it is never repaired by display.

Search relevance is a separate `search_relevance` fact labelled `Релевантность поиска`; it is never
called recommendation, decision or participation score.

## Absolute precedence

Presentation precedence is:

1. blocking persisted stop-factor or hard exclusion;
2. decision-affecting unresolved verification conflict;
3. stale/incompatible/missing decision evidence;
4. current persisted decision;
5. subordinate AI or search-relevance context.

For a blocking factor the first semantic section is a text+icon critical banner, its accessible
description names the blocking evidence, and the primary action is review/verification. A high score,
positive recommendation string, search relevance or AI summary cannot receive a positive dominant
tone or displace this block.

## Freshness

A decision is current only when its stored input fingerprint is present, its score/profile contract
is compatible, and no newer unresolved critical verification state invalidates its evidence. Where a
current tender-input fingerprint cannot be proven without recomputation, the last persisted decision
is displayed as `STALE`/`last known`, not current.

Missing decision is `decision_unavailable`, distinct from `not_recommended`.

## Invariants

- Theme, locale, route, ordering and AI text do not change recommendation/action plan.
- Component/evidence ordering is deterministic by stable code/source.
- Critical state appears in compact card, full detail and safe text export/copy.
- All evidence retains its source; missing evidence is explicit.
- RM-107 policy and critical stop-factor priority are byte-for-byte owned by existing modules.

## Failure and rollback

Payload errors expose bounded reason codes without raw JSON, exception, path or secret-shaped text.
Rollback removes only the presentation projection; persisted decision/score state is untouched.
