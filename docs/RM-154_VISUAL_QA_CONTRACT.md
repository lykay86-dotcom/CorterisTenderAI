# RM-154 Visual QA Contract

Contract version: `rm154-visual-contract-v1`

## Outcome model

Each case ends in exactly one machine-readable state:

- `PASS`: canonical fingerprint matches and the approved comparison policy passes;
- `FAIL`: canonical fingerprint matches and pixels violate the policy;
- `BLOCKED`: the renderer environment, fixture readiness, or required asset is not
  canonical, so a pixel verdict would be misleading;
- `SKIPPED`: a policy-declared noncanonical CI leg or local developer invocation did
  not request candidate rendering.

`BLOCKED` and `SKIPPED` include a typed reason. They are never counted as a pixel
pass. The canonical comparison command treats missing baselines, missing cases,
unexpected cases, and environment mismatch as nonzero outcomes.

## Case identity and catalog

Case IDs match:

```text
[a-z0-9]+(?:[.-][a-z0-9]+)*\.(dark|light)\.(canonical|compact)
```

Each typed catalog entry declares:

- case ID and fixture schema version;
- surface owner and factory;
- theme, logical viewport, and expected DPR;
- state builder and ready predicate;
- focus/selection/scroll contract;
- comparison policy and mask policy IDs;
- whether native RM-152 evidence is also required;
- synthetic-data/privacy classification;
- baseline filename and review label.

Catalog order is lexicographic and unique. Tests reject duplicate IDs, unsafe paths,
unversioned policies, unknown states, mutable case objects, and case/baseline drift.

## Fixture isolation

Visual cases may access only approved repository assets and installed font files.
The test fixture provides in-memory repositories and settings, a fixed clock, fixed
locale/timezone, fixed domain objects, disabled controller startup, disabled health
refresh, and bounded Qt event draining. Network sockets, live AI providers, keyring,
user configuration, real business databases, and arbitrary filesystem traversal are
forbidden and guarded by tests.

Widgets must be closed and deleted after each case. A repeated-case resource check
must show no positive growth in the RM-153 tracked timer/thread categories.

## Capture contract

1. Validate environment and fonts before constructing the case.
2. Construct through the existing production owner plus test-only adapters.
3. Apply theme and route/state explicitly.
4. Resize to the catalog viewport, show offscreen, drain bounded events, and assert
   the ready predicate.
5. Render the client widget to an opaque RGB32 image.
6. Normalize to metadata-free RGB PNG and validate the expected dimensions.
7. Capture the same case three times with fresh widget construction when generating
   a candidate; all normalized byte hashes must match.
8. Dispose the widget and all patch/adaptor scopes in a `finally` path.

Native chrome, cursor, tooltip timing, drag images, OS dialogs, and screen pixels are
outside this capture contract.

## Baseline and manifest contract

Approved files live under `tests/visual/baselines/rm154-v1/`. The stable JSON
manifest contains:

- manifest/schema versions and sorted case records;
- renderer fingerprint and its SHA-256;
- source commit used to generate the reviewed candidate;
- normalized PNG SHA-256 and pixel SHA-256;
- width, height, RGB mode, encoded byte size;
- theme, viewport, case-fixture, comparison, and mask policy IDs;
- reviewer authorization record and update reason;
- native-evidence-required flag.

Absolute paths, usernames, CI workspace paths, environment dumps, secrets, and
machine identifiers are prohibited in committed manifests. JSON serialization is
UTF-8, sorted-key, compact, and newline-terminated.

Missing, extra, renamed, unhashed, dimension-mismatched, or modified baseline files
fail validation. The manifest is authoritative; directory enumeration is only a
consistency check.

## Comparison policies

Initial approved comparison policy:

| ID | Size | Changed pixels | Max channel delta | Mean delta | Masks |
|---|---|---:|---:|---:|---|
| `strict-rgb-v1` | exact | 0 | 0 | 0 | `none-v1` |

`none-v1` contains no rectangles and no alpha/semantic exclusions. Any future
tolerance or mask requires a new versioned policy, a stated visual-risk rationale,
unit tests proving both pass and fail boundaries, an audit amendment, and explicit
golden review. Policies cannot be weakened in place.

The comparator reports dimensions, changed-pixel count and percentage, per-channel
maximum, mean absolute delta, bounding box, and hashes. A deliberate one-pixel token
mutation and a deliberate layout mutation must fail its tests.

## Failure and candidate artifacts

On `FAIL`, the harness writes only to a caller-supplied artifact root:

- actual normalized PNG;
- expected approved PNG;
- absolute RGB diff image;
- visible overlay/highlight image;
- sanitized result JSON with metrics and typed outcome;
- sanitized environment diff.

Candidate mode writes the same review structure plus a candidate manifest and the
three repeatability hashes. It never writes the approved baseline directory.

Artifact paths are resolved and checked to remain below the supplied root. Existing
files are replaced only within a case-specific artifact directory. CI retention is
14 days. Success runs do not upload a full artifact bundle unless explicitly running
candidate mode.

## Baseline update authorization

There is no environment-variable-only or implicit update path. The workflow is:

1. run candidate mode on the canonical Python 3.12 CI renderer;
2. download and visually review the bounded artifact bundle;
3. verify repeatability, privacy scan, dimensions, case list, hashes, and environment;
4. invoke the local import command with an explicit RM-154 approval phrase, candidate
   directory, update reason, and reviewer identifier;
5. review the source diff including every PNG and manifest record;
6. rerun canonical comparison in CI.

The import command refuses CI, a dirty/untracked candidate tree, noncanonical
fingerprints, missing/extra cases, a blank reason/reviewer, an incorrect approval
phrase, or failed privacy/repeatability checks. It does not generate candidates.
Removing a baseline follows the same authorization and must also remove or amend the
catalog entry.

## Privacy contract

Committed images and artifacts use only fixed synthetic content. Automated checks
scan manifest strings, PNG ancillary chunks, and extracted textual fixture inputs for:

- current username, home/workspace/temp/download paths, and drive-specific absolute
  paths;
- emails, access tokens, API-key patterns, connection strings, and private hostnames;
- real tender/database records, provider output, and user settings;
- timestamps other than the approved fixed fixture values.

PNG output may contain only structural PNG chunks required for the normalized RGB
image. Failure reports include normalized relative identifiers, never exception
environment dumps or raw settings.

## Performance and packaging guardrails

- Normal full-suite visual work is bounded to the approved catalog and canonical leg.
- Candidate repeatability is three captures per case; ordinary comparison captures
  once per case.
- Artifact and baseline size is reported and checked against a versioned repository
  budget before import.
- Visual infrastructure remains under tests/scripts and is not imported by product
  startup paths.
- The PyInstaller spec and frozen smoke gate must prove that no baseline, candidate,
  diff, review artifact, or system font is bundled.
- RM-153 performance tests and exact budgets remain unchanged and must pass.

## Native evidence rule

The manifest's `native_evidence_required` field is informational linkage. RM-154
tools must not edit RM-152 native evidence and must not translate an offscreen visual
`PASS` into a native cell status. The closeout report lists those linked cases as
still subject to their existing RM-152 status.

