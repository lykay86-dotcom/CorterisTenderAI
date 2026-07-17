# RM-137 — acceptance evidence отраслево-независимой нормализации

Дата: 17 июля 2026 года. Feature baseline:
`cf60941a94bc4023edfa73cba65885f9c6b16b8c`.

## Entry gate

- RM-136 feature PR #78, merge `d84288ab74553e500ad9eaf9f51a091404490551`.
- RM-136 exact merge-SHA Windows run `29606492310`: success на Python 3.12/3.13.
- RM-136 docs-only closeout PR #79, merge
  `2a8514df70c4f6f8d856d07f5a2d367e30d60189`.
- RM-137 является единственным `IN PROGRESS`; RM-138–RM-200 остаются `PLANNED`.
- Baseline: `1859 passed, 2 warnings in 127.69s` на Python 3.12.7.

## Реализация

- Canonical model owner: `app.tenders.models.UnifiedTender` (не менялся на новый type).
- Canonical normalization owner: `app.tenders.collector.normalizer.TenderNormalizer`.
- Contract: `TENDER_NORMALIZATION_CONTRACT_VERSION = 1`.
- Existing `NormalizedTender` расширен typed bounded diagnostics, safe unverified provenance,
  contract version и semantic fingerprint.
- Existing `content_hash` остаётся semantic fingerprint owner; duplicate/identity/document/
  analysis hashes не смешаны с ним.
- Collector уже использовал normalizer через DI; legacy provider-result engine теперь вызывает
  ту же pure boundary до merge/dedup.
- EIS currency mapping больше не подставляет RUB без explicit marker; Moscow status использует
  exact allowlist, а documented naive portal timestamps получают explicit MSK context.
- Manual API/RSS/FTP/FTPS mappings проходят тот же offline normalization method; live
  enablement/admission/credentials/transport RM-136 не изменены.
- Money canonical tender path отклоняет `float`, поддерживает locale-independent Decimal strings,
  total precision 38 и scale 28, сохраняя legacy RM-130 Decimal payloads.
- Canonical datetimes aware и приводятся к UTC; naive legacy values остаются readable, но при
  новом normalization становятся missing + typed diagnostic и безопасный freshness signal.
- URLs обрабатываются offline; userinfo/control rejected, secret-like query и fragment не
  попадают в canonical URL/diagnostics/provenance.
- Text/IDs/collections нормализуются консервативно; leading zeros сохраняются, отраслевые
  keywords не меняют law/status/region.

## Persistence и compatibility

- Новая БД, repository, table или search pipeline не создавались.
- Collector SQLite остаётся schema 14; Registry остаётся schema 1.
- Collector tender payload v1 и legacy unversioned Registry JSON читаются без destructive
  rewrite. DB migration/backup не требуются.
- Normalization metadata добавляется как backward-compatible optional JSON content.
- RM-107 regression guard подтверждает неизменные score/recommendation/hard-exclusion для тех же
  canonical facts; весь существующий decision/critical stop-factor suite зелёный.
- UI/export не менялись: для DoD отдельная вкладка или новый export contract не требуются.

## Локальная проверка

Окружение: Microsoft Windows 10.0.19045 x64, Python 3.12.7,
`Russian Standard Time` (UTC+03:00). Из-за недоступного глобального pytest temp команды
использовали workspace-local `--basetemp`; это test-harness adjustment, код не менялся.

- Expected red до production: одна collection error отсутствующих RM-137 symbols.
- Focused contract: `20 passed in 5.13s`.
- Provider/RM-107 neighbors: `95 passed in 13.19s`.
- Precision compatibility: `31 passed in 5.40s`.
- Full pytest: `1879 passed, 2 warnings in 98.80s`.
- `python -m ruff check .`: success.
- `python -m ruff format . --check`: `608 files already formatted`.
- Required `python -m mypy`: `Success: no issues found in 20 source files`.
- Changed-owner mypy: `Success: no issues found in 7 source files`.
- `python scripts/check_repository_secrets.py`: passed.
- Offline credential-isolation smoke: `2 passed in 12.10s`.
- Migration/schema smoke: `5 passed in 6.82s`.
- Public import smoke: `DashboardController`.
- Headless composition smoke: `1 passed in 0.41s`.
- Release/build smoke: `6 passed in 7.84s`.
- `python -m pip_audit --skip-editable`: no known vulnerabilities; editable project skipped as
  expected. Workspace-local cache удалён после проверки.
- `git diff --check`: success.

Первый full run после реализации дал `1865 passed, 14 failed, 2 warnings`: все 14 failures
имели одну причину — новый scale limit 18 отклонял легальный legacy RM-130 Decimal scale 19.
После root-cause fix limit установлен в 28 при прежней total precision 38; focused RM-130 и
последующий full suite зелёные. Skip/xfail/assertion weakening не применялись.

## Delivery

- Feature branch: `feat/rm-137-industry-agnostic-normalization`.
- Audit commit: `32a1257`.
- Expected-red commit: `209acd7`.
- Core normalizer commit: `c40aa4d`.
- Provider routing commit: `1b6fd59`.
- Decimal compatibility commit: `c184c2f`.
- Feature PR / PR gate / merge SHA / exact merge-SHA gate: pending.
- Docs-only closeout: запрещён до успешного exact merge-SHA Windows gate.

## Rollback

Feature-level rollback выполняется reverse revert commits после audit/expected-red history:
`c184c2f`, `1b6fd59`, `c40aa4d`. Legacy payload readers и schema остаются прежними, поэтому
данные не требуют downgrade. Optional normalization metadata игнорируется старым reader.
Destructive reset и DB rewrite не нужны.

## Scope guard и ограничения

RM-138 parallel search, RM-139 monitoring и RM-140 stabilization не реализовывались. Existing
legacy concurrency не расширялась. Commercial и manual providers без подтверждённого live
contract остаются non-runnable; parity доказана offline без фиктивного сетевого результата.
