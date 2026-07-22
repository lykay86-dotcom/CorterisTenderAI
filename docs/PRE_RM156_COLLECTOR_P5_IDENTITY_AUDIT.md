# PRE-RM-156 Collector P5 — provider identity/catalog audit

Дата: 22 июля 2026 года.

Статус: `AUDIT COMPLETE`; application changes не начаты.

## 1. Entry gate и scope

- Exact baseline: P4 Mos Supplier merge `b4704480010a363e02ad80fe579d5c836cd04509`.
- PR #126 head `1943d57dc944490d1fd30051be289624b22d7f4b`; PR-head run `29946701032` и
  exact merge-SHA run `29947263908` успешны на Python 3.12/3.13, включая dependency audit.
- P5 ограничен identity/catalog/settings/DB/export compatibility. Provider adapters, live network,
  parser/fixtures, provider credentials values, deterministic score/recommendation и critical
  stop-factor priority не входят в scope.
- Target built-in IDs: `eis`, `mos_supplier`, `zakaz_rf`, `roseltorg`, `rad`, `tek_torg`,
  `ets_nep`, `sber_a`, `rts_tender`, `gazprombank`, `b2b_center`, `fabrikant`, `otc`.

## 2. Найденные владельцы и расхождения

| Boundary | Current owner | Evidence | P5 decision |
|---|---|---|---|
| Built-in descriptors | `canonical_provider_definitions()` | 10 IDs; unique IDs/sources | сохранить owner, расширить до exact 13 |
| Source enum | `TenderSource` | отсутствуют `zakaz_rf`, `rad`, `ets_nep` | добавить только identity values |
| Aliases | `provider_aliases()` | `sber_a/rts_tender/roseltorg` ошибочно направлены в `_commercial` | развернуть: `_commercial` становятся legacy aliases canonical IDs |
| Commercial definitions | `default_commercial_provider_definitions()` | пять canonical IDs и три `_commercial` | использовать 11 non-reference canonical descriptors; новые identities disabled/access-pending |
| Async factory | `create_default_async_providers()` | EIS/Mos и optional commercial catalog | сохранить factory; не создавать adapters для P5 identities |
| Legacy sync registry | `create_builtin_providers()` | отдельные 8 descriptors, generic `commercial`, нет Mos и части targets | проецировать canonical descriptors в inert placeholders; EIS остаётся existing real sync adapter |
| Manual catalog | `resolved_provider_catalog()` | collisions проверяются по built-ins и aliases | автоматически принять новый exact catalog/aliases |
| Settings | `ProviderEnablementRepository` schema 6 | aliases разрешаются при чтении, но canonical keys старые | schema 7, explicit v6 migration, backup, canonical write/readback |
| Legacy commercial settings | `CommercialProviderSettingsRepository` schema 1 | raw provider keys без alias migration | read-compatible alias normalization; canonical output только через mutation/export |
| Credentials | `provider_credential_descriptors()` | provider ID берётся из commercial definition | canonical provider ID, но старые keyring/env account names сохранить |
| Network settings | `CollectorNetworkSettings` | три keys имеют `_commercial` IDs | canonical keys; legacy lookup только через audited alias resolver |
| Collector DB | `CollectorSchemaMigrator` schema 15 | historical provider IDs хранятся в runs/outcomes/checkpoints/artifacts/pages | schema 16 alias registry; не переписывать historical rows |
| Export/read model | `get_run()`/`list_provider_outcomes()` → analytics/export | raw historical provider IDs выходят наружу | canonicalize known aliases; unknown identity не угадывать |
| Profiles/schedules | existing repositories + `canonical_provider_id()` at use boundary | read-compatible, файлы не переписываются | сохранить bytes; новые saves используют canonical IDs |

Baseline identity/settings/catalog/schema contour на exact P4 merge: `27 passed in 10.47s`.

## 3. Migration contract

### 3.1 Provider settings schema 7

- v6 читается отдельной migration branch со статусом `MIGRATED_V6`;
- `_commercial` keys разрешаются в `sber_a`, `rts_tender`, `roseltorg`;
- при alias+canonical collision canonical value имеет deterministic priority, alias игнорируется с
  bounded warning;
- первая mutation создаёт byte-exact v6 backup, пишет schema 7 atomic replace и выполняет readback;
- future/corrupt/manual registration safeguards сохраняются; secrets не записываются.

### 3.2 Collector DB schema 16

- добавить только `collector_provider_identity_aliases(alias_id, canonical_id, introduced_version)`;
- seed содержит три audited mappings `_commercial` → canonical;
- migration 15→16 использует existing inspect/verified-backup/transaction/readback contour;
- historical run/outcome/checkpoint/artifact/page rows не переписываются и не удаляются;
- canonical filters включают canonical ID и его audited legacy aliases; export/read model возвращает
  canonical ID. Unknown/ambiguous IDs сохраняются как unknown evidence и не mapped guessing.

### 3.3 Credential/network compatibility

- Provider-facing IDs становятся canonical;
- для Sber/RTS/Roseltorg сохраняются существующие environment names и keyring names
  `collector.*_commercial.api_key`, чтобы P5 не терял protected credentials;
- новые `zakaz_rf`, `rad`, `ets_nep` identities не получают working access claim, endpoint или
  credential value. Их descriptors disabled by default и `commercial_access_pending`.

## 4. Test-first contract

До implementation отдельный P5 suite обязан доказать:

1. exact 13 IDs и 13 unique `TenderSource` values во всех catalog projections;
2. только три audited legacy aliases, отсутствие canonical/alias/name/source collisions;
3. новые identities disabled/not configured и не делают сеть;
4. sync/async/commercial/manual catalogs не создают второй identity для одной source;
5. schema-6 settings migrate в schema 7 с backup, deterministic collision rule и readback;
6. schema-15 DB migrate в schema 16 с verified backup, alias registry и без row rewrite;
7. historical `_commercial` run/outcome export становится canonical, canonical filter видит legacy
   rows, unknown ID не получает guessed mapping;
8. legacy credential account names остаются прежними при canonical provider IDs;
9. profiles/schedules/manual registrations принимают aliases только read-compatibly и отвергают
   collisions;
10. full regression сохраняет P4 page/artifact/checkpoint и RM-107 deterministic boundaries.

## 5. Rollback

До merge — revert P5 commits. После schema 16 предпочтителен roll-forward: automatic downgrade и
удаление alias registry запрещены. Verified schema-15 backup может быть восстановлен только явной
операцией при подтверждённом отсутствии новых schema-16 данных. Settings v6 backup сохраняется;
profile/schedule, keyring, artifacts, accepted pages и historical rows rollback не удаляет.
