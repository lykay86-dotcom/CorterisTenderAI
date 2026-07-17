# RM-136 — acceptance evidence безопасного manual provider health-check

Дата: 17 июля 2026 года

Baseline / RM-135 docs-closeout SHA:
`ef5cee6d0ef2079f23866fbb809575806f52a0d4`.

Feature commit:
`0d270a8b58ed2489811648443ee69d4ccab39959`.

Статус: **feature acceptance, PR merge и exact merge-SHA gate пройдены; RM-136 закрывается
отдельным docs-only closeout.**

## 1. Реализованный контракт

- immutable health outcome/state/reason/stage/result/evidence и exact revision-aware binding;
- code-owned TTL 15 минут, clock rollback/future/mismatch fail closed;
- existing `collector_provider_health.json` повышен до schema v2: latest evidence, typed load,
  atomic replace, v1 byte-exact backup, invalidate и stale compare-and-replace;
- existing provider settings повышены до schema v6 для typed FTPS implicit/explicit mode;
  v5 мигрирует лениво в implicit с byte-exact backup при первой mutation;
- dynamic non-secret manual credential descriptors и runtime-only redacted resolution через
  existing `ProviderCredentialService`;
- all-answer DNS classification, global-address allow policy, pinned HTTPS/FTPS connection,
  TLS hostname verification, redirects/non-2xx rejected, proxy/custom-CA/downgrade surface absent;
- HTTP/RSS только `GET`; FTP/FTPS только bounded passive listing и один suffix-matching sample;
  plaintext FTP не создаёт healthy evidence, а credentials для него блокируются;
- payload проходит existing RM-135 bounded parser/mapping preview без Tender/DB/checkpoint writes;
- single-flight per provider, global maximum 2, cooldown 5 секунд и cooperative cancellation
  DNS/connect/read operations;
- configured manual provider проверяется явно и независимо от enabled; success показывает
  `Готов к включению`, но не включает provider;
- explicit enablement и каждый admission требуют current `PASSED/HEALTHY` exact evidence;
- protocol/spec/registration/credential mutations инвалидируют evidence;
- built-in provider flow и existing in-run health monitor сохранены.

## 2. Expected-red evidence

После docs-only commit `f4bb93a` и до production changes exact focused run дал:

```text
12 errors during collection in 6.03s
```

Все errors были только отсутствующими RM-136 modules/symbols. Expected-red commit:
`31da549`.

## 3. Final verification evidence

Среда: Windows, CPython 3.12.7, `PYTHONUTF8=1`, `QT_QPA_PLATFORM=offscreen`, отдельные
`--basetemp` каталоги.

| Gate | Exact result |
|---|---|
| RM-136 focused modules | `36 passed in 4.34s` |
| Full pytest, final current tree | `1859 passed, 2 warnings in 70.14s` |
| Repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format check | `606 files already formatted` |
| Required mypy contour | `Success: no issues found in 20 source files` |
| Explicit RM-136 owner mypy contour | `Success: no issues found in 8 source files` |
| Offline credential isolation smoke | `2 passed in 4.06s` |
| DB/schema smoke | `5 passed in 2.77s` |
| Public import smoke | `DashboardController` |
| Headless composition smoke | `1 passed in 0.20s` |
| Release/build smoke | `6 passed in 3.16s` |
| Dependency audit | editable project skipped; `No known vulnerabilities found` |
| Git whitespace check | passed |

Два warnings — принятые legacy openpyxl fixture warnings об unsupported extension и conditional
formatting; новых warnings нет.

## 4. Security and no-side-effect evidence

- automated tests используют fakes/injected pinned ports и не обращаются к public providers;
- literal/private/link-local/metadata/IPv4-mapped/mixed DNS targets, unsafe ports, userinfo и
  encoded control characters fail closed;
- HTTP redirect/error/MIME/oversize и FTP passive bounce/listing/sample limits покрыты;
- FTPS implicit `990` и explicit AUTH TLS `21` dispatch типизированы; control/data TLS use the
  validated hostname and pinned address;
- cancellation прерывает inflight resolution/I/O and does not replace previous evidence;
- raw exception/payload/endpoint/secret sentinel не проходит в health serialization или Qt;
- legacy `ManualConnectorTester`, host keyring guessing, startup probe, automatic enable/profile/
  scheduler mutation и normal collection side effects отсутствуют;
- tampered `enabled=true`, corrupt/future evidence, stale TTL или changed binding не обходят
  canonical admission.

## 5. Release boundary

Feature PR #78 слит в `main` merge commit
`d84288ab74553e500ad9eaf9f51a091404490551`.

PR Quality Gate run `29606049619` успешен:

- Python 3.12 — `1859 passed, 2 warnings in 142.75s`;
- Python 3.13 — `1859 passed, 2 warnings in 87.96s`.

Exact merge-SHA Quality Gate run `29606492310` успешен:

- Python 3.12 — `1859 passed, 2 warnings in 93.95s`;
- Python 3.13 — `1859 passed, 2 warnings in 103.55s`.

Все обязательные jobs завершились `success`. Неблокирующее official-actions annotation о
Node.js 20/24 не повлияло на gate. RM-136 соответствует Definition of Done и переводится в
`DONE` этим docs-only closeout; RM-137 становится единственным `IN PROGRESS`, RM-138+ не начаты.
