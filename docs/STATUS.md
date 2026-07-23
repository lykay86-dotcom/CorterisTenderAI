# Текущее состояние CorterisTenderAI

Обновлено: 23 июля 2026 года.

## Активный этап

**RM-156 — модель контрагента (production-реализация приостановлена)**

Статус: `IN PROGRESS`

RM-155 завершён feature PR #118 на head
`c741ba6a39750436fa34ffc2237bd1c264466745`, merge commit
`63a85b4cff5e2de5b53e4fad6dcfb091371200bf` и успешным exact merge-SHA Windows Quality Gate
run `29845412052`. Этот отдельный docs-only closeout переводит RM-155 в `DONE`, закрывает
`UI-141-017` и завершает последовательность полного редизайна RM-141–RM-155. RM-156 —
единственный активный этап; RM-157–RM-200 остаются `PLANNED` и не выполняются параллельно.

Решением владельца от 22 июля 2026 года до production-реализации модели контрагента выполняется
обязательный Collector prerequisite по многоплощадочному сбору. Это prerequisite RM-156, а не
новый или параллельный RM: RM-156 остаётся единственным каноническим `IN PROGRESS`, а
RM-157–RM-200 остаются `PLANNED`. Полный scope и package gates зафиксированы в
[`PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md`](PRE_RM156_TENDER_COLLECTOR_ALL_PLATFORMS_TZ.md).

Docs-only P0 слит PR #121 merge commit
`c20bed32492dc80b48748c79a87da73107533ddd`; exact merge-SHA Quality Gate run `29922814088`
успешен. Docs-only P1 слит PR #122 merge commit
`6593fb2518d724c9bdde3ea46c9de84ff63b1b03`; exact merge-SHA Quality Gate run `29926327653`
успешен на Python 3.12/3.13. P2 strict expected-red tests-only package слит PR #123 merge commit
`83899900fd2913eefd0ad04398e266f4a6b64437`; exact merge-SHA Quality Gate run `29929323692`
успешен на Python 3.12/3.13. P3 shared foundation слит PR #124 merge commit
`cfc473e8a11c6c2c7bc201bbac45aa38404d7cc2`; PR-head run `29939287327` и exact merge-SHA run
`29939811499` успешны на Python 3.12/3.13. Первый P4 package — EIS reference adapter — слит PR
#125 merge commit `300385108082746ac8818dad19104f57618366a9`; PR-head run `29943116366` и exact
merge-SHA run `29943599187` успешны на Python 3.12/3.13. Второй P4 package — `mos_supplier`
reference adapter — слит PR #126 merge commit `b4704480010a363e02ad80fe579d5c836cd04509`;
PR-head run `29946701032` и exact merge-SHA run `29947263908` успешны на Python 3.12/3.13,
включая dependency audit. Один документированный authenticated API response, shared atomic
accepted-page/checkpoint/artifact path, raw search/detail/document/rejected evidence и fail-closed
redaction приняты. Full suite `2458 passed`, exact-data 10k/resource gate зелёный. EIS и Mos
Supplier честно остаются `IMPLEMENTED_OFFLINE` до отдельно разрешённой live verification;
серверная пагинация Mos не заявлена и не угадана. Production-код модели контрагента, RM-157 и
RM-158 не начинаются до
отдельного Collector closeout. Closeout должен вернуть RM-156 в production work; только затем
продолжается модель контрагента и последующие RM в исходной нумерации.

## Завершённый этап

**RM-155 — завершение редизайна**

Статус: `DONE`

Подтверждение:

- audit-first пакет классифицировал 32 compatibility candidates: 9 `REMOVE`, 2 `MIGRATE`,
  21 `KEEP`, 0 `DEPRECATE`, 0 `BLOCKED`, с consumer/history/runtime/settings/frozen/public
  evidence, owner и rollback для каждого;
- удалены только obsolete `app.ui.main_window`, два same-object page alias, их bootstrap fallback
  и неиспользуемый search shim; сохранена одна production composition без duplicate owner;
- J01–J16 и cross-stage RM-142–RM-154 guards прошли; RM-107 deterministic decision и абсолютный
  приоритет critical stop-factor не изменены;
- локально: полный pytest `2411 passed, 2 warnings in 207.24s`, neighboring contour `840 passed`,
  Ruff/format (`794 files`), mypy, secret/offline/migration/composition/build/dependency gates
  успешны;
- fresh RM-153 performance p95 и 25-cycle resource budgets прошли; controlled same-host A/B не
  обнаружил shutdown regression;
- RM-152 native evidence остаётся truthful: `0 PASS`, `4 BLOCKED`, `29 NOT_EXECUTED`;
- actual one-file EXE SHA-256
  `044B35A3D8D73132A603073FBB0F8456010950B19CB5696C2EFBB8D7BC41F7A0` прошёл все девять
  isolated frozen self-test checks;
- feature PR #118 слит merge commit `63a85b4cff5e2de5b53e4fad6dcfb091371200bf`;
- PR-head Quality Gate `29832379070` и exact merge-SHA push-run `29845412052` успешны на Python
  3.12/3.13; Python 3.12 strict visual comparison имеет `14/14 PASS`;
- DB/schema/migration, dependencies, persisted settings/data и provider/network/AI/keyring/domain
  paths не изменены; rollback — revert feature merge без downgrade данных.

## Ранее завершённый этап

**RM-154 — визуальное тестирование**

Статус: `DONE`

- Canonical strict RGB catalog содержит 14 representative dark/light cases с zero tolerance и
  renderer fingerprint `f1cd92373456028fd9360b3a032ef9b8d5784dc90d00abad4080d404db0dba56`.
- Feature PR #116 слит merge commit `40f0e327d0d485b93e93f39bab1d838e584b8914`.
- Exact merge-SHA Quality Gate run `29823579968` успешен на Python 3.12/3.13 и strict visual
  comparison `14/14 PASS`.

## Текущее действие

P5 identity/catalog package принят: PR #127 head
`70ce28001b0be0bfcd19937ba042ac1555919386`, PR-head run `29951810601`, merge commit
`e9a522fc750e0893b46b0c6028c4a61cdbb9b26f`, exact merge-SHA run `29952451892`. Обе Windows
matrix jobs успешны на Python 3.12/3.13, включая dependency audit. Exact 13 canonical IDs,
settings schema 7, Collector DB schema 16 и audited alias/read-model compatibility приняты без
новых adapters/endpoints.

Первый P6 source — `zakaz_rf` — прошёл read-only access audit. Официальный public HTML registry
обнаружен, но опубликованный API/feed contract, разрешение automation/data reuse, pagination,
rate limits, schema и raw retention не подтверждены; `robots.txt` закрывает `/Services/` и
`/QueryForms/`. Readiness честно `BLOCKED_EXTERNAL`; adapter/fixture/live verification не
создаются. Audit принят PR #128: head `2af262d9575f6a9947a51c866d249f28530cec97`, PR-head run
`29956095948`, merge `14bc30300fa40a4008b35df7897d725e682e2437`, exact merge-SHA run
`29958227968`; обе Python 3.12/3.13 jobs и dependency audit успешны.

Docs-only решением `zakaz_rf` сохраняется первым P6 source и ожидает external unblock, а
`roseltorg` назначается следующим последовательным access-audit target по фактической доступности
официального контракта. Это не working/access claim Roseltorg: его сеть, endpoints, fixtures и код
не исследуются этим package. Решение принято PR #129: head `6df486b31d0953ae140be2c03939bab848b757b3`,
PR-head run `29959486498`, merge `862dac27b38968f235f831402139980e17cc90f3`, exact run
`29959911671`; обе matrix jobs и dependency audit успешны.

Отдельный Roseltorg read-only audit обнаружил public HTML search/detail и разрешённую robots
pagination indexability, но не procurement API/feed, data-use/raw-retention permission,
schema/version/rate contract или approved fixtures. API отдельного ЭДО не является tender API.
`roseltorg` честно `BLOCKED_EXTERNAL`; adapter/fixture/live verification не создаются. Audit принят
PR #130: head `ebbdcf640fa87162db136147d9fc3be4420eaa29`, PR-head run `29961223536`, merge
`aa9825b5b4d515958c3b02c00d63a215a5af8b27`, exact run `29961900274`; обе matrix jobs и
dependency audit успешны.

Docs-only решением `zakaz_rf` и `roseltorg` сохраняются в позициях 1–2 P6 со статусом
`BLOCKED_EXTERNAL`, а `rad` назначается только следующим последовательным access-audit target.
Это не working/access claim Rad: его сеть, endpoints, fixtures и код этим package не исследуются.
Решение принято PR #131: head `c4df48df5bfbc4fc1d2dc55a8fedd5fd6ff66803`, PR-head run
`29963756719`, merge `4e5adfec20d7ad95ac2fe4decd005b0041e60909`, exact run
`29964235838`; обе matrix jobs и dependency audit успешны.

Отдельный Rad read-only audit подтвердил official 44-ФЗ/615/223-ФЗ sections and public cards, но
действующее пользовательское соглашение прямо запрещает без письменного разрешения scripts для
access, collection and interaction, а также автоматическое извлечение/копирование информации.
Public procurement API/feed, schema/version/rate/raw-retention contract и approved fixtures не
найдены. `rad` честно `BLOCKED_EXTERNAL`; adapter/fixture/live verification не создаются. Текущее
действие подтверждено PR #132: head `6ca84f2f523dce6f853cfb919420d6e36caca06e`, PR-head run
`29965371309`, merge `38fe2d75f80beb544e9b5a7a2d18462963c4f232`, exact run
`29965734080`; обе matrix jobs и dependency audit успешны.

Docs-only решением `zakaz_rf`, `roseltorg` и `rad` сохраняются в позициях 1–3 P6 со статусом
`BLOCKED_EXTERNAL`, а `tek_torg` назначается только следующим последовательным access-audit
target. Это не working/access claim TekTorg: его сеть, endpoints, fixtures и код этим package не
исследуются. Решение принято PR #133: head `4dbd9b1cdfe3a233c97bab2d9f2c58171b3ee10d`, PR-head
run `29966420486`, merge `22f5a530f6ca32ead5b76f102576fa36b559dac5`, exact run
`29966853365`; обе matrix jobs и dependency audit успешны.

Отдельный TekTorg read-only audit обнаружил официальный unauthenticated public procedure export:
discovery, SOAP WSDL, date/section/identity filters, page totals и section/type dictionaries. Это
не guessed endpoint. Однако public contract не публикует rate/retry limits, maximum page and
snapshot/completeness rules, schema/version lifecycle, exact timezone/currency/money semantics или
raw response/document retention and reuse permission. Approved fixtures не сохранялись, procedure
SOAP request и live verification не выполнялись. `tek_torg` локально классифицирован как
`BLOCKED_EXTERNAL`; adapter/tests/settings/schema/dependencies не создаются. Audit принят PR #134:
head `44e2975237899b6672681323f8a36d457fd55825`, PR-head run `29967886571`, merge
`30f6fb1c318d4c0ddc9b10d1dace6cb429c93e8f`, exact run `29968220150`; обе matrix jobs и
dependency audit успешны.

Docs-only решением `zakaz_rf`, `roseltorg`, `rad` и `tek_torg` сохраняются в позициях 1–4 P6 со
статусом `BLOCKED_EXTERNAL`, а `ets_nep` назначается только следующим последовательным
access-audit target. Это не working/access claim ETS/НЭП: его сеть, endpoints, fixtures и код этим
package не исследуются. Решение принято PR #135: head `26e705f7c72d742dd0b4570cdd90084ae9f95c85`,
PR-head run `29969146389`, merge `195f4d2e22d12ca36e1c8329e241bef9c8f8832e`, exact run
`29969484418`; обе matrix jobs и dependency audit успешны.

Отдельный ETS/НЭП audit подтвердил официальный переход `etp-ets.ru` на `44.fabrikant.ru` и общий
operator/platform owner АО «ЭТС» для уже существующих canonical IDs `ets_nep` и `fabrikant`.
Второй adapter запрещён duplicate-owner contract; требуется отдельный identity amendment с
аудитом persisted settings/credentials/history/export. Public HTML cards существуют, но
procurement API/feed, разрешение automation/data reuse, pagination/rate/schema/version и raw
retention не подтверждены; robots disallows XML/CSV export actions and file/download paths.
`ets_nep` локально `BLOCKED_EXTERNAL / IDENTITY_REAUDIT_REQUIRED`; fixtures/code/live verification
не создаются. Audit принят PR #136: head `9765e7d6bc3c2ca59ac0647f565bf1aab12849ef`, PR-head
run `29970355532`, merge `a3ac0d88759002468aa6a3d5cb5c6ba887ba9e26`, exact run
`29970713352`; обе matrix jobs успешны.

Отдельный identity/section audit сохраняет `ets_nep` и `fabrikant` disabled canonical placeholders
без guessed alias/migration: один operator подтверждён, но section/protocol boundary не доказана.
Будущая реализация имеет одного owner АО «ЭТС»; section views допустимы только после contract
evidence. Persisted settings/credentials/profiles/outcomes/artifacts/exports этим package не
меняются. Решение принято PR #137: head `e3550871a95f0c103ee7f6e2799ccc120c1d2ba4`, PR-head
run `29971869854`, merge `cd39b8e82d2ce208aa4498462c545f0fab894044`, exact run
`29972112388`; обе matrix jobs и dependency audit успешны.

Docs-only решением первые пять P6 sources сохраняются с принятыми blocker/identity verdicts, а
`sber_a` назначается только следующим последовательным access-audit target. Это не working/access
claim Сбербанк-АСТ: его сеть, endpoints, fixtures и код этим package не исследуются. Решение
принято PR #138: head `1ddc2d726a6279ffb94023c89d6d90fc82e2347d`, PR-head run
`29972908601`, merge `7d1e728a99c384acd72d3b7b13ab274378fe7d47`, exact run
`29973164497`; обе matrix jobs и dependency audit успешны.

Отдельный Сбербанк-АСТ read-only audit подтвердил official public human registries для 44-ФЗ и
223-ФЗ. Опубликованный machine API/feed contract, automation/data-reuse permission, schema/version,
pagination/completeness, rate/retry, timezone/currency/exact-money и raw retention rules не найдены;
robots закрывает основные document download/view routes. `sber_a` локально `BLOCKED_EXTERNAL`;
adapter/fixture/live verification не создаются. Audit принят PR #139: head
`eb9eb59a14709a42a13a0d8b6422a6e3e1c57ac2`, PR-head run `29973982757`, merge
`642f53bc812593ce2c1d2b1050d7c7e8d8319e2f`, exact run `29974214317`; обе matrix jobs и
dependency audit успешны.

Docs-only решением первые шесть P6 sources сохраняются с принятыми blocker/identity verdicts, а
`rts_tender` назначается только следующим последовательным access-audit target. Это не
working/access claim РТС-тендер: его сеть, endpoints, fixtures и код этим package не исследуются.
Решение принято PR #140: head `ca7a3c53841336d1cfe544ed5326b7d2160eef7f`, PR-head run
`29974875827`, merge `ffc2f4e8f8b3c0db502a4a26c2f8ea69b0a7931f`, exact run
`29975119548`; обе matrix jobs и dependency audit успешны.

Отдельный РТС-тендер read-only audit встретил официальный Anti-DDoS browser challenge/503 на
main и `robots.txt`; bypass не выполнялся. Section-specific public human cards существуют, но
machine API/feed, automation/data-reuse permission, schema/version, pagination/completeness,
rate/retry, timezone/currency/exact-money и raw retention rules не опубликованы. Common B2B-РТС
group ownership не является identity/protocol contract. `rts_tender` локально `BLOCKED_EXTERNAL`;
adapter/fixture/live verification не создаются. Audit принят PR #141: head
`00c0e6900e8d3390f8858d1fbdf9193695684ccf`, PR-head run `29975868619`, merge
`3944dbd0ec35bc358d5149a9cf005b27884b6570`, exact run `29976202290`; обе matrix jobs и
dependency audit успешны.

Docs-only решением первые семь P6 sources сохраняются с принятыми blocker/identity verdicts, а
`gazprombank` назначается только следующим последовательным access-audit target в позиции 8.
Это не working/access claim ЭТП ГПБ: его сеть, endpoints, fixtures и код этим package не
исследуются. Решение принято PR #142: head `8ad58579c5d9a54aec076741f891f95d06579c41`, PR-head
run `29976999580`, merge `cb94e62df7cc7a815693e586b559184868d52e5a`, exact run
`29977374982`; обе matrix jobs и dependency audit успешны.

Отдельный ЭТП ГПБ read-only audit нашёл явное official permission intent для RSS use в стороннем
ПО и точный published endpoint. Однако current/new host redirects заканчиваются final `404`, а
schema/version, pagination/completeness, rate/retry, timezone/currency/exact-money, retention и
approved fixtures не опубликованы. Human query/page scraping и отдельный account-oriented Trading
Portal API не используются как замена. `gazprombank` локально
`BLOCKED_EXTERNAL / PUBLISHED_FEED_UNAVAILABLE`; adapter/fixture/live verification не создаются.
Audit принят PR #143: head `8dcfbf6469747fc3e8644761693cc85a076d1b39`, PR-head run
`29978156861`, merge `102aff662f3cd068c13c095cb6470912cc0bfc60`, exact run
`29978439856`; обе matrix jobs и dependency audit успешны.

Docs-only boundary решением supporting implementation plan синхронизирован с каноническим ТЗ:
`gazprombank` остаётся только восьмым P6 source, P7 начинается с `b2b_center`. Последовательный
P6 access-audit pass завершён, но blocked sources не объявляются implemented/working и Collector
prerequisite не закрывается. Решение принято PR #144: head
`ddd3d37a7f13a10d45b29a1c3c5496f38ff9e1e8`, successful PR-head run `29979195455`, merge
`e54fd46d6525e378cd90795f35ae144f00fffe31`, fresh exact run `29979715877`; обе matrix jobs и
dependency audit успешны.

Отдельный B2B-Center read-only audit подтвердил официальный договорный API/web service, но method
catalog, documentation и XML examples доступны только после login в Личном кабинете и зависят от
договора/тарифа. Публичный Регламент запрещает automated collection без письменного согласия
Оператора и устанавливает ceiling 60 HTTP requests/minute. Подтверждённый entitlement/consent,
endpoint/method/auth, coverage, schema/version, pagination/completeness, API rate/retry,
timezone/money, retention/reuse и approved fixtures отсутствуют. `b2b_center`
`BLOCKED_EXTERNAL / CONTRACT_AND_PERMISSION_GATED`; HTML/login automation, adapter и fixtures не
создаются. Audit принят PR #145: head `d4c0f2fb41fe77c5df642884d29016af0cd0442c`, PR-head run
`29980582710`, merge `f7b20a4a5c5d0ee260b04721347c66b8ee2dad2a`, fresh exact run
`29980836778`; обе matrix jobs и dependency audit успешны. `fabrikant` назначается только следующим
P7 access-audit target без contract/readiness claim; отдельный audit начинается после
publication/exact docs-only transition package. Transition принят PR #146: head
`6fa6e3f93a188e39a71c9e9042cf3b41e770364a`, PR-head run `29981527538`, merge
`dfe1f95f194f494b9beb33dc5c6127d31f428ce4`, exact run `29981883362`; обе jobs успешны.

Фабрикант публикует documented SOAP/XML API для SRM-систем заказчика, но не source-wide tender
discovery/search feed. Organizer methods нельзя подменять Collector adapter; discovery permission,
coverage, pagination/completeness, rate/retry, retention/reuse и fixtures отсутствуют. `fabrikant`
`BLOCKED_EXTERNAL / PUBLISHED_API_SCOPE_MISMATCH`; adapter/fixtures не создаются. Audit принят PR
#147: head `403ec44abee9d0497485ac130b50dc3199351347`, PR-head run `29984554174`, merge
`bf2a44bea889b34689f63495013becae24d050fb`, exact run `29984821509`; обе jobs и dependency audit
успешны. `otc` назначается только следующим P7 access-audit target без contract/readiness claim;
отдельный audit начинается после publication/exact docs-only transition package. Transition принят
PR #148: head `3ba012506e147a4a8392e8a1dea75e153307e016`, PR-head run `29986076319`, merge
`5c087726e2cb32c88c6b9760d8b43b887da4234f`, exact run `29986457553`; обе jobs и dependency audit
успешны.

OTC публикует human search/detail pages и account CRM/EIS integration, но внешний source-wide
procurement discovery API/feed, automation/reuse permission, coverage, pagination/completeness,
schema/version, rate/retry, retention/reuse и fixtures отсутствуют. `otc` локально
`BLOCKED_EXTERNAL / PUBLIC_HTML_WITHOUT_MACHINE_CONTRACT`; HTML/XHR parser, adapter и fixtures не
создаются. Audit принят PR #149: head `f66feda46eb0432ca4bd2391c3caad7e59fc3a95`,
PR-head run `29987577868` attempt 2 успешен после transient native Windows failure attempt 1,
merge `023002df23273d01aad2630f92ae293d2dfc10f2`, fresh exact run `29988314604`; обе jobs и
dependency audit успешны.

Commercial-section matrix сопоставила восемь boundaries только с existing federal operator owners
в canonical P6 порядке. Принятые P6 section/blocker audits переиспользованы без новых identities,
повторных network audits или implementation claim; все позиции остаются `BLOCKED_EXTERNAL`.
Решение принято PR #150: head `fcfed01dbe006c5b80401a976cccbf06a66915a4`, PR-head run
`29989342548`, merge `b11b17a6481e933259dd4d52054ed93bc334d051`, fresh exact run
`29989656986`; jobs `89149333402`/`89149333355` и dependency audit успешны. P7 access-audit pass
завершён, но P7 implementation и Collector prerequisite не считаются `DONE`.

TenderGuru публикует реальный API v2.3 для тендеров с XML/JSON/CSV, pagination и
tariff-dependent fields, но для CorterisTenderAI не предоставлены product-specific
entitlement/license, account token/limits, data visibility/retention/reuse terms, completeness/
schema lifecycle/timezone/money contract или approved fixtures. `tenderguru_discovery` локально
`BLOCKED_EXTERNAL / ENTITLEMENT_AND_LICENSE_REQUIRED`; registration/login/API calls, producer,
credentials и fixtures не создаются. Existing aggregator queue/official-verification gate
переиспользуется и остаётся отдельно от 13 built-ins. Access audit принят PR #151: head
`205d223f67da8ca0fd84732b4b14aeb1c7402662`, PR-head run `29992310890`, merge
`29aba93a4cdb24ba526dbbe265f51e859ba9754a`, fresh exact run `29992951951`; jobs
`89159721376`/`89159721509` и dependency audit успешны после GitHub Actions incident/eventual
consistency.

P8 hardening принят PR #152: head `df91a4cdcb5923f31b7be4501e85cd25e7329485`,
PR-head run `29996521546` (jobs `89171378944`/`89171378841`), merge
`593ea5c7d3657e881fad985933444a44aa12b0f1`, fresh exact run `29996926693`
(jobs `89172697592`/`89172697637`); обе Windows-матрицы и dependency audit успешны. Existing
queue теперь имеет atomic capacity, bounded payload/attempt retention, explicit retry и
error/note/URL sanitization; full protected queue не блокирует authoritative service path.
TenderGuru producer/readiness не открываются. Текущий docs-only P8 closeout фиксирует честный
`BLOCKED_EXTERNAL` и открывает только P9 stabilization после собственного merge/exact gate.
P8 closeout принят PR #153: head `ead2de338628c5dd8b6ae7de19779ceec9dcc102`,
PR-head run `29997803117`, merge `f4fead191323f50c4b5d7a1359e24006c1a3bcb5`, fresh exact
run `29998310114`; jobs `89177176148`/`89177176164` и dependency audit успешны.

Текущий P9 audit package инвентаризирует stabilization gates и фиксирует expected-red для единого
all-provider no-network diagnostic и raw unexpected-health error sanitization. Stabilization
implementation, Collector closeout и production RM-156 до merge/exact audit не начинаются.
RM-157 и RM-158 не начинать.
