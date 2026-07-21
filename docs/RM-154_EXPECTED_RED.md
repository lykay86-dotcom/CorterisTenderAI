# RM-154 Expected-Red Evidence

## Baseline and scope

- Canonical implementation baseline: `2453304b5a7f7bea74bccf07e2ceccc4b6cf11a4`.
- Audit/decision package: `b7c5052`.
- Expected-red commit: `ce3f53c`.
- Scope: UI-141-016 visual regression infrastructure only.

No accepted PNG baseline, renderer, comparison implementation, candidate workflow, or CI visual
gate existed when this contract was executed. The expected-red package introduced typed immutable
contracts and deliberately incomplete seams; it did not change production UI or business logic.

## Exact expected-red result

```text
python -m pytest -q tests/test_rm154_visual_contracts.py
6 failed, 3 passed
```

The three passing tests proved the case schema, unsafe case-ID rejection, and stable sanitized
fingerprint serialization. The six intended failures represented the missing implementation
boundaries:

1. byte-identical normalized RGB comparison;
2. visible detection of a deliberate theme-token mutation;
3. visible detection of a deliberate layout mutation;
4. typed fail-closed renderer-environment mismatch;
5. contained, allowlisted case artifact paths;
6. privacy rejection for absolute paths and secret-like content.

There were no unrelated failures. In particular, the contract did not read network, keyring,
production databases, user settings, live AI, or real tender data.

## Green transition

- `6e5a9a5` implemented the strict comparator and guardrails.
- `fad5f6d` added deterministic synthetic rendering and workflow isolation.
- `c66c076` imported the explicitly reviewed canonical baseline.
- `4871765` enabled the permanent strict comparison workflow.
- `b9134d1` normalized the JSON round-trip boundary for font-family tuples.

The final focused contour contains 30 passing tests across contract, renderer, workflow, baseline,
privacy, release, and build-policy coverage. Deliberate token and layout mutations remain negative
tests; they fail comparison without changing the accepted baseline or tolerance policy.

## Invariants

- Tolerance remains exact RGB (`0` changed pixels); there are no masks.
- Expected-red evidence cannot authorize a baseline update.
- Score, recommendation, critical stop-factor priority, schemas, migrations, and production
  dependencies are unchanged.
- RM-152 native/DPI `BLOCKED` and `NOT_EXECUTED` statuses are not promoted by offscreen evidence.

