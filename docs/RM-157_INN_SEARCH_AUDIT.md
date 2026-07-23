# RM-157 — аудит поиска контрагента по ИНН

Дата: 23 июля 2026 года.

Статус: `AUDIT COMPLETE / IMPLEMENTATION NOT STARTED`.

Audit base: `d4f05be338f28dc79a0b80aba88b7ddc8115fd4c`
(`Merge pull request #160 ... rm156-contractor-closeout`).

## 1. Решение

RM-157 должен добавить один детерминированный offline use case точного поиска сохранённого
контрагента по каноническому ИНН и один пользовательский путь к нему. Он переиспользует
`ContractorInn`, `ContractorRepository`, `UnitOfWork`, canonical route registry и composition
root. Он не создаёт второй search engine, repository, session owner или contractor model.

Поиск RM-157 только читает локальный contractor master-record. Валидный, но отсутствующий ИНН
возвращает честный `NOT_FOUND`; поиск не создаёт запись, не восстанавливает soft-deleted запись,
не обращается к сети и не выдаёт tender customer observation за сведения о контрагенте.

Внешние источники и provenance начинаются только в RM-158. КПП, ОГРН, название, адрес,
руководитель и официальный статус принадлежат RM-159; risk/score/report scope RM-160–RM-168 не
начинается.

## 2. Entry gate

RM-156 принят полностью:

- feature PR #159 head `77b7079d84045eada3afbae9a4a64d34de1de498`;
- feature PR-head run `30011094847`, jobs `89219098426`/`89219098659`, successful;
- feature merge `f06b8a98f8684df7cc68ef30f015b6f118baac16`;
- feature exact run `30011757427`, jobs `89221369306`/`89221369290`, successful;
- closeout PR #160 head `be2d8a57550cbfb7681c7d04ae37cfe0f884ae8b`;
- closeout PR-head run `30012713595`, jobs `89224670514`/`89224670722`, successful;
- closeout merge `d4f05be338f28dc79a0b80aba88b7ddc8115fd4c`;
- closeout exact run `30013255344`, jobs `89226533422`/`89226533373`, successful;
- dependency audit successful в каждой matrix job.

RM-157 — единственный `IN PROGRESS`; RM-158–RM-200 остаются `PLANNED`.

Локальный неизменённый baseline:

```text
tests/test_rm156_contractor_model_expected_red.py
tests/test_rm142_route_registry.py
tests/test_rm155_compatibility_characterization.py
tests/test_bootstrap_tender_search_integration.py

48 passed in 9.40s
```

## 3. Инвентаризация владельцев

| Surface | Фактический смысл | Решение RM-157 |
|---|---|---|
| `ContractorInn` | единственный canonical parser/checksum owner ИНН контрагента | `REUSE`; UI/service не дублируют validation |
| `ContractorRepository.get_by_inn()` | exact local persistence lookup; soft-deleted rows скрыты по умолчанию | `REUSE`; не расширять сетью или presentation logic |
| `UnitOfWork.contractors` | canonical transaction/session access path | `REUSE`; application service управляет коротким read lifecycle |
| ORM `Contractor` | RM-156 identity/audit master-record | `REUSE`; не возвращать attached ORM object за пределы UoW |
| `CompanyRepository.get_by_inn()` | lookup собственной ООО «КОРТЕРИС» | `KEEP SEPARATE`; не использовать для counterparty search |
| `TenderCustomer`, tender registry/dialog search | source observations и поиск закупок | `KEEP SEPARATE`; не master-record и не fallback RM-157 |
| `app.tenders.search_engine` и unified tender search | multi-provider tender search owner | `KEEP SEPARATE`; второй contractor search engine запрещён |
| `RouteId.FUTURE_CLIENTS`, alias `clients` | retained RM-142/RM-155 compatibility identity, hidden `PLANNED`, stale `planned_rm_156` | `MIGRATE IN PLACE`; сохранить stable ID/alias, активировать единственный destination с title «Контрагенты» |
| `ModernMainWindow`, route registry/router | canonical shell/navigation/page ownership | `REUSE`; одна contractor page, без второго shell/router |
| `bootstrap()` / database startup pipeline | composition/data-path/schema owners | `REUSE`; inject service/controller, не открывать БД из widget |
| Figma node `41:35` | canonical large-screen visual reference | `INSPECT BEFORE UI CODE`; адаптировать, не копировать sample data |

## 4. Обнаруженные gaps

1. Repository primitive существует, но application-level exact-INN query/result contract
   отсутствует.
2. Нет immutable detached result projection; возврат ORM entity из закрытого UoW сделал бы
   lifecycle неявным.
3. Нет доказательства, что invalid INN отклоняется до repository/session/network work.
4. Нет явных `FOUND`/`NOT_FOUND` states и контракта, что lookup read-only.
5. Soft-deleted contractor не должен появляться или автоматически восстанавливаться.
6. Canonical route `future.clients` скрыт, имеет устаревший `planned_rm_156`, английский legacy
   alias и не имеет destination/page. Его нельзя удалить или переименовать без сохранения
   RM-142/RM-155 compatibility.
7. В shell/bootstrap нет contractor page/controller/service injection.
8. Нет headless/application/UI/accessibility tests для точного поиска, invalid/not-found/found
   transitions и очистки stale result.

## 5. Границы implementation package

RM-157 включает только:

- typed exact-INN query/result contract с `FOUND` и `NOT_FOUND`;
- read-only application service поверх injected UoW/repository owner;
- detached projection только RM-156 полей: ID, INN, audit timestamps и row version;
- invalid-input fail-fast без repository/session/network side effects;
- soft-delete isolation и отсутствие implicit create/restore;
- in-place activation сохранённого compatibility route как страницы «Контрагенты»;
- один controller/page path с вводом ИНН, search action и honest invalid/not-found/found states;
- keyboard/accessibility/headless tests и composition injection;
- Figma inspection exact target node до первого UI production edit.

RM-157 не включает:

- HTTP, browser automation, provider adapters, keyring или external fixtures;
- автоматическое создание contractor record после `NOT_FOUND`;
- fallback к собственной `Company` или `TenderCustomer`;
- fuzzy/name/KPP/OGRN/full-text search, suggestions, recent-list или bulk import;
- schema/data migration, новые dependencies или изменение Collector schema 16;
- registration/source/provenance/risk/score/chart/note/report fields RM-158–RM-168;
- AI и изменение RM-107 score/recommendation/critical stop-factor priority.

## 6. Expected-red contract

Следующий отдельный tests-only package должен зафиксировать strict expected-red boundaries:

1. canonical trim/checksum path без второго INN parser;
2. found detached projection и exact identity;
3. valid not-found без mutation;
4. invalid type/length/checksum без repository/UoW/network access;
5. soft-deleted row hidden, без restore;
6. repository/infrastructure failure sanitization без утечки paths/SQL;
7. retained `future.clients` identity и `clients` alias при title «Контрагенты»;
8. единственный available primary contractor route/destination/page owner;
9. page states invalid/not-found/found и stale-result clearing;
10. Enter/button parity, focus/accessible names и deterministic Russian status text;
11. bootstrap injection и shutdown без leaked session/thread;
12. import/offline guard, запрещающий RM-158 source/network dependencies.

Expected-red assertions нельзя ослаблять ради implementation. UI assertions определяются после
обязательного inspection Figma node `41:35`.

## 7. Stop conditions и rollback

Остановить implementation, если требуется угадать источник, сетевой contract или сведения
RM-159+, доверить tender observation, смешать собственную компанию и контрагента, создать второй
search/router/repository/session owner, сломать retained `clients` alias или изменить RM-107
deterministic priority.

Audit package docs-only. Rollback — revert audit merge; schema/data/settings/dependencies не
меняются.
