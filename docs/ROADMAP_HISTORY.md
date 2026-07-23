# История дорожной карты CorterisTenderAI

## 2026-07-23 — P7 commercial-section matrix/order подготовлен

- Восемь federal operator boundaries сопоставлены только с existing canonical owners в принятом P6
  порядке; compatibility aliases не создают providers, АО «ЭТС» сохраняет один implementation
  owner при двух disabled persisted placeholders.
- Принятые P6 audits уже покрывают section evidence и DoR blockers. Повторный network audit,
  adapters/fixtures/settings/DB/dependencies не создаются; все commercial sections остаются
  `BLOCKED_EXTERNAL`.
- После merge/exact P7 access-audit pass может завершиться без implementation claim; P8 открывается
  только отдельным package.
- Локально: первый длинный basetemp вызвал Windows path-length SQLite backup error при `33 passed`;
  focused rerun с коротким basetemp — `34 passed`, full — `2467 passed, 2 warnings`.
  Ruff/format (`804 files`), mypy (`20 source files`), secret scan и `git diff --check` успешны.

## 2026-07-23 — Collector P7 OTC access audit принят и слит

- Official public human search/detail pages существуют, а Регламент описывает account OTC-CRM и
  customer-side EIS integration. Published external procurement discovery API/feed и permitted
  automation/reuse contract отсутствуют; verdict
  `BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`.
- HTML/XHR reverse engineering, login, forms, bulk access и fixture capture не выполнялись.
  Commercial sections не начинаются до merge/exact audit и отдельного docs-only section matrix/order
  решения внутри existing owners.
- Локально: focused `34 passed in 14.76s`, full suite
  `2467 passed, 2 warnings in 254.20s`; Ruff/format (`804 files`), mypy (`20 source files`),
  secret scan и `git diff --check` успешны. Pytest использовал
  `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #149 head `f66feda46eb0432ca4bd2391c3caad7e59fc3a95`; PR-head run `29987577868`
  attempt 1 Python 3.12 поймал transient native Windows `access violation`, attempt 2 успешен
  (jobs `89143828971`/`89143830089`). Merge
  `023002df23273d01aad2630f92ae293d2dfc10f2`; fresh exact run `29988314604` успешен
  (jobs `89145077281`/`89145077332`), включая dependency audit.
- Только после exact success создан отдельный docs-only commercial-section matrix/order worktree.

## 2026-07-23 — P7 docs-only переход к OTC принят и слит

- Принятые B2B-Center и Фабрикант blockers сохраняются в позициях 1–2 P7; `otc` назначен только
  следующим access-audit target в позиции 3 без access/readiness/fixture/working claim.
- Application/tests/settings/credentials/DB/schema/fixtures/dependencies не меняются. Отдельный OTC
  audit не начинается до merge и успешного exact merge-SHA Quality Gate этого решения; commercial
  sections, P8/P9 и production RM-156 не начинаются параллельно.
- Локально: focused `34 passed`; первый full run поймал один shutdown timing-race при
  `2466 passed`, тот же lifecycle test прошёл `10/10` fresh processes, повторный full run —
  `2467 passed, 2 warnings`. Ruff/format (`804 files`), mypy (`20 source files`), secret scan и
  `git diff --check` успешны.
- PR #148 head `3ba012506e147a4a8392e8a1dea75e153307e016`; PR-head run `29986076319`
  успешен (jobs `89138089157`/`89138089106`). Merge
  `5c087726e2cb32c88c6b9760d8b43b887da4234f`; exact run `29986457553` успешен (jobs
  `89139297913`/`89139297894`), включая dependency audit.
- Только после exact success создан отдельный OTC access-audit worktree.

## 2026-07-23 — Collector P7 Фабрикант access audit принят и слит

- Official SOAP/XML API и section specifications опубликованы, но предназначены для SRM-систем
  заказчика: own notices/protocols/proposals/status/files. Source-wide discovery/search contract
  отсутствует; verdict `BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH`.
- DEMO form/login не использовались, organizer API не подменяет discovery adapter, human registry
  scraping и fixture capture запрещены. `otc` не начинается до merge/exact audit package.
- Локально: focused `34 passed in 12.19s`, full suite
  `2467 passed, 2 warnings in 251.08s`; Ruff/format (`804 files`), mypy (`20 source files`),
  secret scan и `git diff --check` успешны. Pytest использовал
  `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #147 head `403ec44abee9d0497485ac130b50dc3199351347`; PR-head run `29984554174`
  успешен (jobs `89133465443`/`89133465378`). Merge
  `bf2a44bea889b34689f63495013becae24d050fb`; exact run `29984821509` успешен (jobs
  `89134271091`/`89134271135`), включая dependency audit.
- Только после exact success создан отдельный docs-only worktree перехода к OTC.

## 2026-07-23 — P7 docs-only переход к Фабриканту принят и слит

- Принятый B2B-Center blocker сохраняется в позиции 1 P7; `fabrikant` назначен только следующим
  access-audit target в позиции 2 без access/readiness/fixture/working claim.
- Application/tests/settings/credentials/DB/schema/fixtures/dependencies не меняются. Отдельный
  Фабрикант audit не начинается до merge и успешного exact merge-SHA Quality Gate этого решения;
  `otc`, commercial sections, P8/P9 и production RM-156 не начинаются параллельно.
- Локально: focused `34 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны. Pytest использовал workflow
  `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #146 head `6fa6e3f93a188e39a71c9e9042cf3b41e770364a`; PR-head run `29981527538`
  успешен (jobs `89124142766`/`89124142791`). Merge
  `dfe1f95f194f494b9beb33dc5c6127d31f428ce4`; exact run `29981883362` успешен (jobs
  `89125248024`/`89125248048`), включая dependency audit.
- Только после exact success создан отдельный Фабрикант access-audit worktree.

## 2026-07-23 — Collector P7 B2B-Center access audit принят и слит

- Audit выполнен от принятого boundary merge `e54fd46d6525e378cd90795f35ae144f00fffe31` после fresh
  exact run `29979715877`; application/tests/settings/credentials/schema/dependencies не меняются,
  procurement payloads, documents и fixtures не сохраняются.
- Official web service/API существует, но method catalog, documentation и XML examples доступны
  только после login в Личном кабинете и зависят от договора/тарифа. Public Регламент запрещает
  automated collection без письменного consent Оператора и задаёт ceiling 60 HTTP requests/minute.
- Entitlement/consent, exact endpoint/method/auth and coverage, schema/version, pagination/
  completeness, API rate/retry, timezone/money, retention/reuse и approved fixtures отсутствуют.
  Verdict `BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`; human HTML/login automation, adapter
  и fixture capture запрещены. `fabrikant` не начинается до merge/exact audit package.
- Локально: focused `34 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны. Pytest использовал workflow
  `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #145 head `d4c0f2fb41fe77c5df642884d29016af0cd0442c`; PR-head run `29980582710`
  успешен (jobs `89121318689`/`89121318642`). Merge
  `f7b20a4a5c5d0ee260b04721347c66b8ee2dad2a`; fresh exact run `29980836778` успешен (jobs
  `89122049907`/`89122049924`), включая dependency audit.
- Только после exact success создан отдельный docs-only worktree перехода к Фабриканту.

## 2026-07-23 — docs-only reconciliation границы P6/P7 принят и слит

- Canonical ТЗ имеет приоритет: `gazprombank` остаётся восьмым P6 source, P7 начинается с
  `b2b_center`. Supporting implementation plan исправлен без повторного source slot и без
  изменения identity/accepted history.
- P6 access-audit pass по позициям 1–8 завершён с честными verdicts, но blocked sources не
  объявляются implemented/working и Collector prerequisite не закрывается. `b2b_center` назначен
  только следующим P7 access-audit target; network research начинается после merge/exact.
- Application/tests/settings/credentials/DB/schema/fixtures/dependencies не меняются. Локально:
  focused `34 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy,
  secret scan и `git diff --check` успешны. Pytest использовал workflow
  `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #144 head `ddd3d37a7f13a10d45b29a1c3c5496f38ff9e1e8`; PR-head run `29979195455`
  успешен после controlled rerun failed Python 3.12 job (jobs `89118148283`/`89118148873`). Merge
  `e54fd46d6525e378cd90795f35ae144f00fffe31`; fresh exact run `29979715877` успешен (jobs
  `89118819142`/`89118819085`), включая dependency audit.
- Только после exact success создан отдельный B2B-Center access-audit worktree.

## 2026-07-23 — Collector P6 ЭТП ГПБ access audit принят и слит

- Восьмой и последний по canonical ТЗ P6 audit выполнен от exact order merge
  `cb94e62df7cc7a815693e586b559184868d52e5a`; application/tests/settings/credentials/schema/
  dependencies не меняются, fixtures и procurement payloads не сохраняются.
- Official page явно предназначает RSS стороннему ПО и публикует exact endpoint. Ordinary GET
  current/new address chain заканчивается final `404`; generic robots также запрещает query URLs
  и `/procedures/page`. HTML/query scraping и отдельный account-oriented Trading Portal API не
  используются как replacement.
- Schema/version, section coverage, pagination/completeness, rate/retry, timezone/money, retention
  и approved fixtures не опубликованы. Local verdict
  `BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE`; locally focused `34 passed`, full suite
  `2467 passed, 2 warnings`, Ruff/format (`804 files`), mypy, secret scan и `git diff --check`
  успешны. Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped
  `--basetemp`.
- PR #143 head `8dcfbf6469747fc3e8644761693cc85a076d1b39`; PR-head run `29978156861`
  успешен (jobs `89114212457`/`89114212487`). Merge
  `102aff662f3cd068c13c095cb6470912cc0bfc60`; exact run `29978439856` успешен (jobs
  `89115056696`/`89115056687`), включая dependency audit.
- Только после exact success создан отдельный P6/P7 boundary reconciliation worktree.

## 2026-07-23 — P6 docs-only переход к ЭТП ГПБ принят и слит

- Первые семь P6 sources сохраняют принятые blocker/identity verdicts; ни один не удаляется и не
  считается реализованным. `gazprombank` назначен только следующим access-audit target в исходной
  позиции 8 без access/readiness claim и без network/code changes.
- Application/tests/settings/credentials/DB/schema/fixtures не меняются. Отдельный ЭТП ГПБ audit
  не начинается до merge и успешного exact merge-SHA Quality Gate этого решения; P7 не начинается
  параллельно. Локально: focused `34 passed`, full suite `2467 passed, 2 warnings`;
  Ruff/format (`804 files`), mypy, secret scan и `git diff --check` успешны. Pytest использовал
  workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #142 head `8ad58579c5d9a54aec076741f891f95d06579c41`; PR-head run `29976999580`
  успешен (jobs `89110806182`/`89110806185`). Merge
  `cb94e62df7cc7a815693e586b559184868d52e5a`; exact run `29977374982` успешен (jobs
  `89111932002`/`89111932016`), включая dependency audit.
- Только после exact success создан отдельный ЭТП ГПБ access-audit worktree.

## 2026-07-23 — Collector P6 РТС-тендер access audit принят и слит

- Седьмой P6 audit выполнен от exact order merge
  `ffc2f4e8f8b3c0db502a4a26c2f8ea69b0a7931f`; application/tests/settings/credentials/schema/
  dependencies не меняются, fixtures и procurement payloads не сохраняются.
- Official main и `robots.txt` возвращают Anti-DDoS browser challenge/503; bypass запрещён.
  Section-specific public human cards существуют, но machine API/feed, automation/reuse,
  schema/pagination/rate/timezone/retention contract и approved fixtures не опубликованы.
- Common B2B-РТС group ownership не доказывает shared identity/protocol. Local verdict
  `BLOCKED_EXTERNAL`; locally focused `33 passed`, full suite `2467 passed, 2 warnings`,
  Ruff/format (`804 files`), mypy, secret scan и `git diff --check` успешны. Pytest использовал
  workflow `QT_QPA_PLATFORM=offscreen` и fresh command-scoped `--basetemp`.
- PR #141 head `00c0e6900e8d3390f8858d1fbdf9193695684ccf`; PR-head run `29975868619`
  успешен (jobs `89107358104`/`89107358117`). Merge
  `3944dbd0ec35bc358d5149a9cf005b27884b6570`; exact run `29976202290` успешен (jobs
  `89108357449`/`89108357536`), включая dependency audit.
- Только после exact success подготовлено отдельное решение о переходе к `gazprombank`.

## 2026-07-23 — P6 docs-only переход к РТС-тендер принят и слит

- Первые шесть P6 sources сохраняют принятые blocker/identity verdicts; ни один не удаляется и не
  считается реализованным. `rts_tender` назначен только следующим access-audit target в исходной
  позиции 7 без access/readiness claim и без network/code changes.
- Application/tests/settings/credentials/DB/schema/fixtures не меняются. Локально: focused
  `33 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy, secret scan
  и `git diff --check` успешны. Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh
  command-scoped `--basetemp`.
- PR #140 head `ca7a3c53841336d1cfe544ed5326b7d2160eef7f`; PR-head run `29974875827` успешен
  (jobs `89104418590`/`89104418532`). Merge `ffc2f4e8f8b3c0db502a4a26c2f8ea69b0a7931f`;
  exact run `29975119548` успешен (jobs `89105143244`/`89105143234`), включая dependency audit.
- Только после exact success создан отдельный РТС-тендер access-audit worktree.

## 2026-07-23 — Collector P6 Сбербанк-АСТ access audit принят и слит

- Шестой P6 audit выполнен от exact order merge
  `7d1e728a99c384acd72d3b7b13ab274378fe7d47`; application/tests/settings/credentials/schema/
  dependencies не меняются, fixtures и procurement payloads не сохраняются.
- Official public human 44-ФЗ/223-ФЗ registries существуют. Machine API/feed, permitted
  automation/reuse, stable schema/version, pagination/completeness, rate/retry, timezone/currency/
  exact-money and raw retention contract не опубликованы; robots закрывает document view/download.
- Local verdict `BLOCKED_EXTERNAL`; parser/adapter/fixture/live claim запрещены. Локально: focused
  `33 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy, secret scan
  и `git diff --check` успешны. Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh
  command-scoped `--basetemp`.
- PR #139 head `eb9eb59a14709a42a13a0d8b6422a6e3e1c57ac2`; PR-head run `29973982757`
  успешен (jobs `89101773700`/`89101773723`). Merge
  `642f53bc812593ce2c1d2b1050d7c7e8d8319e2f`; exact run `29974214317` успешен (jobs
  `89102457552`/`89102457455`), включая dependency audit.
- Только после exact success подготовлено отдельное решение о переходе к `rts_tender`.

## 2026-07-23 — P6 docs-only переход к Сбербанк-АСТ принят и слит

- Первые пять P6 sources сохраняют принятые blocker/identity verdicts; ни один не удаляется и не
  считается реализованным. `sber_a` назначен только следующим access-audit target в исходной
  позиции 6 без access/readiness claim и без network/code changes.
- Application/tests/settings/credentials/DB/schema/fixtures не меняются. Локально: focused
  `33 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy, secret scan
  и `git diff --check` успешны. Pytest использовал workflow `QT_QPA_PLATFORM=offscreen` и fresh
  command-scoped `--basetemp`.
- PR #138 head `1ddc2d726a6279ffb94023c89d6d90fc82e2347d`; PR-head run `29972908601` успешен
  (jobs `89098549848`/`89098549930`). Merge `7d1e728a99c384acd72d3b7b13ab274378fe7d47`;
  exact run `29973164497` успешен (jobs `89099325527`/`89099325555`), включая dependency audit.
- Только после exact success создан отдельный Сбербанк-АСТ access-audit worktree.

## 2026-07-23 — ETS/НЭП ↔ Fabrikant identity ownership решение принято и слито

- Common АО «ЭТС» ownership/domain migration подтверждены, но section/protocol boundary между
  `44.fabrikant.ru` и `fabrikant.ru` не доказана machine contract evidence.
- Both canonical IDs remain disabled placeholders; no guessed alias, persisted-ID migration or
  duplicate adapter. Future implementation has one operator owner with section profiles only when
  audited differences require them.
- Application/tests/settings/credentials/DB/schema/fixtures не меняются. Focused `33 passed`,
  neighboring contour `15 passed`, workflow-compatible prefix `965 passed`, final full suite
  `2467 passed, 2 warnings`; Ruff/format (`804 files`), mypy, secret scan и `git diff --check`
  успешны. Первый full attempt без workflow `QT_QPA_PLATFORM=offscreen` завершился native Windows
  `0xc0000374`; exact contour и оба workflow-compatible прогона прошли без изменения code/tests.
  PR #137 head `e3550871a95f0c103ee7f6e2799ccc120c1d2ba4`; PR-head run `29971869854` успешен
  (jobs `89095401781`/`89095401782`). Merge `cd39b8e82d2ce208aa4498462c545f0fab894044`;
  exact run `29972112388` успешен (jobs `89096127682`/`89096127713`), включая dependency audit.
  Только после exact success подготовлено отдельное решение о переходе к `sber_a`.

## 2026-07-23 — Collector P6 ETS/НЭП access audit принят и слит

- Пятый P6 audit выполнен от exact order merge
  `195f4d2e22d12ca36e1c8329e241bef9c8f8832e`; application/test code, identities, aliases,
  settings, credentials, schema, fixtures and live calls не менялись.
- Official migration `etp-ets.ru` → `44.fabrikant.ru` and common АО «ЭТС» ownership prove that
  canonical `ets_nep` and `fabrikant` now describe one operator platform. A second adapter would
  violate the duplicate-owner contract; separate identity re-audit is required.
- Public cards exist, but API/feed, automation/reuse permission, stable schema/pagination/rate and
  raw retention are not published; robots disallows XML/CSV exports and file/download paths.
  Local verdict: `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`; no fixtures/code/live claim.
- Локально: focused `33 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны.
- PR #136 head `9765e7d6bc3c2ca59ac0647f565bf1aab12849ef`; PR-head `29970355532`, merge
  `a3ac0d88759002468aa6a3d5cb5c6ba887ba9e26`, exact `29970713352`; both matrix jobs successful.

## 2026-07-23 — P6 docs-only переход к ETS/НЭП принят

- ZakazRF, Roseltorg, Rad и TekTorg сохранены в позициях 1–4 P6 со статусом
  `BLOCKED_EXTERNAL`; `ets_nep` назначен только следующим последовательным access-audit target
  без access/readiness claim и без network/code changes.
- Локально: focused `33 passed`; final full suite `2467 passed, 2 warnings`; Ruff/format
  (`804 files`), mypy, secret scan и `git diff --check` успешны. Первый full attempt имел один
  невоспроизводимый native Windows/Qt `0xc0000374`; exact test, четыре повтора файла и final full
  suite прошли без изменения кода/tests/thresholds.
- PR #135 head `26e705f7c72d742dd0b4570cdd90084ae9f95c85`; PR-head run `29969146389` успешен
  (jobs `89087096040`/`89087095959`). Merge `195f4d2e22d12ca36e1c8329e241bef9c8f8832e`;
  exact run `29969484418` успешен (jobs `89088142031`/`89088142008`), включая dependency audit.
- Только после exact success создан отдельный ETS/НЭП audit worktree.

## 2026-07-23 — Collector P6 TekTorg access audit принят и слит

- Четвёртый P6 provider package выполнен от exact order-decision merge
  `22f5a530f6ca32ead5b76f102576fa36b559dac5` и ограничен official read-only
  access/legal/contract audit. Application/test code, schema, dependencies, settings,
  credentials, fixtures и procedure live calls не менялись.
- Official `api.tektorg.ru` публикует unauthenticated discovery, public SOAP procedure export,
  WSDL, filters, page totals and section/type dictionaries. Endpoint не угадан. Но rate/retry,
  page maximum/snapshot consistency, schema/version lifecycle, exact timezone/currency/money
  semantics and raw retention/reuse permission не опубликованы; approved fixtures отсутствуют.
  `tek_torg` локально классифицирован как `BLOCKED_EXTERNAL`, disabled/not configured.
- Локально: focused `33 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны.
- PR #134 head `44e2975237899b6672681323f8a36d457fd55825`; PR-head run `29967886571` успешен
  (jobs `89083246018`/`89083245976`). Merge commit
  `30f6fb1c318d4c0ddc9b10d1dace6cb429c93e8f`; exact merge-SHA run `29968220150` успешен
  (jobs `89084249165`/`89084249132`), включая dependency audit. Только после этого подготовлено
  отдельное docs-only решение о следующем P6 access-audit target `ets_nep`.

## 2026-07-23 — P6 docs-only переход к TekTorg принят

- ZakazRF, Roseltorg и Rad сохранены в позициях 1–3 P6 со статусом `BLOCKED_EXTERNAL`; TekTorg
  назначен только следующим последовательным access-audit target без access/readiness claim и
  без network/code changes.
- PR #133 head `4dbd9b1cdfe3a233c97bab2d9f2c58171b3ee10d`; PR-head run `29966420486` успешен
  (jobs `89078811152`/`89078810946`). Merge `22f5a530f6ca32ead5b76f102576fa36b559dac5`;
  exact run `29966853365` успешен (jobs `89080134032`/`89080134075`), включая dependency audit.
- Только после exact success создан отдельный TekTorg access-audit worktree.

## 2026-07-23 — Collector P6 Rad access audit принят и слит

- Третий P6 provider package выполнен от exact order-decision merge
  `4e5adfec20d7ad95ac2fe4decd005b0041e60909` и ограничен official read-only
  access/legal/contract audit. Application/test code, schema, dependencies, settings,
  credentials, fixtures и live calls не менялись.
- Official public procurement sections/cards подтверждены, но operator agreement требует
  письменного разрешения для scripts/access/collection и запрещает automated extraction/copying.
  Procurement API/feed/schema/rate/retention contract и approved fixtures не найдены; `rad`
  честно принят как `BLOCKED_EXTERNAL`, disabled/not configured.
- Локально: focused `15 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны.
- PR #132 head `6ca84f2f523dce6f853cfb919420d6e36caca06e`; PR-head run `29965371309` успешен
  (jobs `89075592391`/`89075592367`). Merge commit
  `38fe2d75f80beb544e9b5a7a2d18462963c4f232`; exact merge-SHA run `29965734080` успешен
  (jobs `89076696779`/`89076696809`), включая dependency audit. Только после этого подготовлено
  отдельное docs-only решение о следующем P6 access-audit target `tek_torg`.

## 2026-07-23 — P6 docs-only переход к Rad принят

- ZakazRF и Roseltorg сохранены в позициях 1–2 P6 со статусом `BLOCKED_EXTERNAL`; Rad назначен
  только следующим последовательным access-audit target без access/readiness claim и без
  code/network changes.
- PR #131 head `c4df48df5bfbc4fc1d2dc55a8fedd5fd6ff66803`; PR-head run `29963756719` успешен
  (jobs `89070568520`/`89070568448`). Merge `4e5adfec20d7ad95ac2fe4decd005b0041e60909`;
  exact run `29964235838` успешен (jobs `89072056995`/`89072057051`), включая dependency audit.
- Только после exact success создан отдельный Rad access-audit worktree.

## 2026-07-23 — Collector P6 Roseltorg access audit принят и слит

- Второй P6 provider package выполнен от exact order-decision merge
  `862dac27b38968f235f831402139980e17cc90f3` и ограничен official read-only
  access/legal/contract audit. Application/test code, schema, dependencies, settings,
  credentials, fixtures и live calls не менялись.
- Public HTML search/detail и robots indexability подтверждены, но procurement API/feed либо
  явно разрешённый stable HTML contract, data-use/raw-retention permission, schema/version/rate
  rules и approved fixtures не найдены. API отдельного ЭДО не является tender API; `roseltorg`
  честно принят как `BLOCKED_EXTERNAL`, disabled/not configured.
- Локально: focused `18 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны.
- PR #130 head `ebbdcf640fa87162db136147d9fc3be4420eaa29`; PR-head run `29961223536` успешен
  (jobs `89062439998`/`89062440086`). Merge commit
  `aa9825b5b4d515958c3b02c00d63a215a5af8b27`; exact merge-SHA run `29961900274` успешен
  (jobs `89064615441`/`89064615340`), включая dependency audit. Только после этого подготовлено
  отдельное docs-only решение о следующем P6 access-audit target `rad`.

## 2026-07-23 — P6 docs-only переход к Roseltorg принят

- ZakazRF сохранён первым P6 source и `BLOCKED_EXTERNAL`; Roseltorg назначен только следующим
  последовательным access-audit target без access/readiness claim и без code/network changes.
- PR #129 head `6df486b31d0953ae140be2c03939bab848b757b3`; PR-head run `29959486498` успешен
  (jobs `89056801850`/`89056801718`). Merge `862dac27b38968f235f831402139980e17cc90f3`;
  exact run `29959911671` успешен (jobs `89058199578`/`89058199554`), включая dependency audit.
- Только после exact success создан отдельный Roseltorg access-audit worktree.

## 2026-07-23 — Collector P6 ZakazRF access audit принят и слит

- Первый P6 provider package выполнен от exact P5 merge
  `e9a522fc750e0893b46b0c6028c4a61cdbb9b26f` и ограничен официальным read-only
  access/legal/contract audit. Application code, schema, dependencies, settings, credentials,
  fixtures и live calls не менялись.
- Официальный public HTML registry подтверждён, но API/feed/data-use contract,
  pagination/rate/schema/retention rules и approved fixtures не найдены. `zakaz_rf` честно принят
  как `BLOCKED_EXTERNAL`, disabled/not configured; guessed endpoint/adapter не создавался.
- Локально: focused `18 passed`, full suite `2467 passed, 2 warnings`; Ruff/format (`804 files`),
  mypy, secret scan и `git diff --check` успешны.
- PR #128 head `2af262d9575f6a9947a51c866d249f28530cec97`; PR-head run `29956095948` успешен
  (jobs `89045424680`/`89045424729`). Merge commit
  `14bc30300fa40a4008b35df7897d725e682e2437`; exact merge-SHA run `29958227968` успешен
  (jobs `89052589841`/`89052589770`), включая dependency audit. Только после этого подготовлено
  отдельное docs-only решение о следующем P6 access-audit target.

## 2026-07-22 — Collector P5 provider identity/catalog принят и слит

- P5 создан от exact P4 Mos Supplier merge `b4704480010a363e02ad80fe579d5c836cd04509`:
  audit `69e83f1`, strict expected-red tests `83d048d`, implementation `62e6962`, acceptance docs
  `70ce280`.
- Приняты exact 13 canonical provider IDs, три audited `_commercial` legacy aliases, settings
  schema 7 и Collector DB schema 16 alias registry. Historical rows не переписаны; новые
  `zakaz_rf`, `rad`, `ets_nep` и прочие non-reference identities остались disabled/not configured
  без guessed endpoints, fixtures или live calls.
- Full suite `2467 passed, 2 warnings in 251.10s`; Ruff/format (`804 files`), mypy, secret,
  offline/migration/composition/build/frozen/RM-155 gates успешны. Dependencies не менялись.
- PR #127 head `70ce28001b0be0bfcd19937ba042ac1555919386`; PR-head run `29951810601` успешен
  на Python 3.12/3.13 (jobs `89031089368`/`89031089332`). Merge commit
  `e9a522fc750e0893b46b0c6028c4a61cdbb9b26f`; exact merge-SHA run `29952451892` успешен
  (jobs `89033211301`/`89033211251`), включая dependency audit. Только после этого начат
  отдельный P6 `zakaz_rf` access audit.

## 2026-07-22 — Collector P4 Mos Supplier reference adapter принят и слит

- Второй P4 package создан от exact EIS merge `300385108082746ac8818dad19104f57618366a9`:
  test-first `31bc13c`, implementation `e3fedb6`. Existing provider/engine/repository/config/keyring
  paths переиспользованы без нового runtime, DB owner, migration или dependency.
- `mos-supplier-api-v1` честно ограничен одним документированным authenticated response: серверная
  пагинация не подтверждена и не угадана. Без token сеть не выполняется; readiness остаётся
  `IMPLEMENTED_OFFLINE` до отдельно разрешённой live verification.
- Accepted page, raw search artifact и checkpoint commit-coupled existing Collector transaction;
  card/document/rejected bodies сохраняются content-addressed с sanitized public errors.
- Target `9 passed`, regression contour `37 passed`, full suite `2458 passed, 2 warnings in
  259.43s`; secret, Ruff/format (`802 files`), mypy, offline/migration/bootstrap/build/frozen/RM-155
  gates успешны. Локальный dependency audit заблокирован политикой экспорта inventory и остаётся
  обязательным PR-head/exact gate; dependencies не менялись.
- Два stop-line performance diagnostics сохранены как host-load variance evidence. Immutable EIS
  control прошёл, затем Mos reproduction прошёл: p50 `6 962.190 ms`, p95 `7 117.944 ms`, delta
  `-12.0848%`, RSS `62 406 656`; 25 cycles без resource growth, cancellation `16.407 ms`.
- PR #126 head `1943d57dc944490d1fd30051be289624b22d7f4b`; PR-head run `29946701032` успешен.
  Merge commit `b4704480010a363e02ad80fe579d5c836cd04509`; exact merge-SHA run `29947263908`
  успешен на Python 3.12/3.13; dependency audit прошёл в обоих matrix jobs. Только после этого
  создан отдельный provider identity/catalog P5 worktree.

## 2026-07-22 — Collector P4 EIS reference adapter принят и слит

- P4 EIS создан от exact P3 merge `cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`: test-first
  `a0842a2`, implementation `c4a4c7a`. Новый engine/parser/repository не создан; существующий
  `AsyncEisTenderProvider` переведён на shared bounded page/resume/artifact contract.
- `eis-public-html-v1` ограничивает collection 20 pages/500 items per page/50 MiB; checkpoint и
  search artifact metadata commit-coupled с accepted page до следующего HTTP request. Снят последний
  strict xfail `C-CP-001`; CAPTCHA/access-denied/structure drift остаются fail closed.
- Search/detail/document bodies получают content-addressed SHA-256 evidence и sanitized metadata;
  connection mode остаётся `public_html_async`, official API не заявлен. Live canary не запускался,
  readiness честно остаётся `IMPLEMENTED_OFFLINE`.
- Focused contour `82 passed`; full suite `2449 passed, 2 warnings in 258.23s`; secret,
  Ruff/format (`800 files`), mypy, offline/migration/bootstrap/build/frozen/RM-155 gates успешны.
- Controlled exact-data reproduction: p50 `8 939.589 ms`, p95 `9 040.632 ms`, regression
  `11.6627%`, RSS `53 055 488`; 25 cycles без resource growth, cancellation `16.427 ms`. Первый
  near-threshold time diagnostic и immutable P3 RSS control сохранены как host variance evidence;
  thresholds/fixture/code не ослаблялись.
- PR #125 head `db69f47891e2ea71187d26ad84e084c7de45d440`; PR-head run `29943116366` успешен.
  Merge commit `300385108082746ac8818dad19104f57618366a9`; exact merge-SHA run `29943599187`
  успешен на Python 3.12/3.13. Только после него начат отдельный Mos Supplier package.

## 2026-07-22 — Collector P3 shared foundation принят и слит

- P3 создан от exact P2 merge `83899900fd2913eefd0ad04398e266f4a6b64437`: characterization
  `f7dd6a2`, shared foundation `b7f5aaf`, GC guards `523ac63`, bounded production optimization
  `9202290`.
- Общий page/artifact/checkpoint contract, schema 15 migration/backup/restore, atomic page receipt,
  process-wide lease, truthful statuses и interactive/scheduled budgets реализованы без второго
  engine, repository или DB owner. Последующий P4 EIS package снял последний xfail `C-CP-001`.
- Controlled exact-data 10k acceptance: p50 `9 506.289 ms`, p95 `9 588.611 ms`, regression
  `18.4309%`, RSS delta `64 634 880 bytes`; 25 cycles не оставили tasks/threads/handles/temp,
  cancellation `16.724 ms`.
- Exact optimization commit full suite: `2441 passed, 1 xfailed, 2 warnings in 237.18s`; secret,
  Ruff/format (`798 files`), mypy, offline/migration/import/bootstrap/build/frozen/RM-155 gates
  зелёные. PR #124 head `d9b89a68d2f82aab6a0bcb0ba4f87daafae3acb4`; PR-head run
  `29939287327` успешен. Merge commit `cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`; exact
  merge-SHA run `29939811499` и jobs `88990529239` (3.12)/`88990529142` (3.13) успешны.

## 2026-07-22 — Collector P2 expected-red contracts зафиксированы до implementation

- P2 PR #123 на head `ef529fabcd80e8deea61af14bacebe362a8f4109` слит merge commit
  `83899900fd2913eefd0ad04398e266f4a6b64437`. PR-head Quality Gate `29928510935` и exact
  merge-SHA run `29929323692` успешны на Python 3.12/3.13; exact jobs: `88954536449`
  (Python 3.12) и `88954536180` (Python 3.13).

- P1 PR #122 на head `a24fdb7bc5ad823711f3b41b542403c1bc96d7d4` слит merge commit
  `6593fb2518d724c9bdde3ea46c9de84ff63b1b03`. PR-head Quality Gate `29925849223` успешен:
  Python 3.12 job `88942668666`, Python 3.13 job `88942668628`.
- Exact P1 merge-SHA push-run `29926327653` успешен на exact `6593fb2`: Python 3.12 job
  `88944312496`, Python 3.13 job `88944312478`; full suite, dependency audit и required Windows
  gates прошли.
- P2 создан отдельной веткой `codex/pre-rm156-collector-correctness-contracts` от exact P1 merge.
  Tests-only contract commit `c7c11ae` не меняет `app/`, schema, dependencies, settings или
  production fixtures.
- Strict expected-red matrix содержит 14 contracts: 11 отсутствующих boundaries и 3 уже
  существующих passing guards. Direct `--runxfail` дал `11 failed, 3 passed in 9.12s`; все failures
  относятся к целевым assertions, setup/import/network failures отсутствуют.
- Regular P2 file: `3 passed, 11 xfailed`; focused neighbors: `27 passed, 11 xfailed`; full suite:
  `2414 passed, 11 xfailed, 2 warnings in 290.81s`. Mandatory pair `2 passed`, migrations `5`,
  bootstrap `1`, build/frozen `9`; secret scan, Ruff/format (`795 files`), mypy, RM-155 guard и
  dependency audit успешны.
- P2 остался tests/docs-only. После merge и exact merge-SHA success начат отдельный P3 shared
  page/artifact/checkpoint foundation; provider identity/adapters и production RM-156 не
  начинаются параллельно.

## 2026-07-22 — Collector P1 audit/contract/plan подготовлен до application changes

- Governance P0 PR #121 слит merge commit
  `c20bed32492dc80b48748c79a87da73107533ddd`; exact merge-SHA Windows Quality Gate run
  `29922814088` успешен на Python 3.12/3.13.
- P1 выполнен в отдельной ветке `codex/pre-rm156-collector-audit` от exact P0 merge SHA. Audit
  commit `6cc9b7e` и contract commit `39057de` созданы раздельно до expected-red/application edits;
  implementation и rollback plans зафиксированы этим docs-only package.
- Runtime inventory сохраняет единственные owners: `CollectorRunSession`,
  `CollectorNetworkRuntime`, `AsyncProviderSearchEngine`, `CollectorService`,
  `CollectorStateRepository`/`CollectorSchemaMigrator`, canonical provider catalog и
  `ProviderEnablementRepository`. Legacy sync catalog, split commercial settings и EIS debug
  snapshots классифицированы как transition/migration/debug residuals, не новые owners.
- Critical gaps: engine не исполняет pagination; EIS/Mos checkpoints продвигаются до durable batch
  commit; zero-success/timeout проецируются в `PARTIAL`; typed commit/replay checkpoint и raw
  artifact owner отсутствуют; provider identity неполна; schema version 14 не имеет explicit
  sequential migration/backup/restore contour.
- Readiness matrix фиксирует 13 target built-ins: EIS и Mos Supplier имеют offline implementations,
  три источника отсутствуют, три имеют перевёрнутую legacy alias identity, остальные являются
  disabled access-pending placeholders. Ни один placeholder не объявлен working.
- Clean baseline: focused `107 passed in 41.39s`, mandatory pair `2 passed`, migration `5 passed`,
  bootstrap `1 passed`, build/frozen `9 passed`, full `2411 passed, 2 warnings in 264.42s`; secret
  scan, Ruff/format (`794 files`), mypy (20 files), RM-155 guard и dependency audit успешны.
- Same-host 10k normalize/dedup baseline после warm-up: n=5, p50 `7583.978 ms`, nearest-rank p95
  `8096.375 ms`, sampled RSS delta `33,087,488 bytes`. P1 budgets и measurement caveats записаны в
  audit; 20-sample + tracemalloc attempt, превысивший 240 seconds, не выдан за успешный результат.
- P1 остаётся docs-only. Следующий шаг после merge/exact merge-SHA gate — отдельный P2 strict
  expected-red tests-only package; production RM-156, RM-157 и RM-158 остаются заблокированы до
  Collector closeout.

## 2026-07-22 — Collector назначен обязательным prerequisite RM-156

- Решением владельца production-реализация модели контрагента RM-156 приостановлена до
  завершения промышленного многоплощадочного Collector prerequisite. Причина — сначала требуется
  закрыть аудит, единый adapter contract, честную readiness-модель, pagination/checkpoints,
  provenance, partial-failure, security/legal и offline/live verification gaps существующего
  Collector. Полное ТЗ:
  [`PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md`](PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md).
- Collector не является новым или параллельным RM. Нумерация RM-001–RM-200 не изменяется,
  RM-156 остаётся единственным каноническим `IN PROGRESS`, RM-157–RM-200 остаются `PLANNED`.
- Этот P0 ограничен документацией. До его merge application-код Collector не изменяется; разрешены
  только read-only аудит, исследование публичной документации, подготовка ТЗ и offline fixtures без
  секретов.
- После merge P0 работа продолжается отдельным P1 audit/contract/plan пакетом до expected-red и
  implementation. После полного prerequisite обязателен отдельный closeout, возвращающий RM-156
  в production work.
- Влияние на порядок: production RM-156 приостановлен; RM-157 (поиск по ИНН) и RM-158
  (архитектура источников) не начинаются до Collector closeout и последующего завершения RM-156 по
  Definition of Done. Их scope и номера не меняются.
- Docs-only [PR #121](https://github.com/lykay86-dotcom/CorterisTenderAI/pull/121) создан из ветки
  `codex/pre-rm156-collector-governance`, основанной на `origin/main`
  `d007460f72bccc9486d1f330a865b74f15a6d368`.

## 2026-07-21 — RM-155 завершён, RM-156 активирован

- Audit-first package committed before cleanup and classified 32 compatibility candidates:
  9 `REMOVE`, 2 `MIGRATE`, 21 `KEEP`, 0 `DEPRECATE`, 0 `BLOCKED`. Every item records exact
  runtime/import/test/history/settings/frozen/public consumers, replacement, owner and rollback.
- Controlled retirement removed only obsolete `app.ui.main_window` and its re-exports, the
  same-object `quotes_page`/`estimates_page` aliases, their bootstrap fallbacks and the unused
  compatibility search shim. One `ModernMainWindow`, typed router and canonical tender/workflow
  pages remain; no duplicate production owner was introduced.
- J01–J16 and RM-142–RM-154 cross-stage gates pass. Retained residuals are the supported route,
  settings, action/object-name, public/data migration, identity/table, accessibility, performance
  and visual contracts listed in the inventory; there are no deprecated or blocked residuals.
- Locally: final full pytest `2411 passed, 2 warnings in 207.24s`, neighboring RM-127–154 contour
  `840 passed`; Ruff/format (`794 files`), required mypy, secret/offline/migration/composition/
  build/dependency guards pass. RM-107 decision integrity contour passed 37 tests.
- Fresh 20-sample RM-153 p95 guards and 25-cycle resource budgets pass. A controlled same-session
  A/B measured exact baseline shutdown p95 13.507 ms and feature 8.696 ms, confirming no cleanup
  regression without relaxing the 12 ms guard.
- Actual one-file EXE is 83,683,131 bytes, SHA-256
  `044B35A3D8D73132A603073FBB0F8456010950B19CB5696C2EFBB8D7BC41F7A0`; all nine isolated frozen
  checks pass. RM-152 native evidence remains truthful at `0 PASS`, `4 BLOCKED`, `29 NOT_EXECUTED`.
- Feature PR #118 head `c741ba6a39750436fa34ffc2237bd1c264466745` merged as
  `63a85b4cff5e2de5b53e4fad6dcfb091371200bf`. PR-head run `29832379070` passed jobs
  `88640055860`/`88640055889`.
- Exact merge-SHA run `29845412052` confirmed that exact head: Python 3.12 job `88684644919`
  (`2411 passed`, strict visual 14/14 `PASS`) and Python 3.13 job `88684644939` (`2411 passed`);
  dependency audit and every required step succeeded on both versions.
- No dependency, DB/schema/settings migration, telemetry, persistent cache or decision authority
  changed. Rollback is revert of the feature merge without DB/data/settings downgrade.
  `UI-141-017` and the RM-141–RM-155 redesign sequence are closed. RM-155 is `DONE`; RM-156 is the
  sole `IN PROGRESS` stage, while RM-157–RM-200 remain `PLANNED`.

## 2026-07-21 — RM-154 завершён, RM-155 активирован

- Audit/state inventory/renderer decision/contract/expected-red/plan packages establish a single
  deterministic visual QA path without a second shell/router/theme/chart/table/dialog/business
  owner. Expected red was `6 failed, 3 passed`, with all six missing boundaries intended.
- The accepted catalog contains 14 normalized PNGs across seven representative dark/light pairs.
  Canonical renderer fingerprint is
  `f1cd92373456028fd9360b3a032ef9b8d5784dc90d00abad4080d404db0dba56`; strict RGB comparison
  has zero tolerance and no masks. Three-repeat stability and deliberate token/layout regression
  detection pass.
- Candidate creation and baseline import are separated: canonical update requires explicit phrase,
  reviewer and reason. Synthetic fixtures read no network, keyring, production DB, user settings,
  live AI or real tender data; privacy/path/hash/size/package guards pass. Artifact retention is 14
  days through pinned official upload-artifact v6.
- Locally: focused `30 passed in 40.44s`, full pytest
  `2378 passed, 2 warnings in 199.01s`, RM-153 guards `9 passed in 13.20s`; secret scan,
  design/UI audits, Ruff/format (`788 files`), required mypy, RM-154 Bandit contour and dependency
  audit pass. Real one-file EXE SHA-256 is
  `46c199c7b9792e2d4686e709c419135cf475983e7108dc420967897e2565db92`; all nine frozen self-test
  checks pass.
- RM-152 native evidence remains truthful at `0 PASS`, `4 BLOCKED`, `29 NOT_EXECUTED`; offscreen
  goldens do not certify native Windows/DPI behavior.
- Feature PR #116 on head `109f084aaf84cd907b849d17635bb7cfad1d97ab` merged as
  `40f0e327d0d485b93e93f39bab1d838e584b8914`.
- Final PR-head Quality Gate `29822184296` passed: Python 3.12 job `88607135547`, Python 3.13 job
  `88607135493`. Exact merge-SHA run `29823579968` confirmed that exact head: Python 3.12 job
  `88611629793` (`2378 passed`, strict visual 14/14 `PASS`) and Python 3.13 job `88611629760`
  (`2378 passed`); dependency audit and every required step are successful.
- The only CI annotations are non-blocking official-actions Node.js 20/24 migration notices.
  DB/schema/migration, production dependencies, RM-107 score/recommendation/critical stop-factor
  priority and RM-152/RM-153 guards are unchanged. Rollback is the feature merge revert without
  DB/data/settings downgrade. RM-154 is `DONE`; RM-155 is the sole `IN PROGRESS` stage, while
  RM-156–RM-200 remain `PLANNED`.

## 2026-07-21 — RM-153 завершён, RM-154 активирован

- Audit/contract/plan, characterization, expected-red and deterministic benchmark evidence cover
  shell construction/first paint/shutdown, routing, dashboard, theme, table, chart and bounded
  resource lifecycle without a second shell/router/theme/table/chart/lifecycle owner.
- One monotonic theme epoch scopes repolish to shell chrome and the active page; stale hidden pages
  synchronize through the existing route owner before exposure. No new timer, thread, cache,
  persistence, telemetry, dependency, DB/settings schema or migration was introduced.
- Post p95 improved shell construction 43.7%, first paint 32.3%, page switching 23.9%, dashboard
  update 47.0%, theme switching 74.6% and chart update 16.9%; table filtering changed +2.8% and
  remained inside its 155 ms guard. Fresh 25-cycle resource counts have non-positive growth.
- Eight-page dark/light inspection passed. Owner native confirmation on 2026-07-21 passed responsive
  page switching, absence of white strips after light/dark switching and normal native close.
- Locally: focused/neighboring `39 passed`, final focused `13 passed`, full pytest
  `2354 passed, 2 warnings in 193.39s`; secret scan, design audit, Ruff/format (`775 files`), mypy,
  workflow smokes and dependency audit passed.
- Feature PR #114 on head `ecff610e77bebcbec316dc5db1888ec1894dcfe9` merged as
  `1e8ddf02177a460e14151c7482d5e1cd7dc8e5ad`.
- PR-head Quality Gate `29785396286` passed: Python 3.12 job `88495726494`, Python 3.13 job
  `88495726570`. Exact merge-SHA run `29787372667` confirmed
  `headSha=1e8ddf02177a460e14151c7482d5e1cd7dc8e5ad`: Python 3.12 job `88501750635`, Python
  3.13 job `88501750646`; full suite, dependency audit and every required step are `success`.
- The only CI annotations are non-blocking official-actions Node.js 20/24 migration notices.
  DB/schema/migration, dependencies, provider/network/AI/keyring/domain paths and RM-107
  score/recommendation/critical stop-factor priority are unchanged. Rollback is the feature merge
  revert without DB/data/settings downgrade. RM-153 is `DONE`; RM-154 is the sole `IN PROGRESS`
  stage, while RM-155–RM-200 remain `PLANNED`.

## 2026-07-20 — RM-152 завершён, RM-153 активирован

- Audit/contracts, characterization, expected-red and implementation packages established one
  shell focus chain, table Tab-release, safe focus restore, accessible metadata, focus styling,
  geometry clamp, contrast inventory and fail-closed native evidence validation without a second
  shell, router, lifecycle, table, chart, operation or business owner.
- Dark-theme white fallback strips and Russian safe-feedback mojibake were reproduced, fixed and
  guarded. The exact frozen artifact was observed at representative 1920x1080 100/125/150%, with
  Narrator and High Contrast; scale and High Contrast were restored after the runs.
- The native matrix remains truthful: `0 PASS`, `4 BLOCKED`, `29 NOT_EXECUTED`. Owner decision
  `RM152-OWNER-EXCEPTIONS-2026-07-20` names all 33 cells with exact environment, reason, residual
  risk and retained status. The strict validator rejects missing, malformed, duplicate, unknown,
  status-mismatched or `PASS` exceptions.
- Locally: owner-exception/static `20 passed`, stop-factor contour `8 passed`, full pytest
  `2345 passed, 2 warnings in 197.56s`; secret scan, strict RM-152 gate, Ruff/format (`772 files`),
  mypy, offline/migration/import/composition/build/frozen smokes and dependency audit passed.
- Final closeout EXE built with PyInstaller 6.21.0 / Python 3.12.7 passed nine isolated self-test
  checks; SHA-256 is `5BED2D3F30AE6917F911800FBB85D7679BFBA6CEBB76F6F98F6B73376EBC2719`.
- Feature PR #112 on head `ae70c0ae5ee5fff0a1bcf374361d82d80bfb329a` merged as
  `5f20df74b89fcf6d67c7c79faa2e8cceca4b206b`.
- PR-head Quality Gate `29776619427` passed: Python 3.12 job `88467423008`, Python 3.13 job
  `88467423174`. Exact merge-SHA run `29777125490` confirmed
  `headSha=5f20df74b89fcf6d67c7c79faa2e8cceca4b206b`: Python 3.12 job `88469119363`, Python
  3.13 job `88469119432`; full suite, dependency audit and every required step are `success`.
- The only CI annotations are non-blocking official-actions Node.js 20/24 migration notices.
  DB/schema/migration, dependencies, provider/network/AI/keyring/domain paths and RM-107
  score/recommendation/critical stop-factor priority are unchanged. Rollback is the feature merge
  revert without DB/data/settings downgrade. RM-152 is `DONE`; RM-153 is the sole `IN PROGRESS`
  stage, while RM-154–RM-200 remain `PLANNED`.

## 2026-07-20 — RM-151 завершён, RM-152 активирован

- Audit 30 operation groups и восемь обязательных pre-production contract/plan документов
  зафиксированы commit `c64f3c6`; characterization — `abeeecd`, expected-red — `0f91d94`,
  Qt-free core — `b719417`, representative owner adapters — `c233087`, bounded performance
  evidence — `627faf8`, acceptance и feature head — `dfa7701`.
- Один immutable Qt-free episode contract сохраняет RM-140 states, fail-closed transitions,
  retry/cancel/close и stale/late guards. Allowlist-first safe feedback скрывает raw exception,
  secrets, paths, URL query/fragment, traceback, markup и control/bidi markers, но сохраняет
  actionable bounded diagnostics по opaque correlation ID.
- Schema-v1 notification adapter переиспользует единственный существующий scheduler repository;
  exact identity/freshness, dedupe/read/dismiss/action и announcement coalescing проверены без
  второго lifecycle, scheduler, notification, shell, crash или support owner.
- Search, dashboard, document/analysis/AI/score/provider, workflow, crash/support boundaries
  адаптированы без переноса business work и без изменения RM-107 decision/critical priority.
- Локально: focused `42 passed`, neighboring `35 passed`, full pytest
  `2318 passed, 2 warnings in 138.70s`; secret scan, RM-151 boundary guard, Ruff/format
  (`761 files`), mypy, offline/migration/import/composition/build/frozen smokes, benchmark и
  dependency audit успешны.
- Benchmark 0/1/100/1k/10k не вводит arbitrary threshold: safe feedback остаётся одним bounded
  output, announcements ограничены 12 updates, active retention после terminal равен нулю, а 1000
  duplicate legacy notifications сохраняются один раз.
- Feature PR #110 на head `dfa7701db8c669a1f095604671f615aa8c38d4b5` слит merge commit
  `7176f8542357f91b7d5283bd0b6167efcc63982e`.
- PR-head Quality Gate `29710971738` успешен: Python 3.12 job `88254690838`, Python 3.13 job
  `88254690835`. Exact merge-SHA run `29711141067` подтверждён с
  `headSha=7176f8542357f91b7d5283bd0b6167efcc63982e`: Python 3.12 job `88255104161`, Python
  3.13 job `88255104196`; full suite, dependency audit и все обязательные steps — `success`.
- Единственные CI annotations — non-blocking official-actions Node.js 20/24 migration notices.
  DB/schema/migration, dependencies, notification storage schema, provider/network/AI paths и
  RM-107 score/recommendation/critical stop-factor priority не изменены. Native Narrator, physical
  keyboard/high-contrast/DPI inspection остаются `NOT_EXECUTED` и переданы RM-152. Rollback —
  revert feature merge без DB/data/settings downgrade. RM-151 переведён в `DONE`; RM-152 назначен
  единственным `IN PROGRESS`, RM-153–RM-200 остаются `PLANNED`.

## 2026-07-20 — RM-150 завершён, RM-151 активирован

- Audit 35 pre-production product table sites и решения `migrate=11`, `keep=12`, `defer=12`
  зафиксированы commit `6c79157` вместе с девятью обязательными contract/plan документами до
  production code; characterization — `efd9402`, expected-red — `a9ba57d`, implementation —
  `0e90130`, acceptance regression fix — `3e37a7c`, local evidence — `4f432cb`.
- Один Qt-free immutable `app.ui.tables` contract и reusable Qt adapters закрепили stable
  surface/row/column/revision identity, typed Decimal sort/filter с ID tie-break, exact
  selection/action validation, loading/empty/error/partial sibling states, accessibility roles и
  visible-snapshot export parity. 11 representative surfaces мигрированы без нового business,
  repository, router или dependency owner; 24 keep/defer решения остаются явными.
- Exact target сохраняется across refresh/sort/filter/recalculation; missing identity снимает
  selection вместо adjacent-row fallback. RM-107 decision/critical priority, RM-148 financial
  exactness и RM-149 tender identity/action ownership не изменены.
- Локально: focused `31 passed`, deterministic hash-seed contours `22 + 22 passed`, registry guard
  `18 passed`, full pytest `2276 passed, 2 warnings in 151.15s`; secret scan, Ruff/format
  (`744 files`), mypy, offline/migration/import/composition/build/frozen smokes и dependency audit
  успешны.
- 0/100/1k/10k benchmark на Windows Python 3.12.7/PySide6 6.11.1 не вводит arbitrary threshold.
  На 10,000 rows typed Decimal sort p95 улучшен с `2295.315 ms` до `90.907 ms`; missing-text
  filter p95 `137.449 ms` ниже RM-141 historical `148.005 ms`. Native Narrator/physical
  keyboard/DPI inspection отмечен `NOT_EXECUTED` и остаётся RM-152 scope.
- Feature PR #108 на head `4f432cbe650c76994ba6c44f62685a20fb5ed555` слит merge commit
  `8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd`.
- PR-head run `29708327405` успешен: Python 3.12 job `88248797493` —
  `2276 passed, 2 warnings in 143.14s`; Python 3.13 job `88248797488` —
  `2276 passed, 2 warnings in 113.57s`; dependency audit и все обязательные steps — `success`.
- Exact merge-SHA push-run `29708473745` подтверждён с
  `headSha=8d6640691ca3e0fc6a22d7e6dd2d732955e0eedd`: Python 3.12 job `88249137810` —
  `2276 passed, 2 warnings in 116.60s`; Python 3.13 job `88249137786` —
  `2276 passed, 2 warnings in 183.21s`; dependency audit и все обязательные steps — `success`.
- Единственные annotations — non-blocking official-actions Node.js 20/24 migration notices.
  DB/schema/migration, dependencies, provider/network/AI paths и RM-107
  score/recommendation/critical stop-factor priority не изменены. Rollback — revert feature merge
  без DB/data/settings downgrade. RM-150 переведён в `DONE`; RM-151 назначен единственным
  `IN PROGRESS`, RM-152–RM-200 остаются `PLANNED`.

## 2026-07-20 — RM-149 завершён, RM-150 активирован

- Audit/source-of-truth/hierarchy/critical/action/navigation/parity/implementation decisions
  зафиксированы commit `1540d75` до production code; characterization — `cb4fd56`, expected-red —
  `f37bef9`, основной implementation — `632d5aa`, final hardening/acceptance — `d7a6896`.
- Один Qt-free `app.tenders.detail` owner предоставляет typed registry/legacy identity, immutable
  detail/card contracts, bounded read-only assembler, reason codes, complete action catalog,
  deterministic fingerprint и fail-closed HTTPS/stale-action policy.
- Native RM-143 detail/card widgets интегрированы с exact registry и persisted-search surfaces;
  RM-147 drill-down переиспользует тот же registry owner, legacy Dashboard остаётся отдельным
  `legacy_orm`, а RM-148 сохраняет price/currency projection ownership.
- Critical warning физически предшествует decision, approved persisted recommendation не
  пересчитывается, unresolved verification conflict получает приоритет действия, а missing
  decision не превращается в negative recommendation.
- Benchmark: 10,000 card projections p50 `502.915 ms`, p95 `505.788 ms`, peak `1,608 bytes`, reads
  `0`; 25 post-warm-up publications имеют zero QObject/QThread/QTimer growth.
- Локальная acceptance: focused `36 passed`, neighboring `358 passed`, full pytest
  `2245 passed, 2 warnings in 185.80s`; secret scan, Ruff/format (`735 files`), mypy,
  offline/migration/import/composition/build/frozen smokes и dependency audit успешны.
- Feature PR #106 на head `d7a6896b9fa2daf94e760b0fcf1ae030089adcb1` слит merge commit
  `219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- PR-head Quality Gate `29703943804` успешен: Python 3.12 job `88238135602` —
  `2245 passed, 2 warnings in 95.59s`; Python 3.13 job `88238146684` —
  `2245 passed, 2 warnings in 125.70s`. Первая Python 3.12 попытка завершилась native Windows
  access violation без assertion; rerun того же head SHA прошёл без code/doc изменений.
- Exact merge-SHA push-run `29704404132` подтверждён с
  `headSha=219e7c43527ca230a61de8cdeb3f191288fc3f87`: Python 3.12 job `88239262921` —
  `2245 passed, 2 warnings in 209.10s`; Python 3.13 job `88239263398` —
  `2245 passed, 2 warnings in 141.43s`; все обязательные steps — `success`. Первая Python 3.12
  попытка также завершилась native heap violation без assertion; rerun того же merge SHA прошёл.
- Единственные annotations — existing non-blocking official-actions Node.js 20/24 migration
  notices. DB/schema/migration, dependencies, provider/network/AI paths, generic-table scope и
  RM-107 score/recommendation/critical stop-factor priority не изменены. Rollback — revert feature
  merge без DB/data/settings downgrade. RM-149 переведён в `DONE`; RM-150 назначен единственным
  `IN PROGRESS`, RM-151–RM-200 остаются `PLANNED`.

## 2026-07-19 — RM-148 завершён, RM-149 активирован

- Audit/numeric/currency/unit/rounding/margin/schema/parity/implementation contracts зафиксированы
  commit `b488468`; characterization — `aa8f261`, expected-red contract — `399ac71`.
- Один Qt-free `app.financial` owner предоставляет finite Decimal, explicit RUB/currency/unit/state,
  HALF_UP boundaries, derived revenue/weighted margin, immutable snapshots/fingerprints и exact
  JSON/CSV projection вне UI.
- Existing workflow repository остаётся source of truth и хранит schema v3 fixed-point strings.
  Explicit v2→v3 migration имеет deterministic dry-run issues, source SHA-256, byte-exact safety
  artifact, fsync, atomic replace, all-record readback и rollback; ordinary reads не мигрируют.
- Workflow editor/table/detail/audit, Dashboard, RM-147 analytics, RM-146 chart/accessibility,
  JSON/CSV/XLSX import/export, backup/restore и health используют общий exact contract. XLSX hidden
  `FinancialExact` является authoritative и conflict/tamper fail closed.
- Missing/invalid/conflicted/unsupported currency отделены от zero; mixed currency не суммируется;
  margin только `profit / total × 100`, aggregate margin weighted. FX/network/provider/AI и второй
  repository/route/chart owner не добавлены.
- Benchmark 0/1/100/1,000/10,000 records: 10,000 p50 `190.453 ms`, p95 `202.872 ms`, peak
  `7,559,228 bytes`; service/export repository reads — 0, sampling отсутствует.
- Локальная acceptance: focused `38 passed`, XLSX contour `16 passed`, full pytest
  `2209 passed, 2 warnings in 182.09s`; secret scan, Ruff/format (`722 files`), mypy,
  offline/migration/import/composition/build/frozen smokes и dependency audit успешны.
- Feature PR #104 на head `7af94361f47660a44256751126a5871b34851202` слит merge commit
  `1116216cf00fc74dad2b870617c496242cd659c2`.
- PR-head Quality Gate `29698349596` успешен: Python 3.12 job `88222880837` —
  `2209 passed, 2 warnings in 189.67s`; Python 3.13 job `88222880880` —
  `2209 passed, 2 warnings in 142.97s`.
- Automatic push-run не появился; официальный workflow-dispatch exact merge-SHA run `29699279963`
  запущен на `main` и подтверждён с `headSha=1116216cf00fc74dad2b870617c496242cd659c2`.
  Python 3.12 job `88225434927` — `2209 passed, 2 warnings in 131.83s`; Python 3.13 job
  `88225434947` — `2209 passed, 2 warnings in 131.69s`; все обязательные steps — `success`.
- RM-107 score/recommendation/critical stop-factor priority, dependencies и RM-149 card scope не
  изменены. Rollback — feature merge revert плюс verified v2 safety bytes при выполненной data
  migration. RM-148 переведён в `DONE`; RM-149 назначен единственным `IN PROGRESS`, RM-150–RM-200
  остаются `PLANNED`.

## 2026-07-19 — RM-147 завершён, RM-148 активирован

- Audit/source-of-truth/metric/time/provenance/drill-down/export/plan contracts зафиксированы
  commit `2eea4ee`; characterization — `486dd04`, expected-red contract — `150d8b9`.
- Один Qt-free `app.tenders.analytics` owner предоставляет immutable aware-time query/snapshot
  contracts, four-metric catalog, deterministic aggregation, provenance/partial states и exact
  JSON/CSV export вне UI.
- Existing tender registry и collector-state repositories предоставляют bounded bulk read-only
  facts. Analytics route/page/controller переиспользует RM-146 charts, modern shell lifecycle и
  exact stable-ID tender drill-down без второго repository/router/chart/KPI/business owner.
- Preset/custom/all-available intervals, grain/source/status/law/archive filters, complete textual
  tables и contributor identity покрыты unit/integration/UI/accessibility/frozen tests. Missing,
  unknown-time, conflicted, stale и unavailable data не выдумываются.
- Exact-data limit — 10,000 records; 10,001 fail closed как `TOO_LARGE` без sampling. Benchmark до
  10,000 records сохранил ordered/shuffled equality, service query count 0, application read-query
  count 4 и p95 aggregation `295.1390 ms`.
- Локальная acceptance: RM-147 focused `40 passed in 7.30s`, full pytest
  `2163 passed, 2 warnings in 165.42s`; secret scan, Ruff/format (`705 files`), mypy,
  offline/migration/import/composition/build/frozen smokes, design-system guard и dependency audit
  успешны.
- Feature PR #102 на head `ea84b068d437cf2e4e2e366aa94bb079938587e5` слит merge commit
  `d85cf8c99f8ee72279bbb8054942a0f4d5675ac2`.
- PR-head Quality Gate `29692568668` успешен: Python 3.12 — `4m36s`,
  `2163 passed, 2 warnings in 146.82s`; Python 3.13 — `4m40s`,
  `2163 passed, 2 warnings in 151.95s`.
- Exact merge-SHA run `29693165086` успешен: Python 3.12 — `6m36s`,
  `2163 passed, 2 warnings in 257.05s`; Python 3.13 — `4m48s`,
  `2163 passed, 2 warnings in 150.21s`; dependency audit и все обязательные jobs — `success`.
- Единственные annotations — existing non-blocking official-actions Node.js 20/24 migration
  notices. DB/schema/migration, dependencies, provider/network/AI paths, financial semantics и
  RM-107 score/recommendation/critical stop-factor priority не изменены. Rollback — revert feature
  merge без DB/data/settings downgrade. RM-147 переведён в `DONE`; RM-148 назначен единственным
  `IN PROGRESS`, RM-149–RM-200 остаются `PLANNED`.

## 2026-07-19 — RM-146 завершён, RM-147 активирован

- Audit/contract/plan зафиксированы commit `aeb02e7`; characterization — `0d1584b`,
  expected-red contract — `162bd08`.
- Один dependency-free QPainter owner `app.ui.charts` предоставляет immutable bar/line contracts,
  deterministic normalized render plan, typed selection и один semantic path для UI и exports.
- Восемь honest states, aware-time/Decimal/missing rules, complete-data accessible table,
  mouse/keyboard interaction и PNG/SVG/JSON/CSV exports не вводят второй theme/router/DI или
  business owner.
- Six-series/1,000-render/10,000-data limits, resize/DPI behavior и isolated hidden frozen smoke
  измерены. Native Narrator/high-contrast/per-monitor DPI observations остаются честно переданными
  RM-152, optimization — RM-153, cross-platform pixel-golden work — RM-154.
- Локальная acceptance: focused `27 passed`, neighboring contour `203 passed`, full pytest
  `2123 passed, 2 warnings in 133.56s`; secret scan, Ruff/format (`682 files`), required/strict
  mypy, frozen/build smoke, design-system guard и dependency audit успешны.
- Feature PR #100 на head `72118c31a31f16b524c79ee83bc82a9daf7071fb` слит merge commit
  `e09af67931c3a63874e259bed08efc5ce3a14284`.
- PR-head Quality Gate `29685966343` успешен: Python 3.12 — `6m18s`, Python 3.13 — `4m16s`.
  Первый Python 3.12 job завершился native Windows access violation без test assertion; rerun того
  же SHA прошёл без code/doc изменений. Финальные full suites — `2123 passed, 2 warnings` на обеих
  версиях.
- Exact merge-SHA run `29686798140` успешен: Python 3.12 — `5m8s`, Python 3.13 — `4m54s`;
  full suite, dependency audit и все обязательные jobs завершились `success`.
- Единственные annotations — existing non-blocking official-actions Node.js 20/24 migration
  notices. DB/schema/migration, runtime dependencies, KPI/tender/financial semantics и RM-107
  score/recommendation/critical stop-factor priority не изменены. Rollback — revert feature merge
  без DB/data/settings downgrade. RM-146 переведён в `DONE`; RM-147 назначен единственным
  `IN PROGRESS`, RM-148–RM-200 остаются `PLANNED`.

## 2026-07-19 — RM-145 завершён, RM-146 активирован

- Audit-first contract зафиксирован commit `89d8346`; characterization — `3e2ae9a`,
  expected-red contract — `3db1cbe`.
- Один immutable six-entry registry определяет truthful Dashboard KPI lineage: typed raw values,
  source/evidence/state/action, `Decimal` для денег и `None` для отсутствующих данных.
- Видимый KPI `Оценка 80+` является числовым score cohort, а не AI recommendation; workflow
  attention и profit опираются на exact repository contributors без analysis/deadline fallback.
- Tender/workflow source failures изолированы. Последнее usable значение сохраняет original
  observation time, переходит `PARTIAL`/`STALE`, а atomic ViewModel apply публикует одну generation.
- Closed typed filters и существующие destinations обеспечивают exact tender stable-ID и workflow
  contributor/Decimal parity. Mouse/Enter/Space, disabled loading/error и accessibility evidence
  semantics используют одну typed action.
- Локальная acceptance: RM-145 contract `13 passed in 4.70s`, neighboring contour
  `53 passed in 16.33s`, full pytest `2095 passed, 2 warnings in 166.94s`; secret scan,
  Ruff/format (`670 files`), mypy, frozen/build smoke, design-system guard и dependency audit
  успешны.
- Feature PR #98 на head `ac846e9e6cfa6c8ab77c445810cd081097478bc8` слит merge commit
  `ac8d2662911e8a0e450fcb20677f99082187793a`.
- PR-head Quality Gate `29676604619` успешен: Python 3.12 — `3m19s`, Python 3.13 — `4m36s`.
  Exact merge-SHA run `29680204767` успешен: Python 3.12 — `4m31s`, Python 3.13 — `3m41s`;
  full suite, dependency audit и все обязательные jobs завершились `success`.
- Единственная annotation — existing non-blocking official-actions Node.js 20/24 migration notice.
  DB/schema/migration, runtime dependencies и RM-107 score/recommendation/critical stop-factor
  priority не изменены. Rollback — revert feature merge без DB/data/settings downgrade.
  RM-145 переведён в `DONE`; RM-146 назначен единственным `IN PROGRESS`, RM-147–RM-200 остаются
  `PLANNED`.

## 2026-07-19 — RM-144 завершён, RM-145 активирован

- Audit/contract/plan зафиксированы commit `70d06f3` до application changes;
  characterization — `a7e7b93`, expected-red contract — `fab3eae`.
- `TenderWorkspacePage` извлечён из embedded legacy owner в canonical
  `app.ui.pages.tender_workspace_page`; legacy import сохраняет exact class identity, а
  `MainWindow` остаётся thin compatibility wrapper вне production bootstrap.
- Workflow, Proposals, Estimates и Projects сведены к одному physical `workflow` destination и
  одному `BusinessWorkflowPage`. Temporary `quotes_page`/`estimates_page` aliases указывают на тот
  же object; второй services/monitor/timer/page-stack owner удалён.
- `SystemHealthMonitor` использует dedicated owned pool, typed `OPEN/RUNNING/CLOSING/CLOSED`,
  retained worker signal source, generation/current-sender delivery guards и bounded idempotent
  shutdown. Workflow page останавливает timers/guards pending single-shots; shell сохраняет
  RM-140 search veto и закрывает workflow до Dashboard.
- Rapid offscreen close: один production QMainWindow, три destinations, одна tender page, одна
  workflow page/monitor, два owned timers до close и ноль после; page/monitor — `CLOSED`, network
  attempts — 0, deleted signal-source/QObject/thread warnings — 0.
- Локальная acceptance: RM-144 contract `9 passed in 12.00s`, neighboring workflow contour
  `79 passed`, full pytest `2073 passed, 2 warnings in 206.16s`; secret scan, Ruff/format
  (`666 files`), mypy, frozen/build smoke, design-system guard и dependency audit успешны.
- Feature PR #96 на head `15f49972b0e8caf539cfc65a2fe73f017160e047` слит merge commit
  `491b13a0b5e5dd204bf00faba09fa513c5f9de3b`.
- PR-head Quality Gate `29665840955` успешен: Python 3.12 — `3m35s`, Python 3.13 — `3m31s`.
  Exact merge-SHA run `29666054057` успешен: Python 3.12 — `4m24s`, Python 3.13 — `4m51s`;
  full suite, dependency audit и все обязательные jobs завершились `success`.
- Единственная annotation — existing non-blocking official-actions Node.js 20/24 migration notice.
  DB/schema/migration, runtime dependencies и RM-107 score/recommendation/critical stop-factor
  priority не изменены. Rollback — revert feature merge без DB/data/settings downgrade.
  RM-144 переведён в `DONE`; RM-145 назначен единственным `IN PROGRESS`, RM-146–RM-200 остаются
  `PLANNED`.

## 2026-07-19 — RM-143 завершён, RM-144 активирован

- Audit/contract/matrix/plan зафиксированы commit `69785ee` до application changes;
  characterization — `6cfc79d`, expected-red contract — `363a572`.
- `app.ui.theme` расширен одним immutable `corteris-design-v1` token root, одинаковыми dark/light
  roles и deterministic sRGB contrast audit без второго theme package.
- Один semantic `IconId` registry разрешает repository-owned original SVG assets через bounded
  cache и safe path-free fallback. RM-142 route IDs/order/aliases/availability/context не изменены.
- `CorterisButton`, `Card`/`KpiCard`, status/data/form primitives и offline component gallery
  покрывают обе темы, focus/keyboard/loading/error/disabled states и lifecycle stability; business
  status, KPI, score и recommendation остаются у прежних owners.
- Exact matrix покрывает 45 baseline `setStyleSheet` sites. Итог: 43 current calls, семь legacy
  MIGRATE/REMOVE calls устранены, пять canonical token-backed owners добавлены, broad exceptions и
  literal colours outside theme отсутствуют.
- Локальная acceptance: RM-143 contract `76 passed in 10.23s`, соседний UI contour
  `40 passed in 29.35s`, full pytest `2059 passed, 2 warnings in 284.17s`; secret scan,
  Ruff/format (`662 files`), mypy, frozen/build smoke, design guard и dependency audit успешны.
- Feature PR #94 на head `1915be92dc0a9e0b9c1edc0bb5955abf6c94f948` слит merge commit
  `c8d111f3db615dd3c21c231bf265bb00093c65bd`.
- PR-head Quality Gate run `29662950338` успешен: Python 3.12 — `5m03s`, Python 3.13 — `3m30s`.
  Exact merge-SHA run `29663124774` успешен: Python 3.12 — `4m38s`, Python 3.13 — `4m54s`;
  full suite, dependency audit и все обязательные jobs завершились `success`.
- Non-blocking official-actions annotation о Node.js 20/24 остаётся отдельной CI maintenance
  задачей и не влияет на RM-143 acceptance.
- DB/schema/migration, runtime dependencies и RM-107 score/recommendation/critical stop-factor
  priority не изменены. Rollback — revert feature merge без DB/data/settings downgrade.
  RM-143 переведён в `DONE`; RM-144 назначен единственным `IN PROGRESS`, RM-145–RM-200 остаются
  `PLANNED`.

## 2026-07-18 — RM-142 завершён, RM-143 активирован

- Audit/contract/plan зафиксированы commit `985601d` до application changes; characterization —
  `153ab5f`, expected-red contract — `535db20`.
- `app/ui/navigation/` добавляет immutable typed routes, availability, closed context, requests,
  results и bounded memory-only history. Existing `DashboardLayout` остаётся единственным
  production navigation owner и владельцем одного page stack.
- Primary Sidebar содержит Dashboard, Tenders и один Business Workflow. Five false peer
  placeholders удалены; planned routes fail safe, legacy aliases остаются однозначными.
- Dashboard quick actions, exact tender deep links, global search, AI/settings и существующие
  documents/scheduler/notification owners сведены к canonical route requests без второго action,
  service, repository, worker или lifecycle owner.
- Workflow proposal/estimate/project оформлены typed child intents. Search/filter state, stable
  record selection, explicit no-selection, focus origin и back/return сохраняются offline.
- UI-141-001 и UI-141-002 закрыты. DB/schema/migration, RM-107 score/recommendation/critical
  stop-factor priority и RM-143+ application scope не изменены.
- Локальная acceptance: RM-142 focused `37 passed`, соседний UI/lifecycle contour `68 passed`,
  full pytest `1983 passed, 2 warnings in 165.65s`; secret scan, Ruff/format (`644 files`), required
  mypy и diff-check успешны.
- Feature PR #92 на финальном head `01c73aee26facf4061ba32db57d4cad92fc6f62d` слит merge commit
  `246734d2f3b700392c6682c7bcfb5d6ab1469ec5`.
- Финальный PR Quality Gate run `29659175137` успешен: Python 3.12 — `3m49s`, Python 3.13 —
  `3m33s`. Exact merge-SHA push run `29659317641` успешен: Python 3.12 — `3m46s`, Python 3.13 —
  `3m38s`; dependency audit и все обязательные jobs завершились `success`.
- Non-blocking official-actions annotation о Node.js 20/24 остаётся отдельной CI maintenance
  задачей и не влияет на RM-142 acceptance.
- Rollback — revert feature merge без DB/data downgrade; legacy aliases сохраняют прежние entry
  points. RM-142 переведён в `DONE`; RM-143 назначен единственным `IN PROGRESS`, RM-144–RM-200
  остаются `PLANNED`.

## 2026-07-18 — RM-141 завершён, RM-142 активирован

- Шесть обязательных audit-документов зафиксировали production composition и owner map,
  68 UI modules / 28 910 строк, navigation as-is, 16 user journeys, redesign handoff и acceptance.
- Read-only deterministic inventory и table-model benchmark добавлены без изменения `app/`,
  dependencies, DB schema/migrations, navigation/theme или production behavior.
- Зарегистрированы 17 findings: P0 — 0, P1 — 0, P2 — 16, P3 — 1. Каждый actionable finding
  назначен ровно одному primary RM из RM-142–RM-155; недоступные DPI/screen-reader/visual cases
  честно отмечены `NOT_EXECUTED`.
- Локальная acceptance: secret scan, Ruff/format (`632 files`), mypy, mandatory offline/migration/
  composition/build selection (`14 passed in 19.32s`), UI contour
  (`302 passed, 2 warnings in 81.39s`) и full pytest
  (`1946 passed, 2 warnings in 165.52s`) успешны.
- Audit PR #90 на head `f5de117d15265fb1529df346e577f571b1ccc838` слит merge commit
  `a2e8d0528a1b9c6378a543a5c9f2c5b762483c63`.
- PR Quality Gate run `29654916158` успешен: Python 3.12 — `3m59s`, Python 3.13 — `4m21s`.
  Exact merge-SHA push run `29655095879` успешен: Python 3.12 — `3m46s`, Python 3.13 — `4m36s`;
  dependency audit и все обязательные jobs завершились `success`.
- Non-blocking official-actions annotation о Node.js 20/24 остаётся отдельной CI maintenance
  задачей и не влияет на RM-141 acceptance.
- Deterministic score/recommendation/critical stop-factor priority и AI decision boundary не
  изменены. RM-141 переведён в `DONE`; RM-142 назначен единственным `IN PROGRESS`,
  RM-143–RM-200 остаются `PLANNED`.

## 2026-07-18 — RM-140 завершён, RM-141 активирован

- Audit/contract/plan зафиксированы commit `30b2f4a` до application changes; characterization —
  `23d28ce`, expected-red contract — `ed150ae`.
- Saved profiles, unified/manual search и scheduler сведены к одному Collector admission/generation;
  typed lifecycle, late-result guards, bounded cancellation и идемпотентный shutdown закреплены.
- Active timestamps используют aware UTC, durations — monotonic clock; safe typed errors и sentinel
  exclusion проходят через outcome, persistence, UI, notifications, logs и support bundle.
- Production legacy engine/service/runner retired при сохранённом public compatibility API;
  Collector schema v14 и Registry schema v1 сохранены без migration или data copy.
- SQLite connections закрываются после операций, schema/WAL initialization выполняется один раз
  на repository instance; offline composition не выполняет network или keyring I/O.
- RM-107 score/recommendation/hard-exclusion, critical stop-factor priority и AI decision boundary
  не изменены.
- Локальная acceptance: full pytest `1946 passed, 2 warnings in 155.86s`; secret scan,
  Ruff/format (`630 files`), mypy, workflow smokes, five-cycle race gate и performance contour
  успешны.
- Feature PR #88 слит merge commit `8c09ca6df469549b4ae50457b6924898a629c0d2`.
- PR Quality Gate run `29651765243` и exact merge-SHA push run `29651986321` успешны на Python
  3.12/3.13; dependency audit и все обязательные jobs завершились `success`.
- Schema/data rollback остаётся code revert без migration rollback. RM-140 переведён в `DONE`;
  RM-141 назначен единственным `IN PROGRESS`, RM-142–RM-200 остаются `PLANNED`.

## 2026-07-18 — RM-139 завершён, RM-140 активирован

- Audit/contract/plan зафиксированы commit `6ad5741` до application changes; expected-red
  contract — `d9b2b97`.
- Existing provider/configuration, connection evidence, Collector accepted run/outcome and
  checkpoint persistence, C19 verification, schedule, health monitor/circuit, notifications и
  provider manager dialog переиспользованы без второго monitoring stack или schema bump.
- Code-owned immutable snapshot раздельно показывает enablement, connection readiness,
  operational run/circuit, checkpoint freshness, C19 verification и schedule; aware UTC,
  explicit TTL/future-skew policy, safe UI/notifications и stable transition dedup сохранены.
- Startup network I/O не добавлен; active Collector admission, RM-107 score/recommendation/
  hard-exclusion, critical stop-factor priority и AI boundaries не изменены.
- Локальная acceptance: full pytest `1908 passed, 2 warnings in 120.62s`; secret scan,
  Ruff/format (`620 files`), required и owner-contour mypy, workflow smokes, five-cycle
  circuit/notification gate, dependency audit и diff-check успешны.
- Feature PR #86 слит merge commit `41b547f67020b9645d915694c943b962b46ddc08`.
- PR Quality Gate run `29623757948` успешен: Python 3.12 —
  `1908 passed, 2 warnings in 82.11s`, Python 3.13 —
  `1908 passed, 2 warnings in 109.04s`.
- Exact merge-SHA push run `29624355650` на
  `41b547f67020b9645d915694c943b962b46ddc08` успешен: Python 3.12 —
  `1908 passed, 2 warnings in 120.67s`, Python 3.13 —
  `1908 passed, 2 warnings in 133.34s`; dependency audit и все обязательные jobs — `success`.
- Неблокирующее official-actions annotation о Node.js 20/24 не повлияло на gate и остаётся
  отдельной CI maintenance задачей.
- RM-139 переведён в `DONE`; RM-140 назначен единственным `IN PROGRESS`.
  RM-141–RM-200 остаются `PLANNED`.

## 2026-07-18 — локальная feature acceptance RM-139

- Audit/contract/plan зафиксированы commit `6ad5741` до application changes; expected-red
  contract — `d9b2b97`, семь collection errors отсутствующих RM-139 production symbols.
- Existing provider/configuration, connection evidence, Collector accepted run/outcome and
  checkpoint persistence, C19 verification, schedule, health monitor/circuit, notifications и
  provider manager dialog переиспользованы; второй monitoring stack и schema bump не добавлены.
- Code-owned immutable snapshot раздельно показывает enablement, connection readiness,
  operational run/circuit, checkpoint freshness, C19 verification и schedule. Aware UTC,
  explicit TTL/future-skew policy, deterministic transitions и stable notification dedup
  закреплены contract-тестами.
- Read-only monitoring не выполняет startup network I/O и не создаёт schema; explicit health
  check отклоняется во время active Collector session. Safe UI/notifications не раскрывают raw
  exception, URL, credential или response body.
- RM-107 score/recommendation/hard-exclusion, critical stop-factor priority и AI boundaries не
  изменены.
- Локальная acceptance: full pytest `1908 passed, 2 warnings in 120.62s`; secret scan,
  Ruff/format (`620 files`), required и owner-contour mypy, workflow smokes, five repeated
  circuit/notification runs, dependency audit и diff-check успешны.
- Полное evidence записано в `docs/RM-139_ACCEPTANCE.md`.
- Это feature evidence, не closeout: RM-139 остаётся единственным `IN PROGRESS` до feature PR
  merge, exact merge-SHA Windows Quality Gate и отдельного docs-only closeout. RM-140–RM-200
  остаются `PLANNED`.

## 2026-07-18 — RM-138 завершён, RM-139 активирован

- Audit/contract/plan зафиксированы commit `bd3880d` до application changes;
  expected-red lifecycle contract — `7360125`.
- Existing production async Collector coordinator, run-session settings/admission, provider
  factory, RM-137 normalizer/deduplicator, repository/DB, HTTP retry и DI paths переиспользованы;
  третий engine, второй retry/model/repository/DB не добавлены.
- Immutable revisioned snapshots дают exact queued/running/completed states, aware UTC,
  monotonic provider/overall deadlines, bounded concurrency и engine-owned progress.
- Cooperative idempotent cancellation ставит terminal boundary до отмены задач, сохраняет
  accepted partial results и отвергает late completions; legacy blocking-thread limit отражён
  явно.
- Canonical partial output использует RM-137 normalization/dedup один раз, не зависит от
  completion schedule; bounded dispatcher изолирует slow/failing progress subscribers.
- Safe typed errors проходят через outcomes, persistence и Qt worker без raw exception, URL,
  credential или response body; UI не блокирует event loop и не вычисляет business progress.
- Sync `TenderSearchEngine` compatibility, RM-107 score/recommendation/hard-exclusion и critical
  stop-factor priority сохранены.
- Локальная acceptance: full pytest `1892 passed, 2 warnings in 125.33s`; secret scan,
  Ruff/format (`611 files`), mypy, workflow smokes, five-cycle race gate, dependency audit и
  diff-check успешны.
- Feature PR #84 слит merge commit `593ed39c7b81efc8a67e36eef47ceadbbbaf46ca`.
- PR Quality Gate run `29619784410` успешен: Python 3.12 —
  `1892 passed, 2 warnings in 94.36s`, Python 3.13 —
  `1892 passed, 2 warnings in 111.15s`.
- Exact merge-SHA push run `29619998396` на
  `593ed39c7b81efc8a67e36eef47ceadbbbaf46ca` успешен: Python 3.12 —
  `1892 passed, 2 warnings in 102.67s`, Python 3.13 —
  `1892 passed, 2 warnings in 82.24s`; dependency audit и все обязательные jobs — `success`.
- Неблокирующее official-actions annotation о Node.js 20/24 не повлияло на gate и остаётся
  отдельной CI maintenance задачей.
- RM-138 переведён в `DONE`; RM-139 назначен единственным `IN PROGRESS`.
  RM-140–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-137 завершён, RM-138 активирован

- Audit/plan зафиксированы commit `32a1257` до application changes; expected-red contract —
  `209acd7`, одна collection error отсутствующих RM-137 symbols.
- Existing `UnifiedTender`, `TenderNormalizer`, Collector/repository/dedup/verification и DI paths
  переиспользованы; pure normalization contract v1 добавил strict Decimal, aware UTC dates,
  safe URLs, stable collections, bounded diagnostics/provenance и versioned semantic fingerprint.
- Collector, legacy provider-result path и offline manual mappings используют одну boundary;
  manual/commercial live admission остаётся fail-closed. Новый model/repository/DB/search engine
  не добавлен; Collector schema 14, Registry schema 1 и legacy payload readers сохранены.
- RM-107 score/recommendation/hard-exclusion и critical stop-factor priority не изменены.
- Локальная acceptance: focused `20 passed in 5.13s`, full pytest
  `1879 passed, 2 warnings in 98.80s`; secret scan, Ruff/format (`608 files`), mypy, workflow
  smokes, dependency audit и diff-check успешны.
- Feature PR #81 слит merge commit `e38c8c13f0ec822fde76bdbc6319a18a05fd500b`.
- PR Quality Gate run `29614656151` успешен: Python 3.12 —
  `1879 passed, 2 warnings in 147.32s`, Python 3.13 —
  `1879 passed, 2 warnings in 96.35s`.
- Exact merge-SHA run `29615080804` успешен: Python 3.12 —
  `1879 passed, 2 warnings in 105.98s`, Python 3.13 —
  `1879 passed, 2 warnings in 94.45s`; все обязательные jobs завершились `success`.
- RM-137 переведён в `DONE`; RM-138 назначен единственным `IN PROGRESS`.
  RM-139–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-136 завершён, RM-137 активирован

- Audit/plan зафиксированы commit `f4bb93a` до application changes; expected-red contract —
  `31da549`, только 12 collection errors отсутствующих RM-136 modules/symbols.
- Existing health evidence повышен до schema v2, provider settings — до schema v6;
  in-memory migration, byte-exact backup, atomic replace, stale compare-and-replace,
  revision-aware binding и bounded history сохранены.
- Explicit manual-provider health check использует bounded HTTP/RSS/FTP/FTPS transport,
  all-answer DNS classification, global-address allow policy, pinned TLS, redirect/unsafe-target
  rejection, runtime-only credential resolution и existing RM-135 parser/mapping preview.
- Current `PASSED/HEALTHY` evidence с code-owned TTL 15 минут требуется для explicit enablement
  и каждого admission; success не включает provider автоматически, binding mutations
  инвалидируют evidence, plaintext FTP остаётся degraded и не принимает credentials.
- Local acceptance на feature HEAD `fcf68ae3df340a62b4ce07e2e088a8a63a8dad5b`:
  focused `36 passed in 4.34s`, full pytest `1859 passed, 2 warnings in 70.14s`; secret scan,
  Ruff/format (`606 files`), required и owner-contour mypy, workflow smokes, dependency audit
  и diff-check успешны.
- Feature PR #78 (`feat(rm-136): add safe manual provider health check`) слит в `main`
  merge commit `d84288ab74553e500ad9eaf9f51a091404490551`.
- PR Quality Gate run `29606049619` успешен: Python 3.12 —
  `1859 passed, 2 warnings in 142.75s`, Python 3.13 —
  `1859 passed, 2 warnings in 87.96s`.
- Exact merge-SHA run `29606492310` успешен: Python 3.12 —
  `1859 passed, 2 warnings in 93.95s`, Python 3.13 —
  `1859 passed, 2 warnings in 103.55s`; все обязательные jobs завершились `success`.
- Неблокирующее official-actions annotation о Node.js 20/24 не повлияло на gate и остаётся
  отдельной CI maintenance задачей.
- Deterministic decision/scoring/critical stop-factor, built-in provider flow, legacy bytes
  и credential boundary сохранены. RM-136 переведён в `DONE`; RM-137 назначен единственным
  `IN PROGRESS`. RM-138–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-135 завершён, RM-136 активирован

- Audit/plan зафиксированы commit `b0f1048` до application changes; expected-red contract —
  `e7b9121`, только семь collection errors отсутствующих RM-135 domain/UI symbols.
- Pure `ManualAdapterSpec` v1, static API/RSS/FTP/FTPS compiler и bounded offline
  JSON/XML/RSS/Atom/CSV preview добавлены внутри existing provider/settings/factory/manager owners;
  второй store/catalog/factory/Collector, DB migration и dynamic code path не создавались.
- Provider settings повышены до schema v5 с in-memory v4 migration, byte-exact backup, atomic
  replace, stale-write rejection, semantic no-op, monotonic revision и bounded rollback history.
- Compiled manual adapter соответствует existing `AsyncTenderProvider`, но остаётся
  disabled/unverified/non-runnable; live methods fail closed `connection_test_required`.
- Network, DNS, TLS handshake, redirects, credential resolution, connection test/live health,
  FTP/FTPS transport, legacy tester/migration и production admission не реализованы.
- Local acceptance: focused `27 passed in 3.65s`, neighbor
  `205 passed, 2 warnings in 13.66s`, full pytest
  `1823 passed, 2 warnings in 64.15s`; secret scan, Ruff/format (`592 files`), required и
  changed-contour mypy, workflow smokes, dependency audit и diff-check успешны.
- Feature PR #76 (`feat(rm-135): add safe custom adapter builder`) слит в `main` коммитом
  `306b209` (`306b20977b6c23956488dc471da63af17f197e25`).
- PR Quality Gate run `29584304208` успешен: Python 3.12 —
  `1823 passed, 2 warnings in 59.52s`, Python 3.13 —
  `1823 passed, 2 warnings in 88.40s`.
- Exact merge-SHA run `29586643112` успешен: Python 3.12 rerun —
  `1823 passed, 2 warnings in 86.41s`, Python 3.13 —
  `1823 passed, 2 warnings in 88.19s`; первый Python 3.12 attempt завершился transient native
  Windows access violation без test assertion, failed-only rerun того же SHA прошёл без изменений.
- Deterministic decision/scoring/critical stop-factor, AI, legacy bytes и credential boundary
  сохранены. RM-135 переведён в `DONE`; RM-136 назначен единственным `IN PROGRESS`.
  RM-137–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-134 завершён, RM-135 активирован

- Audit/plan зафиксированы commit `5889944` до application changes; expected-red contract —
  `6610f11`, только две collection errors отсутствующего RM-134 domain module.
- Existing `ProviderEnablementRepository` и `collector_provider_settings.json` повышены до
  schema v4 с in-memory v3 migration, byte-exact backup, atomic replace и optimistic
  compare-and-replace; второй store/catalog и DB migration не создавались.
- Manual providers получили closed API/RSS/FTP/FTPS policies, strict private-target/path/port
  validation и lifecycle `ADAPTER_REQUIRED`, но остаются disabled/registration-only/non-runnable.
- Existing manager/catalog/dialog/controller/session/search/health paths сохраняют одну execution
  chain и блокируют manual ID до factory/runtime; endpoint скрыт из repr/public/error surfaces.
- Credentials, adapter/parser, connection test, DNS/live network, legacy migration,
  normalization/ranking, score/recommendation/critical stop-factor и AI semantics не изменены.
- Локальная acceptance: focused `38 passed in 4.12s`, neighbor
  `169 passed, 2 warnings in 14.66s`, full pytest
  `1796 passed, 2 warnings in 69.63s`; secret scan, Ruff/format (`583 files`), mypy,
  workflow smokes, dependency audit и diff-check успешны.
- Feature PR #74 (`feat(rm-134): add safe provider protocol selection`) слит в `main`
  коммитом `7ef0378` (`7ef0378315f9ef76046a651d1211f3da191b7719`).
- PR Quality Gate run `29577913214` успешен: Python 3.12 —
  `1796 passed, 2 warnings in 113.76s`, Python 3.13 —
  `1796 passed, 2 warnings in 87.91s`.
- Exact merge-SHA run `29578571237` успешен: Python 3.12 rerun —
  `1796 passed, 2 warnings in 84.87s`, Python 3.13 —
  `1796 passed, 2 warnings in 124.47s`; первый Python 3.12 attempt завершился transient native
  Windows heap abort `0xc0000374`, failed-only rerun на том же SHA прошёл без изменений.
- RM-134 переведён в `DONE`; RM-135 назначен единственным `IN PROGRESS`.
  RM-136–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-133 завершён, RM-134 активирован

- Audit и plan зафиксированы docs-only commit `31e1456` до application changes;
  expected-red contract — `d3f8906`, только семь ошибок отсутствующей RM-133 boundary.
- Existing `ProviderEnablementRepository` и `collector_provider_settings.json` повышены до
  schema v3 с in-memory v2 migration, byte-exact backup и atomic replace; второй store/catalog,
  SQLite migration и legacy auto-import не создавались.
- Ручные регистрации получили stable `manual_<uuid>` identity, строгую inert URL validation и
  lifecycle `PROTOCOL_REQUIRED`; endpoint скрыт из public/error/log surfaces.
- Manager, resolved catalog, existing dialog, profiles/controller/scheduler/session/factory
  сохраняют единую execution chain и блокируют manual ID до network/runtime construction.
- Credentials, protocol/adapter, connection test, DNS/live network, normalization/ranking,
  score/recommendation/critical stop-factor и AI semantics не изменены.
- Локальная acceptance: focused `51 passed in 4.31s`, neighbor
  `160 passed, 2 warnings in 12.65s`, full pytest `1758 passed, 2 warnings in 66.57s`;
  secret scan, Ruff/format (`578 files`), mypy, workflow smokes, dependency audit и diff-check успешны.
- Feature PR #72 (`feat(rm-133): add safe manual provider registration`) слит в `main` коммитом
  `c067b5e` (`c067b5ecbc24428906dd006abe1e0ee6eef48e12`).
- PR Quality Gate run `29572356676` успешен: Python 3.12 —
  `1758 passed, 2 warnings in 93.74s`, Python 3.13 —
  `1758 passed, 2 warnings in 63.88s`.
- Exact merge-SHA run `29573356516` успешен: Python 3.12 —
  `1758 passed, 2 warnings in 104.98s`, Python 3.13 —
  `1758 passed, 2 warnings in 174.96s`; все обязательные jobs — `success`.
- Неблокирующее official-actions annotation о Node.js 20/24 не повлияло на gate.
- RM-133 переведён в `DONE`; RM-134 назначен единственным `IN PROGRESS`.
  RM-135–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-132 завершён, RM-133 активирован

- Audit и plan зафиксированы docs-only commit `25b2eed` до application changes;
  expected-red contract — `131f9a8`, только семь ошибок отсутствующих RM-132
  boundaries.
- Единственный keyring owner `app.security.secrets` сохранён; storage-free typed
  `ProviderCredentialService` не создаёт vault, persistence, encryption или schema.
- MOS и восемь commercial providers используют один explicit
  save/replace/delete contract; UI не делает readback, не prefill и не показывает
  masked fragments.
- Ordinary manager state/composition остаётся no-keyring/no-network; environment override
  runtime-only и не копируется в protected store.
- Legacy manual-platform UI больше не создаёт/читает/удаляет произвольные
  `platform:<name>` credentials; прежние unknown entries не изменялись.
- Локальная acceptance: focused `21 passed in 3.52s`, neighbor `110 passed in 8.59s`,
  full pytest `1707 passed in 64.89s`; secret scan, Ruff/format (`570 files`), mypy,
  workflow smokes, dependency audit и diff-check успешны.
- Feature PR #70 слит в `main` merge commit
  `1ae9c36605043e35333dffc60a6077c16fbd19f4`.
- PR run `29565942602` и exact merge-SHA run `29567132554` успешны на Python 3.12/3.13;
  полный pytest везде дал `1707 passed`, все обязательные jobs — `success`.
- Неблокирующее official-actions annotation о Node.js 20/24 не повлияло на gate и
  остаётся отдельной CI maintenance задачей.
- RM-132 переведён в `DONE`; RM-133 назначен единственным `IN PROGRESS`.
  RM-134–RM-200 остаются `PLANNED`; decision/scoring/AI semantics не изменены.

## 2026-07-17 — RM-131 завершён, RM-132 активирован

- Audit `docs/RM-131_AUDIT.md` и implementation plan зафиксированы docs-only commit `243ab56` до
  application changes; expected-red characterization — commit `4c13913` (`7 errors in 4.49s` только
  по отсутствующим RM-131 boundaries).
- Existing `ProviderEnablementRepository` повышен до единственного schema-v2 owner в прежнем
  `<data_directory>/collector_provider_settings.json`; typed load различает
  missing/current/migrated-split-v1/corrupt/future и fail closed сохраняет invalid original.
- Split-v1 migration детерминированно объединяет general и legacy commercial settings при первой
  explicit mutation, создаёт byte-for-byte backups, использует atomic replace, очищает temp при
  ошибке и сохраняет legacy source для rollback.
- Pure canonical provider definitions и только явные aliases разделяются manager, profiles,
  scheduler, session и factory; generic `commercial` отклоняется, profile/schedule bytes не
  переписываются ради canonicalization.
- Один immutable resolved snapshot устранил divergence между UI и фактическим Collector run;
  environment overrides runtime-only и read-only, credential/keyring values не сохраняются и не
  выводятся.
- Existing provider manager dialog, unified panel, Collector dialog, scheduler и legacy manual
  compatibility handoff адаптированы без второго settings owner, catalog, factory или search engine.
- Health JSON, C19 SQLite verification, credentials, DB/schema/migrations, normalization/ranking,
  score/recommendation/critical stop-factor и AI contracts не изменены.
- Локальная acceptance: focused `30 passed in 4.37s`, neighbor `76 passed in 12.01s`, full pytest
  `1686 passed in 63.19s`; secret scan, Ruff/format (`562 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Feature PR #68 (`feat(rm-131): consolidate provider settings`) слит в `main` коммитом `bbfd8e3`
  (`bbfd8e3b858a29f07d7b55fde5fdb5a80a1d9cf2`).
- PR Quality Gate run `29538903447` успешен: Python 3.12 — `1686 passed in 90.24s`, Python 3.13 —
  `1686 passed in 101.46s`.
- Exact merge-SHA run `29562019173` успешен: Python 3.12 — `1686 passed in 105.77s`, Python 3.13 —
  `1686 passed in 69.02s`; все обязательные jobs завершились `success`.
- Неблокирующее предупреждение official actions о принудительном Node.js 24 не повлияло на gate и
  остаётся отдельной CI maintenance задачей.
- RM-131 переведён в `DONE`; RM-132 назначен единственным `IN PROGRESS` для audit-first hardening
  existing credential input/resolution. RM-133–RM-200 остаются `PLANNED`.

## 2026-07-17 — RM-130 завершён, RM-131 активирован

- Audit `docs/RM-130_AUDIT.md` и implementation plan зафиксированы docs-only commit `09d60cc` до
  application changes; expected-red characterization — commit `f206c0d`.
- Existing `TenderSearchProfileRepository` повышен до schema v2 в прежнем
  `<data_directory>/search_profiles.json`; immutable typed load fail-closed различает
  missing/current/migrated-v1/corrupt/future и не уничтожает original.
- Первая explicit mutation valid v1 создаёт byte-for-byte backup и atomic replace; corrupt/future
  source не перезаписывается, replace failure сохраняет original и очищает temp.
- Canonical built-in ID membership является единственным источником built-in identity; custom
  profiles, disabled state, IDs и deterministic order сохраняются при load/migration/restore.
- `SAVED_PROFILE` и `KEYWORD_OVERRIDE` фиксируют существующую RM-128 семантику; transient text
  заменяет только keywords текущего запуска и не изменяет model/repository bytes.
- Profile price editor использует exact Decimal-safe boundary без float; explicit currency и
  aware-or-unknown timestamps сохраняются без guessed timezone.
- Один repository/path/dialog/editor/unified panel/Collector worker owner сохранён; legacy sync
  runner, async Collector, scheduler profile-ID behavior и RM-129 business projection не заменены.
- DB/schema/migrations, dependencies, provider settings/credentials, normalization/ranking,
  score/recommendation/critical stop-factor, AI и RM-131+ production scope не изменены.
- Локальная acceptance: focused `82 passed in 9.68s`, neighbor `64 passed in 6.33s`, full pytest
  `1656 passed in 60.73s`; secret scan, Ruff/format (`554 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Feature PR #66 (`feat(rm-130): add safe saved search profile schema v2`) слит в `main` коммитом
  `3a4d530` (`3a4d53067b7b0f8eaf0b5969c139284c9d5ed987`).
- PR Quality Gate run `29533900495` успешен: Python 3.12 — `1656 passed in 101.17s`, Python 3.13 —
  `1656 passed in 150.85s`.
- Exact merge-SHA run `29534568925` успешен: Python 3.12 — `1656 passed in 141.74s`,
  Python 3.13 — `1656 passed in 66.21s`; все обязательные jobs завершились `success`.
- RM-130 переведён в `DONE`; RM-131 назначен единственным `IN PROGRESS` для audit-first
  консолидации existing provider settings/catalog. RM-132–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-129 завершён, RM-130 активирован

- Audit `docs/RM-129_AUDIT.md` и implementation plan зафиксированы docs-only commit `ddb8427` до
  application changes; expected-red characterization — commit `3331131`.
- Existing `CompanyCapabilityProfileRepository` повышен до schema v2 в том же JSON path; v1
  мигрируется in memory, typed load fail-closed различает missing/current/migrated/corrupt/future и
  не уничтожает original.
- Content-bound confirmation version 1 связывает все decision facts с deterministic SHA-256;
  explicit currency, decimal strings и aware UTC timestamps сохраняются без guessed capabilities.
- Pure frozen `BusinessCapabilityProjection` является одной confirmed-facts boundary для manual score,
  automatic Collector и stop-factor engine; runtime/controller/dialog разделяют existing repository.
- V1/v2 golden score components/explanations/recommendation, stop и final decision совпадают; matching,
  saved search, DB/migrations, provider/network, AI и `ParticipationDecisionService` не изменены;
  critical block остаётся абсолютным.
- Локальная acceptance: focused `76 passed in 5.25s`, neighbor `38 passed in 6.85s`, adjacent
  summary/full-analysis `51 passed in 3.53s`, full pytest `1623 passed in 70.35s`; secret scan,
  Ruff/format (`549 files`), mypy, workflow smokes, dependency audit и diff-check успешны.
- Feature PR #64 (`feat(rm-129): add universal confirmed business profiles`) слит в `main` коммитом
  `f9b43c3` (`f9b43c37bb5c7e631e4851cde2b39c1178d34239`).
- PR Quality Gate run `29522220375` успешен: Python 3.12 — `1623 passed in 164.70s`, Python 3.13 —
  `1623 passed in 63.03s`.
- Exact-SHA post-merge run `29522737754` успешен: Python 3.12 — `1623 passed in 69.59s`,
  Python 3.13 — `1623 passed in 103.67s`; все обязательные jobs завершились `success`.
- Неблокирующее предупреждение official actions о принудительном Node.js 24 не повлияло на gate и
  остаётся отдельной CI maintenance задачей.
- RM-129 переведён в `DONE`; RM-130 назначен единственным `IN PROGRESS` для audit-first upgrade
  existing saved-search profile contract. RM-131–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-129: feature acceptance подготовлена

- Audit `docs/RM-129_AUDIT.md` и implementation plan зафиксированы docs-only commit `ddb8427` до
  production changes; expected-red characterization — commit `3331131`.
- Существующий `CompanyCapabilityProfileRepository` повышен до schema v2 в том же JSON path;
  v1 мигрируется только in memory, typed load различает missing/current/migrated/corrupt/future,
  invalid/future original не перезаписывается.
- Content-bound confirmation version 1 exact-связывает все decision facts с deterministic SHA-256;
  explicit `base_currency` нормализуется, money остаётся decimal strings, timestamps — aware UTC.
- Pure frozen `BusinessCapabilityProjection` отделяет facts от Corteris completeness/scoring policy и
  fail-closed скрывает неподтверждённые capability facts.
- Manual recalculation и automatic Collector строят одну projection для existing ranker и
  `StopFactorEngine`; v1/v2 golden components/explanations/recommendation/stop/final-decision guards
  совпадают, critical block остаётся абсолютным.
- Existing runtime/controller/dialog используют один repository instance; UI вызывает domain
  confirmation, требует новое подтверждение после edit и показывает migrated/corrupt/future status без
  auto-save.
- Matching catalog/`canonical_term`, saved search profiles, DB/migrations, provider/network,
  dependencies, AI и `ParticipationDecisionService` production code не изменены.
- Локальная acceptance на feature HEAD `a99252b`: focused `76 passed in 5.25s`, neighbor
  `38 passed in 6.85s`, adjacent summary/full-analysis `51 passed in 3.53s`, full pytest
  `1623 passed in 70.35s`; secret scan, Ruff/format (`549 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Это feature evidence, не closeout: RM-129 остаётся `IN PROGRESS` до feature PR/merge, exact-SHA
  Windows Quality Gate 3.12/3.13 и отдельного docs-only closeout. RM-130 остаётся `PLANNED`.

## 2026-07-16 — RM-128 завершён, RM-129 активирован

- Audit `docs/RM-128_AUDIT.md` и implementation plan зафиксированы docs-only commit `39605d0` до
  application changes; expected-red characterization — commit `19aceba`.
- Одна `TenderUnifiedSearchPanel` встроена над existing tabs одной `TenderWorkspacePage`; topbar
  использует narrow page → panel → existing controller path и не меняет equipment `catalog_query`.
- Pure immutable request boundary использует existing `TenderSearchProfileRepository` snapshots,
  сохраняет profile query/`Decimal`/currency/dates и отклоняет unknown/disabled/stale provider без
  silent fallback или network.
- Unified panel, Collector dialog и scheduler разделяют один existing `TenderSearchUiController`,
  единственный `_CollectorRunWorker`, cancellation/progress/result cleanup и canonical registry.
- Unified path использует existing async `CollectorRunSession`; legacy sync profile dialog/runner
  сохранён до parity/retirement RM-138.
- Новый repository, engine, Collector, provider catalog, DB/migration, profile schema, dependency,
  decision или AI contract не добавлен; critical stop-factor priority неизменен.
- Локальная acceptance: focused `23 passed in 5.20s`, neighbor `66 passed in 8.80s`, full pytest
  `1552 passed in 61.49s`; secret scan, Ruff/format (`545 files`), mypy, workflow smokes,
  dependency audit и diff-check успешны.
- Feature PR #62 (`feat(rm-128): add unified tender search panel`) слит в `main` коммитом `a67f5df`
  (`a67f5df331f8257799e24a9ef3980c6feea69c7a`).
- PR Quality Gate run `29499175129` успешен: Python 3.12 — `1552 passed in 67.74s`, Python 3.13 —
  `1552 passed in 97.95s`.
- Exact-SHA post-merge run `29499519358` успешен: Python 3.12 —
  `1552 passed in 169.06s`, Python 3.13 — `1552 passed in 73.62s`; initial Python 3.12 native access
  violation не воспроизвёлся при rerun того же SHA. Все обязательные jobs завершились `success`.
- RM-128 переведён в `DONE`; RM-129 назначен единственным `IN PROGRESS` для audited generalization
  existing company capability без смешивания с saved search profiles. RM-130–RM-200 остаются
  `PLANNED`.

## 2026-07-16 — RM-127 завершён, RM-128 активирован

- Audit `docs/RM-127_AUDIT.md` и implementation plan были зафиксированы docs-only commit
  `13dfb83` до production changes; characterization contract — commit `cb21b82`.
- Existing tender content выделен как одна `TenderWorkspacePage(QWidget)` с exact 8 top-level и
  6 nested settings tabs, stable keys/objectNames и narrow compatibility API.
- Production `ModernMainWindow` больше не создаёт hidden legacy `MainWindow`, не вызывает
  `takeCentralWidget()` и не обращается к `table/current_id/catalog_query` напрямую; standalone
  legacy wrapper строит одну reusable page.
- Один существующий `TenderSearchUiController`, те же 7 direct и 2 scheduler QAction, menu/toolbar,
  shortcuts, dialogs, workers и C11 full-analysis workflow сохранены без дублирования.
- Topbar сохраняет прежний price/equipment catalog contract; universal search RM-128, новый engine,
  Collector, repository, DB/migration, provider, decision или AI changes не добавлены.
- Локальная acceptance: focused `54 passed in 31.02s`; полный pytest дважды —
  `1532 passed in 55.91s` и `1532 passed in 77.25s`; secret scan, Ruff, format, mypy,
  workflow smokes, dependency audit и diff-check успешны.
- Feature PR #60 (`feat(rm-127): isolate tender workspace in modern tab structure`) слит в `main`
  коммитом `0b95567` (`0b9556799a20ddbf7338476fe76f602e7ff79d07`).
- PR Quality Gate run `29488228903` успешен: Python 3.12 — `1532 passed in 94.14s`,
  Python 3.13 — `1532 passed in 83.76s`.
- Post-merge Quality Gate run `29489511239` успешен: Python 3.12 —
  `1532 passed in 82.83s`, Python 3.13 — `1532 passed in 145.43s`; на обеих версиях прошли
  Ruff check/format (`540 files`), mypy (20 файлов), secret scan,
  offline/migration/import/composition/build smoke tests и dependency audit.
- RM-127 переведён в `DONE`; RM-128 назначен единственным `IN PROGRESS` для одной search panel над
  существующим saved-profile repository и audited sync/async facade. RM-129–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-126.1 завершён, RM-127 активирован

- Feature PR #58 (`feat(rm-126.1): harden EIS parser stage 1`) слит в `main` коммитом `b6369c8`
  (`b6369c85791b9c06a97f03a1fbb2504c88a1dea7`).
- Post-merge Quality Gate run `29460395144` завершился статусом `SUCCESS`: Python 3.12 —
  `1524 passed in 95.38s`, Python 3.13 — `1524 passed in 71.31s`.
- На обеих версиях прошли Ruff check/format (`537 files`), mypy (20 файлов), repository secret scan,
  offline/migration/import/composition/build smoke tests и dependency audit.
- Audit `docs/EIS_PARSER_STAGE_1_AUDIT.md` и architecture plan были зафиксированы commit `955ec6a`
  до production changes; implementation commit `ca3e6c2` сохранил единую Collector/DI цепочку.
- `get_tender()` открывает detail-page; 44-ФЗ и 223-ФЗ разделены детерминированным router; mandatory
  fields и HTML drift проверяются fail-closed; добавлены parser versions, diagnostics, separate
  network/parser health, allowed hosts, opt-in sanitized snapshots, fixtures и read-only live canary.
- Новый Collector, HTTP client, tender model, persistence root, DB schema/migration, scoring или
  analysis workflow не добавлены; deterministic decision и critical stop-factor priority не изменены.
- Локальная приёмка: EIS/Collector target `69 passed in 6.35s`, full `1524 passed in 54.24s`,
  repository secret scan, Ruff, mypy, smoke tests, dependency audit и diff-check успешны.
- Live canary не запускался автоматически против внешней ЕИС; сетевой запуск остаётся явной
  operator action и не входит в offline CI.
- Общий RM-126, включая поздний подэтап RM-126.1, переведён в `DONE`; RM-127 назначен единственным
  `IN PROGRESS`, RM-128–RM-200 остаются `PLANNED`.

## 2026-07-16 — RM-126 переоткрыт для технического подэтапа RM-126.1

- После завершения audit/closeout RM-126 владелец проекта предоставил и явно подтвердил позднее
  дополнение `RM-126.1 — Аудит и укрепление текущего провайдера ЕИС`.
- История audit PR #55, closeout PR #56 и их успешных Quality Gate сохраняется без изменения: общий
  архитектурный аудит остаётся принятой завершённой частью RM-126.
- Для соблюдения порядка из дополнения общий RM-126 временно возвращён в `IN PROGRESS`, RM-126.1
  назначен единственным активным техническим подэтапом, а RM-127 возвращён в `PLANNED`.
- RM-126.1 обязан переиспользовать `AsyncHttpClient`, `AsyncProviderSearchEngine`,
  `AsyncEisTenderProvider`, `UnifiedTender`, `CollectorStateRepository`, verification/scoring/full
  analysis и существующий DI; второй Collector, HTTP client, model, database или workflow запрещены.
- До production-кода обязателен отдельный EIS parser audit. Условие завершения: feature merge,
  post-merge Windows Quality Gate и docs-only closeout; только затем активируется RM-127.
- Эта запись меняет только canonical ordering/status и не содержит production- или DB-изменений.

## 2026-07-16 — RM-126 завершён

- Audit PR #55 (`docs(rm-126): audit tenders section`) слит в `main` коммитом `f09d07e`
  (`f09d07ebb1a15acb42279d3b8f7e0393c8d84afc`).
- Post-merge Quality Gate run `29453928900` завершился статусом `SUCCESS`: Python 3.12 —
  `1496 passed in 76.46s`, Python 3.13 — `1496 passed in 157.55s`.
- На обеих версиях прошли Ruff check/format (`523 files`), mypy (20 файлов), repository secret
  scan, offline/migration/import/composition/build smoke tests и dependency audit.
- Entry baseline `7d51159a` прошёл target `395 passed in 36.20s` и full
  `1496 passed in 63.74s`; финальная локальная audit branch — target `395 passed in 33.99s`,
  full `1496 passed in 61.27s`, остальные workflow-equivalent checks и diff-check успешны.
- `docs/RM-126_AUDIT.md` фиксирует UI journeys, sync/async search comparison, provider/profile/
  credentials/persistence/lifecycle/downstream boundaries, 12 findings и семь evidence-based Mermaid
  diagrams; `docs/RM-126_REQUIREMENTS.md` задаёт обязательный handoff RM-127–RM-140.
- Приняты D-01–D-10: modern shell владеет единственной tender page; async Collector — целевой search
  boundary с временным sync facade; существующие provider manager, keyring, saved-profile repository,
  Collector normalization/verification и shared `tender_records` переиспользуются.
- C1–C20 распределены по одному основному RM из RM-127–RM-140; третьи search/provider/settings/
  credential/health/normalization/persistence owners запрещены.
- HIGH handoff для будущих этапов: embedded legacy UI, два search orchestration path, отсутствие
  общего tender shutdown и неоднородная timezone policy. Publication blocker не обнаружен.
- Audit и closeout не изменяют production-код, зависимости, DB schema или migrations и не выполняют
  live-запросы к площадкам; deterministic decision и абсолютный приоритет critical stop-factor сохранены.
- RM-126 переведён в `DONE`; RM-127 назначен единственным `IN PROGRESS` для изоляции tender page по
  D-01 после merge closeout и успешного финального Windows Quality Gate.

## 2026-07-15 — RM-125 завершён

- PR #53 (`Fix/rm 125 stabilize ai platform`) слит в `main` коммитом `bdceb70`
  (`bdceb70f0df1632baf83db4131a7ac4ed6215349`).
- Post-merge Quality Gate run `29450245855` завершился статусом `SUCCESS`: Python 3.12 —
  `1496 passed in 95.46s`, Python 3.13 — `1496 passed in 61.69s`.
- На обеих версиях прошли Ruff check/format (`523 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Единый immutable execution contract v1 exact-связывает provider/model и все versioned
  boundaries анализа; analyzer повышен до v12, остальные утверждённые contracts сохранены.
- Typed cache lookup пропускает corrupt/future/mismatched rows, находит более старую exact
  current-compatible запись и не использует mutable production warning state.
- Empty-source analysis создаёт valid provenance без provider call; pure cacheability predicate
  исключает persistence без exact key/fingerprint/current contract/payload/provenance.
- Allowlisted provider failures получают fixed bounded warnings без raw exception text, retry
  или stale fallback.
- Per-key coordinator сериализует одинаковые run/recheck, сохраняет параллельность разных ключей
  и очищает lock state после исключения.
- Participation decision больше не использует implicit latest AI analysis; текущий AI-результат
  передаётся только явно через existing full-analysis path.
- Сохранены один provider call site, analyzer/service/Orchestrator/repository, одна
  `RUNNING_AI` stage и existing runtime graph; новая AI-stage, provider call, repository, БД,
  таблица или migration не добавлены.
- RM-107 score/recommendation/actions/evidence/confidence/commercial estimate и абсолютный
  приоритет critical stop-factor не изменены.
- Локальная приёмка: target `315 passed in 7.15s`, full `1496 passed in 58.68s`, Ruff
  (`523 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-125 переведён в `DONE`; RM-126 назначен следующим активным этапом только для отдельного
  будущего аудита раздела Тендеры.

## 2026-07-15 — RM-124 завершён

- PR #51 (`feat(rm-124): add explainable AI recheck`) слит в `main` коммитом `cfd044e`
  (`cfd044e2ff437819aabe16864c4426d9b4ad8fd8`).
- Post-merge Quality Gate run `29437124384` завершился статусом `SUCCESS`: Python 3.12 —
  `1466 passed in 108.68s`, Python 3.13 — `1466 passed in 80.07s`.
- На обеих версиях прошли Ruff check/format (`521 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure recheck policy v1 exact-сравнивает analyses одного registry/fingerprint/provider/model/
  version contract, игнорирует меняющиеся technical provenance fields и использует только
  locally verified findings.
- Finding identity основан на `scope + category + citation_id`; added/removed/modified delta и
  ordering deterministic, heuristic matching и promotion unverified findings отсутствуют.
- Existing service/orchestrator строит context/fingerprint один раз, захватывает exact baseline до
  append-only current save и вызывает analyzer ровно один раз. Automatic retry, critic pipeline и
  stale baseline fallback не добавлены.
- Repository read failure не блокирует current request; current provider failure получает
  `current_unavailable`, не заменяется baseline и не сохраняется.
- Existing AI dialog использует confirmation/background worker/per-registry guard, а existing
  JSON/HTML exporter — optional safe `ai_recheck`; новая UI tab или `RUNNING_AI` stage не создана.
- Provider schema/format v4, prompt v6, payload v10, analyzer v11, context v6, citation resolver v1
  и physical SQLite schema не изменены. Сохранены один provider call site, analyzer/service/
  Orchestrator/repository и runtime graph.
- RM-107 score/recommendation/actions/evidence/confidence/commercial estimate и абсолютный
  приоритет critical stop-factor не изменены.
- Локальная приёмка: target `150 passed in 5.70s`, full `1466 passed in 56.89s`, Ruff
  (`521 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-124 переведён в `DONE`; RM-125 назначен следующим активным этапом только для отдельного
  будущего аудита и стабилизации AI-платформы.

## 2026-07-15 — RM-123 завершён

- PR #49 (`feat(rm-123): add deterministic documentation completeness`) слит в `main` коммитом
  `759f015` (`759f015b2d101e56c9dc2a3db2ac57332b9d8ccc`).
- Post-merge Quality Gate run `29430495132` завершился статусом `SUCCESS`: Python 3.12 —
  `1442 passed in 85.09s`, Python 3.13 — `1442 passed in 81.29s`.
- На обеих версиях прошли Ruff check/format (`519 files`), mypy (20 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Первый Python 3.12 attempt завершился transient native Windows heap crash `0xc0000374` без
  failing assertion или Python exception; rerun того же merge SHA полностью прошёл без изменения
  кода, что подтвердило runner-level transient failure.
- Canonical inventory объединяет existing document catalog и latest text extraction по
  `document_key`, сохраняет download failures/archive members и включает safe identity, kind,
  statuses, checksum и context inclusion/truncation без private source metadata.
- Pure local policy задаёт deterministic statuses, counts, stable issue IDs, titles и actions без
  второго provider call, statement/keyword matching, I/O, network, DB или money calculations.
  Provider `missing_documents` не является source of truth и отображается отдельно.
- Inventory входит в context fingerprint; current payload v10 строго валидируется, assessment
  локально пересчитывается и exact-сверяется. Legacy v1–v9 остаётся unavailable, а
  future/corrupt/tampered cache и duplicate JSON keys обрабатываются fail-closed без изменения
  SQLite schema.
- Provider schema/response format v4, prompt v6, citation resolver v1 и
  legal/financial/competition policy v1 не изменены; payload повышен до v10, analyzer — до v11,
  context — до v6, documentation completeness policy имеет версию 1.
- Сохранены один classifier, analyzer/service/Orchestrator/repository/provider call, одна
  `RUNNING_AI` stage и existing AI tab/JSON/HTML exporter. UI/export показывают status,
  disclaimer, counts, coverage, safe inventory, issues/actions и warnings с HTML escaping.
- RM-107 score/recommendation/action plan/evidence/confidence и абсолютный приоритет critical
  stop-factor не изменены; documentation assessment не входит в decision evidence.
- Локальная приёмка: target `589 passed in 15.07s`, full `1442 passed in 52.38s`, Ruff
  (`519 files`), mypy (20 файлов), secret scan, dependency audit и diff-check успешны.
- RM-123 переведён в `DONE`; RM-124 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации повторной проверки AI.

## 2026-07-15 — RM-122 завершён

- PR #47 (`feat(rm-122): add explainable competition assessment`) слит в `main` коммитом
  `4ebbf6c` (`4ebbf6c4dc4cf004e234310a7bc0fdf959ee17c6`).
- Post-merge Quality Gate run `29422296807` завершился статусом `SUCCESS`: Python 3.12 —
  `1389 passed in 100.83s`, Python 3.13 — `1389 passed in 70.65s`.
- На обеих версиях прошли Ruff check/format (`517 files`), mypy (19 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local competition policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  statement keyword/regex matching, market prediction или внешних данных о компаниях.
- Category и review priority заданы фиксированными mappings; stable condition IDs и ordering
  основаны на canonical citation IDs. Generic root findings и deterministic stop-factors не
  копируются.
- Persisted payload v9 локально пересчитывается при чтении; legacy v1–v8 остаётся unavailable,
  а future/corrupt/tampered cache и duplicate JSON keys обрабатываются fail-closed без изменения
  SQLite schema.
- Provider schema/response format v4, prompt v6, context v5, citation resolver v1, legal policy
  v1 и financial policy v1 не изменены; сохранены один analyzer/service/Orchestrator/repository/
  provider call и одна `RUNNING_AI` stage.
- Legacy `COMP_RULES`/`competition_risk`, `raw_metadata`, неподтверждённые результаты торгов,
  company profile, деньги и `float` не используются; прогноз числа конкурентов, вероятности
  победы, снижения цены или законности условий не создаётся.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и informational disclaimer.
- RM-107 score/recommendation/action plan/evidence/confidence и абсолютный приоритет critical
  stop-factor не изменены; competition registry не входит в decision evidence.
- Локальная приёмка: target `468 passed in 14.72s`, full `1389 passed in 67.60s`, Ruff
  (`517 files`), mypy (19 файлов), secret scan, dependency audit и diff-check успешны.
- RM-122 переведён в `DONE`; RM-123 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации полноты документации.

## 2026-07-15 — RM-121 завершён

- PR #45 (`feat(rm-121): add explainable financial risk assessment`) слит в `main` коммитом
  `ac1cec2` (`ac1cec2e11ce4cb08ec7aab3b4ab74ad255da746`).
- Post-merge Quality Gate run `29416563733` завершился статусом `SUCCESS`: Python 3.12 —
  `1289 passed in 66.64s`, Python 3.13 — `1289 passed in 88.80s`.
- На обеих версиях прошли Ruff check/format (`515 files`), mypy (18 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local financial policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  text heuristics, money parsing или финансового прогноза.
- Category и review priority заданы фиксированными mappings; stable risk IDs и ordering основаны
  на canonical citation IDs. Generic root findings и deterministic stop-factors не копируются.
- Persisted payload v8 локально пересчитывается при чтении; legacy v1–v7 остаётся unavailable,
  а future/corrupt/tampered cache обрабатывается fail-closed без изменения SQLite schema.
- Provider schema/response format v4, prompt v6, context v5, citation resolver v1 и legal policy
  v1 не изменены; сохранены один analyzer/service/Orchestrator/repository/provider call и одна
  `RUNNING_AI` stage.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и финансовый disclaimer.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  financial registry не входит в decision evidence.
- CommercialEstimator сохраняет каноническую Decimal-границу; incomplete estimate остаётся
  `DATA_INSUFFICIENT` без вымышленных total cost, profit или margin.
- Локальная приёмка: target `337 passed in 13.12s`, full `1289 passed in 55.25s`, Ruff
  (`515 files`), mypy (18 файлов), secret scan, dependency audit и diff-check успешны.
- RM-121 переведён в `DONE`; RM-122 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации анализа конкуренции.

## 2026-07-15 — RM-120 завершён

- PR #43 (`feat(rm-120): add explainable legal risk assessment`) слит в `main` коммитом
  `f2f87ff` (`f2f87ff640082470bf822acee937ddd184ebcb23`).
- Post-merge Quality Gate run `29411717306` завершился статусом `SUCCESS`: Python 3.12 —
  `1198 passed in 74.13s`, Python 3.13 — `1198 passed in 73.26s`.
- На обеих версиях прошли Ruff check/format (`513 files`), mypy (17 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Pure local legal policy строит versioned registry только из current verified specialized
  requirements, technical specification и draft-contract findings без второго provider call,
  regex-классификации или network legal verification.
- Category и review priority заданы фиксированными mappings; stable risk IDs и ordering основаны
  на canonical citation IDs. Generic root risks и deterministic stop-factors не копируются.
- Persisted payload v7 локально пересчитывается при чтении; legacy v1–v6 остаётся unavailable,
  а future/corrupt/tampered cache обрабатывается fail-closed без изменения SQLite schema.
- Provider schema/response format v4, prompt v6, context v5 и citation resolver v1 не изменены;
  сохранены один analyzer/service/Orchestrator/repository/provider call и одна `RUNNING_AI` stage.
- Existing AI tab и JSON/HTML exporter показывают status, policy version, priority counts,
  escaped titles/actions, current internal citations, warnings и юридический disclaimer.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  legal registry не входит в decision evidence.
- Локальная приёмка: target `342 passed in 11.92s`, full `1198 passed in 51.00s`, Ruff
  (`513 files`), mypy (17 файлов), secret scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-120 переведён в `DONE`; RM-121 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации финансовых рисков.

## 2026-07-15 — RM-119 завершён

- PR #41 (`feat(rm-119): add explainable application requirements analysis`) слит в `main`
  коммитом `dedc361` (`dedc361c1ed88b16e0aa00e7e9f07f9ac131422a`).
- Post-merge Quality Gate run `29406013475` завершился статусом `SUCCESS`: Python 3.12 —
  `1114 passed in 88.59s`, Python 3.13 — `1114 passed in 77.06s`.
- На обеих версиях прошли Ruff check/format (`511 files`), mypy (16 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier и каноническая область источников выделяют application
  requirements/form/instructions/procurement notice, сохраняя приоритет ТЗ и проекта договора;
  AI context переиспользует их и включает application completeness metadata в fingerprint.
- Строгая provider-output schema v4 содержит обязательный раздел из 21 группы, но не отдаёт
  provider контроль над status/category/verified/legal-risk/financial-risk/score/recommendation.
- Persisted payload v6 безопасно читает legacy v1–v5 как unverified/unavailable, отклоняет
  future/corrupt cache и проверяет current provenance без изменения SQLite schema.
- Application evidence проходит единый RM-116 citation resolver только для current locally
  classified application documents; damaged, altered или non-application evidence остаётся
  unverified.
- Existing UI и JSON/HTML export показывают status, completeness, 21 группу,
  citations/provenance и предупреждения без бизнес-логики или private paths.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  application findings не входят в decision evidence.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, application repository/table и миграция БД
  не добавлены.
- Локальная приёмка: target `311 passed in 12.91s`, full `1114 passed in 55.17s`, Ruff
  (`511 files`), mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- RM-119 переведён в `DONE`; RM-120 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-118 завершён

- PR #39 (`feat(rm-118): add explainable draft contract analysis`) слит в `main` коммитом
  `40b7da2` (`40b7da25ec3ce43585650ddcec7afef994299f94`).
- Post-merge Quality Gate run `29399058186` завершился статусом `SUCCESS`: Python 3.12 —
  `1080 passed in 79.65s`, Python 3.13 — `1080 passed in 57.69s`.
- На обеих версиях прошли Ruff check/format (`510 files`), mypy (16 файлов), repository secret
  scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier назначает `DocumentKind.DRAFT_CONTRACT`, сохраняет приоритет ТЗ;
  AI context переиспользует его и включает contract completeness metadata в fingerprint.
- Строгая provider-output schema v3 содержит обязательный раздел из 16 групп, но не отдаёт
  provider контроль над status/category/verified/legal-risk/financial-risk/score/recommendation.
- Persisted payload v5 безопасно читает legacy, отклоняет future/corrupt cache и проверяет
  current provenance без изменения SQLite schema.
- Contract evidence проходит единый RM-116 citation resolver только для current locally
  classified contract documents; damaged, altered или non-contract evidence остаётся unverified.
- Existing UI и JSON/HTML export показывают status, completeness, 16 групп, citations/provenance
  и предупреждения без бизнес-логики или private paths.
- RM-107 score/recommendation/action plan и абсолютный приоритет critical stop-factor не изменены;
  contract findings не входят в decision evidence.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, contract repository/table и миграция БД
  не добавлены.
- Локальная приёмка: target `277 passed in 11.82s`, full `1080 passed in 51.12s`, Ruff
  (`510 files`), mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-118 переведён в `DONE`; RM-119 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-117 завершён

- PR #37 (`feat(rm-117): add explainable technical specification analysis`) слит в `main`
  коммитом `c9d5a31` (`c9d5a31e671ca61a6c6f54428aa8b8f9b26a561a`).
- Post-merge Quality Gate run `29376283665` завершился статусом `SUCCESS`: Python 3.12 —
  `1043 passed in 100.66s`, Python 3.13 — `1043 passed in 150.13s`.
- На обеих версиях прошли Ruff check/format (`509 files`), mypy (16 файлов), repository
  secret scan, offline/migration/composition/build smoke tests и dependency audit.
- Один public pure classifier назначает `DocumentKind.TECHNICAL_SPECIFICATION`; AI context
  переиспользует его, приоритизирует ТЗ и включает completeness metadata в fingerprint.
- Строгая provider-output schema v2 содержит обязательный раздел из 13 групп, но не отдаёт
  provider контроль над status/category/verified/score/recommendation.
- Persisted payload v4 безопасно читает legacy, отклоняет future/corrupt cache и включает
  semantic document kind в current provenance без изменения SQLite schema.
- TS evidence проходит единый RM-116 citation resolver; non-TS, unknown, altered и incomplete
  evidence остаётся unverified, а single-source contradiction не повышается до multi-source.
- Existing UI и JSON/HTML export показывают status, found/included counts, 13 групп,
  citations/provenance и truncation warnings без бизнес-логики или private paths.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/service/Orchestrator/repository/context
  builder/exporter; второй AI workflow, provider call, TS repository/table и миграция БД не
  добавлены.
- Локальная приёмка: target `214 passed`, full `1043 passed`, Ruff, mypy (16 файлов), secret
  scan, dependency audit и diff-check успешны.
- Неблокирующее предупреждение GitHub Actions о переводе pinned official actions с Node.js 20
  на Node.js 24 сохранено как отдельная обслуживающая задача и не влияет на успешный gate.
- RM-117 переведён в `DONE`; RM-118 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-15 — RM-116 завершён

- PR #35 (`feat/rm-116-citations-provenance`) слит в `main` коммитом `b8ff9b1`
  (`b8ff9b13b7f67366f16b24c1eedccf9a63cb4d46`).
- Post-merge Quality Gate run `29372896780` завершился статусом `SUCCESS`: Python 3.12 —
  `1030 passed in 123.59s`, Python 3.13 — `1030 passed in 60.47s`.
- На обеих версиях прошли Ruff check/format (`507 files`), mypy (16 файлов), repository
  secret scan, offline/migration/composition/build smoke tests и dependency audit.
- Реализованы exact local citations, immutable provenance/source registry, payload v3,
  provenance-aware cache, безопасная UI-навигация и JSON/HTML export.
- Provider сообщает только кандидаты и безопасную public metadata; checksum, offsets,
  locator, citation ID и eligibility вычисляются и проверяются локально.
- Legacy/future/corrupt cache и небезопасная provider/source metadata обрабатываются
  fail-closed без сохранения `VERIFIED` и без утечки чувствительных данных.
- RM-107 принимает только current verified citations; score/recommendation и абсолютный
  приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/Orchestrator/repository/context
  builder/exporter; второй schema/parser/workflow и миграция БД не добавлены.
- Локальная приёмка: target `273 passed`, strict/provider/UI `97 passed`, full `1029 passed`,
  Ruff, mypy (16 файлов), secret scan, dependency audit и diff-check успешны.
- RM-116 переведён в `DONE`; RM-117 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-14 — RM-116: подготовлена feature acceptance

- После обязательного аудита реализованы exact local citations, immutable provenance/source
  registry, payload v3, provenance-aware cache, безопасная UI-навигация и JSON/HTML export.
- Provider сообщает только кандидаты и безопасную public metadata; checksum, offsets, locator,
  citation ID и eligibility вычисляются и проверяются локально.
- RM-107 принимает только current verified citations; score/recommendation и абсолютный
  приоритет critical stop-factor не изменены.
- Переиспользованы существующие provider/analyzer/Orchestrator/repository/context
  builder/exporter; второй schema/parser/workflow и миграция БД не добавлены.
- Локально на Python 3.12.7: target `273 passed in 7.40s`, strict/provider/UI `97 passed in
  4.93s`, full `1029 passed in 54.90s`; Ruff, mypy (16 файлов), secret scan, dependency audit и
  diff-check успешны.
- Запись является подготовкой feature PR, а не closeout: RM-116 остаётся `IN PROGRESS`, RM-117
  остаётся `PLANNED`; обязательны feature merge, post-merge Windows gate 3.12/3.13 и отдельный
  merged docs-only closeout.
- Финальный adversarial review устранил duplicate extraction revisions и fail-open cached
  provider/source metadata; naive source timestamp теперь сохраняется как explicit `unknown`.

## 2026-07-14 — RM-115 завершён

- PR #33 (`feat(rm-115): enforce strict Tender Intelligence JSON schema`) слит в `main`
  коммитом `f2573c4` (`f2573c49cd6ac0dbbe703786414422034ffa53b2`).
- Post-merge Quality Gate run `29352442656` после повторного запуска завершился статусом
  `SUCCESS`: Python 3.12 — `901 passed in 74.68s`, Python 3.13 —
  `901 passed in 77.29s`.
- Первый Python 3.12 job завершился нативным Windows access violation внутри pytest примерно
  на 48% suite; повторный job на том же merge SHA прошёл полностью. Python 3.13 прошёл без
  этого сбоя.
- Введена одна каноническая строгая Pydantic v2 provider-output схема, детерминированная
  генерация JSON Schema и fail-closed decoder без частичного принятия payload.
- OpenAI и generic `openai_compatible` отправляют Responses API `text.format`; Ollama
  переиспользует тот же provider с подтверждённым compatibility subset без downgrade,
  capability probe или второго запроса.
- Структурно невалидный ответ возвращает `invalid_response` без AI findings; после успешной
  структуры evidence подтверждается только точным локальным совпадением цитаты.
- Переиспользованы существующие provider, analyzer, Orchestrator, repository и DI; второй AI
  workflow не создан.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor сохранены.
- Локальная приёмка: target `229 passed`, full `901 passed`, Ruff check/format,
  mypy (13 файлов), secret scan, dependency audit и `git diff --check` успешны.
- Persisted schema остаётся версии 2; новая БД или миграция БД не добавлялись.
- RM-115 переведён в `DONE`; RM-116 назначен следующим активным этапом только для отдельного
  будущего аудита и реализации.

## 2026-07-14 — prerequisite RM-115: восстановление Git/Codex integration

- В отдельной ветке `codex/git-integration-recovery` удалён случайный gitlink
  `CorterisTenderAI` (`mode 160000`, commit `38b96ab`), добавленный коммитом `35321dc`
  без обязательного `.gitmodules`.
- Причина: повреждённая submodule-запись ломала обнаружение структуры репозитория и
  `git submodule status`, усложняя Git-операции из Codex; вложенный checkout и пользовательские
  данные в рабочем дереве отсутствовали.
- Application-код, детерминированная логика, score/recommendation, critical stop-factor policy,
  схема БД и активный статус RM-115 не изменены.
- Локальная приёмка: `863 passed in 52.41s`, Ruff check, Ruff format (`502 files`),
  mypy (`10 source files`), secret scan, dependency audit, `git diff --check`, строгий `git fsck`
  и `git submodule status --recursive` успешны.
- PR #32; переход к application-коду RM-115 по-прежнему требует отдельного аудита,
  указанного в `STATUS.md`.

## 2026-07-14 — RM-114 завершён

- PR #30 (`feat(rm-114): harden OpenAI-compatible Responses API`) слит в `main`
  коммитом `e4caca0`.
- Post-merge Quality Gate run `29315630189` завершился статусом `SUCCESS`:
  Python 3.12 — `863 passed in 161.88s`, Python 3.13 — `863 passed in 164.67s`.
- Обязательный audit и Responses API contract зафиксированы до application-кода.
- Укреплён существующий `OpenAICompatibleProvider`; второй provider, analyzer,
  Orchestrator, repository, Decision Engine или AI pipeline не создан.
- Канонический endpoint — один `POST /responses` без streaming, retry, background mode,
  Chat Completions fallback, bootstrap/save health-check или сети до явного анализа.
- Cloud profile отправляет `stream=false` и `store=false`; Ollama переиспользует тот же
  provider и не получает неподтверждённые optional fields.
- Redirects запрещены, TLS verification сохранена, response ограничен 4 MiB, а
  HTTP/JSON/network/TLS/refusal/incomplete ошибки не раскрывают raw body, URL, exception,
  credential, prompt, документы или приватный путь.
- Generic base URL и credential boundaries усилены без изменения stable provider IDs,
  keyring ownership или UI business logic.
- RM-107 score/recommendation и абсолютный приоритет critical stop-factor сохранены.
- Локальная приёмка: target `152 passed`, full `863 passed`, Ruff check/format,
  mypy (10 файлов), secret scan, dependency audit и `git diff --check` успешны.
- Новая БД или миграция БД не добавлялись. Strict JSON Schema, citations/provenance и
  специализированный анализ ТЗ остались за RM-115/RM-116/RM-117.
- RM-114 переведён в `DONE`; RM-115 назначен следующим активным этапом только для
  отдельного будущего аудита и реализации.

## 2026-07-14 — RM-113 завершён

- PR #28 (`feat(rm-113): add safe local Ollama mode`) слит в `main` коммитом `ef8b296`.
- Post-merge Quality Gate run `29285835443` завершился статусом `SUCCESS` на Python 3.12
  и 3.13. Первый Python 3.13 job завершился единичным native Qt access violation в
  существующем `test_matching_catalog_dialog.py`; повторный job прошёл полностью.
- Добавлен stable ID `ollama` с loopback-only endpoint policy и нормализацией к `/v1`.
- Переиспользованы существующие `OpenAICompatibleProvider`, analyzer, Orchestrator,
  repository, ConfigManager и production DI; второй AI pipeline не создан.
- Ollama не использует keyring, а bootstrap/save не выполняют сеть или health-check.
- Невалидная конфигурация и недоступный локальный сервер дают безопасный fallback без
  раскрытия URL, exception, secret или приватного пути.
- Новая БД или миграция БД не требуются.
- Локальная приёмка: целевой набор `58 passed`, полный pytest `808 passed`, Ruff
  check/format, mypy, secret scan, dependency audit и `git diff --check` успешны.
- RM-113 переведён в `DONE`; RM-114 назначен следующим активным этапом.

## 2026-07-13 — RM-112 завершён

- PR #26 (`feat(rm-112): add safe AI provider selection`) слит в `main`
  коммитом `1d559b5`.
- Post-merge Quality Gate run `29280757442` завершился статусом `SUCCESS` на
  Python 3.12 и 3.13.
- Проведён обязательный аудит settings, keyring, runtime, UI и прямых
  provider-вызовов; требования зафиксированы до application-кода.
- Секция `ai` существующего `ConfigManager` назначена каноническим persisted
  source со stable IDs `disabled`, `openai`, `openai_compatible`.
- Переиспользованы существующие provider adapters, analyzer и Orchestrator;
  выбранный provider внедряется в production runtime через bootstrap.
- Default, неизвестная/повреждённая конфигурация и ошибки keyring безопасно
  переходят в `disabled` без утечки secret и без сети при bootstrap/save.
- Legacy label `OpenAI API` не активирует сеть; migration non-secret drafts
  идемпотентна.
- Переиспользована существующая ChatGPT/ИИ вкладка; local/Ollama не добавлен.
- Новая БД или миграция БД не требуются.
- Локальная приёмка: целевой набор `62 passed`, полный pytest `784 passed` за
  52,92 с, Ruff check/format, mypy (9 файлов), secret scan, dependency audit и
  `git diff --check` успешны.
- RM-112 переведён в `DONE`; RM-113 назначен следующим активным этапом.

## 2026-07-13 — RM-111 завершён

- PR #24 (`feat(rm-111): add unified tender AI orchestrator`) слит в `main`
  коммитом `f246381`.
- Обязательный Quality Gate merge-коммита завершился статусом `SUCCESS`
  на Python 3.12 и 3.13.
- Подтверждены единый Orchestrator, отсутствие второго production AI
  workflow, явная передача текущего результата в RM-107 и безопасная
  деградация без API.
- Миграция БД не требуется.
- RM-111 переведён в `DONE`; RM-112 назначен следующим активным этапом
  только после merge PR #24.

## 2026-07-13 — RM-111 AI Orchestrator подготовлен к приёмке

- Проведён аудит всех provider/task-service/repository/Decision Engine/UI/export
  путей; требования зафиксированы до изменения application-кода.
- Создан единый stateless `TenderAiOrchestrator`, переиспользующий
  `TenderDocumentAiAnalysisService` и возвращающий результат текущего запуска.
- Последняя exception boundary и status-to-warning policy удалены из полного
  анализа и централизованы в Orchestrator без раскрытия exception, traceback,
  credentials или приватных путей.
- `TenderFullAnalysisService` вызывает Orchestrator один раз и явно передаёт
  текущий AI-результат в RM-107; stale cache не подменяет текущую ошибку.
- Production runtime создаёт один Orchestrator и один AI repository; по
  умолчанию сохранён `DisabledProvider`, настройки RM-112/RM-114 не добавлялись.
- Неиспользуемый legacy `TenderAIService` с собственными score/recommendation и
  прямым provider-вызовом удалён; совместимые JSON/citation helpers сохранены.
- UI получил отдельную стадию «AI-анализ документации»; существующее поле
  `ai_document_analysis` и HTML/JSON export не изменены.
- Новая БД, таблица или миграция не требуются.
- Локальная приёмка: целевой набор `93 passed`, полный pytest `748 passed` за
  42,79 с, Ruff check/format, mypy (7 файлов), security scan и dependency audit
  успешны.
- RM-111 остаётся `IN PROGRESS` до merge PR; RM-112 не назначен.

## 2026-07-13 — RM-111 quality-gate prerequisite
- Решением владельца герметизация credential-тестов и воспроизводимый Windows
  quality gate назначены обязательным prerequisite текущего RM-111.
- Основание: baseline чистого `origin/main` (`b4c1cc7`) дал
  `719 passed, 2 failed`; offline-тесты прочитали Windows Credential Manager,
  а один тест выполнил реальный API-запрос.
- При пустом временном keyring оба целевых теста проходят (`2 passed`), что
  подтверждает зависимость результата от пользовательского credential store.
- До закрытия prerequisite бизнес-логика AI Orchestrator не реализуется.
- C17 canonicalization и C19 live verification остаются отдельными будущими
  work packages и не включаются в RM-111.
- В отдельной ветке `fix/rm-111-quality-gate` устранено чтение host keyring в
  offline-тестах, добавлены secret/dependency gates, фиксированный mypy-контур
  и Windows GitHub Actions matrix для Python 3.12/3.13.
- Локальный полный регресс прошёл в обычном и изолированном режимах:
  `725 passed` в каждом; Ruff, mypy, security scan и dependency audit успешны.
- PR #22 слит в `main` коммитом `ebfdf01`; обязательные jobs Python 3.12 и 3.13
  прошли на PR и повторно на merge-коммите в `main`.
- Для `main` включена защита: обязательный PR, актуальная ветка, оба стабильных
  quality-gate check context, запрет force-push и удаления; правила действуют
  для администратора.
- Prerequisite переведён в `DONE`; RM-111 остаётся `IN PROGRESS`. AI
  Orchestrator, C17 и C19 в этом пакете не реализовывались.
- В post-job логах GitHub есть неблокирующие предупреждения о переходе official
  actions с Node.js 20 на Node.js 24 и cleanup Git-кэша; итог обоих jobs —
  `SUCCESS`, обновление action pins остаётся обслуживающей задачей CI.

## 2026-07-13 — Roadmap v2
- RM-107 переведён в `DONE`.
- RM-108 назначен активным.
- Сохранена нумерация RM-001–RM-200.
- Добавлены универсальный поиск, полный редизайн, оценка контрагентов, договорный AI, подписки и защита приложения.
- Включена многоуровневая защита: Nuitka, нативные модули, серверные entitlements, подписанные лицензии, Authenticode и защищённые обновления.
- Collector C1–C20 остаётся интеграционным слоем и не заменяет RM.

## 2026-07-13 — RM-108 завершён
- Добавлено детерминированное резюме тендера с безопасным AI-улучшением текста.
- Резюме отображается в полном анализе и сохраняется в реестре закупок.
- Схема реестра обновлена до версии 13.
- RM-109 назначен следующим активным этапом.

## 2026-07-13 — RM-108 acceptance finalization
- Добавлены confidence и provenance для каждого факта резюме.
- Резюме собирает существующие решение RM-107, стоп-факторы, коммерческий расчёт, проверку данных и профиль компании.
- Добавлены история резюме, отдельная вкладка AI summary и тест воспроизводимости offline-результата.
- Полный регресс: 620 passed (без отдельного теста crash-reporting).

## 2026-07-13 — RM-107 закрыт
- Владелец проекта подтвердил статус `DONE` для RM-107.
- Дальнейшие улучшения единого решения об участии ведутся отдельными RM и не
  переоткрывают RM-107.

## 2026-07-13 — RM-109 завершён
- Реализован evidence-first AI-анализ полного комплекта извлечённых документов.
- Вывод без точной цитаты маркируется `unverified` и не влияет на RM-107.
- Добавлены хранение, повторное использование, вкладка UI и экспорт HTML/JSON.
- Полный регресс: 631 passed (без отдельного теста crash-reporting).
- RM-110 назначен следующим активным этапом.

## 2026-07-13 — RM-107 приведён к расширенному Definition of Done
- Добавлены причины решения с числовым impact и верхнеуровневый score.
- Confidence учитывает качество доказательств и количество отсутствующих данных.
- Добавлены отдельные stop_factors, missing data и детерминированный action plan.
- JSON и UI показывают все поля итогового решения.
- Стоп-фактор сохраняет абсолютный приоритет над высоким score.
- Полный регресс: 633 passed (без отдельного теста crash-reporting).

## 2026-07-13 — RM-110 завершён
- PR: #19 (`feat(rm-110): stabilize tender intelligence`).
- Проведён аудит существующей цепочки Tender Intelligence без создания
  дублирующих механизмов.
- Добавлены защитная нормализация AI-ответа, безопасные статусы, контролируемый
  контекст, версионированный fingerprint и восстановление истории SQLite.
- Ошибки AI, сети, контекста и persistence больше не блокируют RM-107,
  детерминированное резюме, UI и экспорт.
- Неподтверждённые и устаревшие AI-выводы не влияют на текущее решение.
- По разрешению владельца устранён существующий Ruff baseline: 768 ошибок;
  legacy-код приведён к единому формату без изменения подтверждённого поведения.
- Полный регресс после очистки, включая crash-reporting: 701 passed.
- `ruff check .` и `ruff format . --check` проходят.
- RM-111 назначен следующим активным этапом только после merge PR #19.

## Правило
Каждое изменение содержит дату, RM, причину, ссылку на PR и влияние на следующие этапы.
