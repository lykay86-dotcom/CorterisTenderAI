# PRE-RM-156 Collector P7 — docs-only commercial-section matrix/order

Дата: 23 июля 2026 года.

Статус: `LOCALLY VALIDATED`; publication и exact merge-SHA Quality Gate ожидаются.

## 1. Основание

Третий named P7 source `otc` прошёл отдельный official read-only access audit и принят как
`BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`:

- PR #149 head `f66feda46eb0432ca4bd2391c3caad7e59fc3a95`;
- PR-head Quality Gate `29987577868`: attempt 1 Python 3.12 поймал transient native Windows
  `access violation`; attempt 2 успешен — jobs `89143828971` (3.12) и `89143830089` (3.13);
- merge commit `023002df23273d01aad2630f92ae293d2dfc10f2`;
- fresh exact merge-SHA Quality Gate `29988314604`: jobs `89145077281` (3.12) и
  `89145077332` (3.13) успешны, включая dependency audit.

Каноническое ТЗ завершает P7 пунктом «commercial sections федеральных операторов внутри их
existing owner». Оно запрещает новые guessed identities/endpoints и требует отдельный package на
каждый разрешённый source. P6 уже выполнил восемь отдельных operator access audits; каждый
зафиксировал section evidence и обязательные DoR blockers. Повторять те же network audits под
другим названием нельзя: это дублировало бы evidence и могло бы создать второй adapter owner.

## 2. Existing-owner matrix

Порядок сохраняет каноническую P6 owner-последовательность. Это порядок будущего re-audit после
external unblock, а не разрешение implementation.

| Позиция | Existing owner / section boundary | Принятое evidence | Commercial-section verdict |
|---|---|---|---|
| 1 | `zakaz_rf` | Public notice HTML; `/Services/` и `/QueryForms/` закрыты robots; API/feed, permission и schema отсутствуют | `BLOCKED_EXTERNAL` |
| 2 | `roseltorg` (`roseltorg_commercial` compatibility alias) | Public section-labelled HTML и indexable pagination; procurement API/data-use contract отсутствует | `BLOCKED_EXTERNAL` |
| 3 | `rad` | Несколько Lot-online section hosts; agreement требует письменное permission для scripts/collection/reuse | `BLOCKED_EXTERNAL` |
| 4 | `tek_torg` | Official procedure export/WSDL и section dictionaries существуют; rate/completeness/version/money/retention permission и approved fixtures отсутствуют | `BLOCKED_EXTERNAL` |
| 5 | один implementation owner АО «ЭТС»: existing placeholders `ets_nep` и `fabrikant` | Operator общий; section/protocol identity boundary не доказана; organizer SOAP API не является discovery API | `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED` |
| 6 | `sber_a` (`sber_commercial` compatibility alias) | Public 44-ФЗ/223-ФЗ registries; machine contract, automation/reuse permission и section coverage отсутствуют | `BLOCKED_EXTERNAL` |
| 7 | `rts_tender` (`rts_commercial` compatibility alias) | Section pages существуют, ordinary client получает Anti-DDoS challenge; shared B2B-РТС protocol не доказан | `BLOCKED_EXTERNAL` |
| 8 | `gazprombank` | Multiple product sections и explicit RSS third-party-use intent; published feed сейчас final `404`, schema/completeness/retention отсутствуют | `BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE` |

Compatibility aliases не являются новыми providers. Для АО «ЭТС» два persisted canonical
placeholders сохраняются без alias migration; будущий contract package обязан выбрать shared
adapter with section profiles, audited distinct adapters или migration только после persisted
settings/credentials/history/export audit.

## 3. Решение

1. Не создавать отдельные provider IDs для commercial sections. Section profile живёт внутри
   existing canonical owner и обязан использовать shared runtime/page/checkpoint/artifact/settings/
   secret/repository paths.
2. Признать принятые P6 audits достаточными для текущего **P7 commercial-section access-audit
   pass**: все восемь позиций честно blocked, ни одна не достигла Definition of Ready.
3. Не создавать повторные parser/client/fixture packages без нового official external evidence.
   Unblock оформляется отдельным amendment package в матричном порядке.
4. Не активировать aliases как самостоятельные identities и не объединять `ets_nep`/`fabrikant`
   без принятого identity/schema migration decision.
5. После merge и успешного exact merge-SHA Gate этого решения P7 access-audit pass считается
   завершённым, но P7 implementation и Collector prerequisite не считаются `DONE`.
6. Следующим может быть только отдельный P8 aggregator-discovery gate package; P8 implementation,
   P9, Collector closeout и production RM-156 параллельно не начинаются.

## 4. Scope boundary

Package меняет только документацию. Network research, application/tests, catalog/factory,
settings/readiness, credentials/keyring, aliases, endpoints/allowlists, fixtures/raw artifacts,
DB/schema/migrations, dependencies и RM-107 deterministic decision не меняются.

No-adapter результат является следствием DoR, а не пропуском implementation. Current disabled/
`NOT_CONFIGURED` placeholders и все accepted unblock requirements сохраняются.

## 5. Rollback

До начала P8 rollback — revert этого docs-only commit. После отдельного P8 package история не
переписывается: выполняется новое docs-only decision. Rollback не снимает blockers, не создаёт
providers и не удаляет P6/P7 evidence.

## 6. Локальная валидация

- Первый focused run с длинным worktree-local basetemp дал `1 failed, 33 passed`: SQLite migration
  backup не открылся из-за Windows path length. Тот же contour с коротким уникальным basetemp:
  `34 passed in 13.86s`.
- Full baseline с коротким command-scoped basetemp:
  `2467 passed, 2 warnings in 278.36s`; обе warnings — прежние `openpyxl` notices.
- Ruff: `All checks passed`; format: `804 files already formatted`; mypy:
  `Success: no issues found in 20 source files`; repository secret scan и `git diff --check`
  успешны.

Pytest использовал workflow-compatible `QT_QPA_PLATFORM=offscreen`. Application/tests/thresholds/
dependencies не менялись; path-length failure не является product regression.

## 7. Publication acceptance

Ожидаются PR-head и exact merge-SHA Windows Quality Gate. P8 worktree создаётся только после
fresh exact success.
