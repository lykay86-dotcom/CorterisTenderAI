# RM-151 retry, cancel, close and recovery matrix

## Cross-cutting rules

- Retry is available only from typed owner capability, creates a new episode/event/attempt and
  revalidates subject, inputs, offline state, authorization and idempotency.
- Cancel request is idempotent and presents `CANCELLING`; only the lifecycle owner can confirm
  `CANCELLED`. Race outcome is the owner's accepted terminal transition.
- Close terminates presentation as `CLOSED`; it neither claims successful work nor kills foreign
  threads. Late generation/revision/sender events are ignored.
- Destructive recovery names and revalidates the exact target/revision after confirmation.
- A previous terminal record, notification and diagnostic evidence are immutable.

## Representative owner matrix

| Surface | Retry | Cancel | Close / late events | Partial / timeout | Recovery and confirmation | Decision |
|---|---|---|---|---|---|---|
| manual collector search | new run/episode after profile/provider revalidation | existing token; request -> cancelling -> owner terminal | RM-140 generation/revision and bounded shutdown preserved | provider partial terminal explicit; timeout distinct | open source/profile or retry explicitly | adapt, never rewrite runtime |
| scheduled search | new scheduled/manual run with new run ID | delegates only to active collector owner | timer stops; controller disconnects on shutdown | consolidate provider partials into one terminal event | edit schedule/profile; admission guard preserved | adapt |
| Dashboard refresh | explicit/button/timer refresh creates new generation | unsupported; disabled reason | sender/thread/generation guard; no post-close page mutation | independent source failure -> partial; no timeout claim | retry refresh | adapt |
| document download | new worker after exact registry/document revalidation | unsupported initially | per-key active map and destroyed-dialog guard | service-owned result; no invented partial | retry exact tender action | migrate projection |
| requirements analysis | new worker/attempt | unsupported initially | per-key guard, terminal immutable | source conflict remains unresolved/partial | retry exact registry key | migrate projection |
| full analysis | new worker/attempt | existing token; wait for owner terminal | per-key generation and dialog close guard | typed service progress; timeout/cancel distinct | retry exact registry key; open diagnostics | migrate projection |
| AI recheck | explicit new worker; provider resolution repeated | unsupported | per-key guard; no late UI publication | disabled/offline/provider failure not success | explicit retry; never reuse credential value in feedback | migrate projection |
| participation score | explicit new worker; deterministic inputs reread | unsupported | per-key guard; decision owner unchanged | missing/conflict not success | retry exact tender; approved prior decision immutable | migrate feedback only |
| provider check | new health check; provider IDs revalidated | existing cancellation token | abandon/owned pool shutdown; late signals rejected | timeout distinct from offline | edit settings/credential only by explicit owner action | adapt |
| system health monitor | new refresh when `OPEN`/idle | existing lifecycle has owner close, no user cancel | RM-144 `OPEN/RUNNING/CLOSING/CLOSED`; sender guard | timed-out close remains closing | open diagnostics/backup/recovery surfaces | adapt projection only |
| backup create | explicit new attempt | unsupported during synchronous owner call | no late event; controls disabled honestly | warnings may be partial | exact destination/artifact; no destructive confirm | adapt, no threading |
| restore/recovery | explicit new attempt after fresh inspection | unsupported during synchronous owner call | no late event; stale action token rejected | warning/usable result -> partial | confirmation names exact backup/DB effect; safety artifact retained | adapt, O1 |
| automatic backup | next timer/manual-now is new episode | stop timer on page close; owner call not cancelled | RM-144 timer shutdown | skipped/due/failure distinct | settings edit/manual retry | adapt |
| Excel import | reselect/re-preview creates new attempt | unsupported during sync import | no late event | validation warnings -> partial, not success | preview/fingerprint and confirmation revalidated | adapt, no threading |
| Excel export/template | explicit new attempt from current visible snapshot | unsupported | no late event | failure terminal | user selects destination; never overwrite silently | adapt |
| crash/support bundle | explicit new bundle attempt | unsupported initially | close does not delete crash/support artifacts | inspection warning may be partial | retry with same report identity; output path not shown | adapt |
| safe mode/recovery | explicit checked recovery | unsupported | process/dialog lifecycle owns exit | damaged/future schema distinct | destructive action confirmed; future schema fail closed | adapt |
| notification open action | failed action can be retried after freshness check | n/a | dialog close preserves item/evidence | stale target is failure | exact typed subject; no current-row fallback | migrate routing adapter |
| application shutdown | no retry in closing shell | owner-specific cancel/wait/refuse | RM-144 ordered bounded shutdown; `CLOSED` presentation | timeout does not become cancelled | user can refuse close only where owner policy permits | keep lifecycle, adapt episodes |

## Unsupported operations

UI must not display a fake cancel/retry button. Unsupported capability includes a stable disabled
reason. RM-151 does not convert synchronous backup/import/export/recovery operations to threads;
that requires separate thread-safety and transactional evidence.

## Race decisions

- cancel accepted before owner terminal: owner decides final result from its state machine;
  presentation never emits cancellation early;
- timeout accepted first: later success is stale and cannot change terminal state;
- close accepted first: later callbacks may update owner persistence but not the closed UI;
- duplicate success/failure: first valid terminal wins; conflict creates internal diagnostic only;
- retry while previous cancellation is pending: rejected until owner terminalizes or explicitly
  permits a separate independent attempt;
- stale destructive confirmation: action revalidation fails as `STALE_TARGET` without mutation.

## Tests

Characterization preserves current RM-140/RM-144 behavior. Expected-red covers new episode IDs on
retry, `CANCELLING` versus confirmed `CANCELLED`, all race decisions, exact target revalidation,
partial/timeout truthfulness and close/no-late-signal behavior with logical events rather than
flaky sleeps.

