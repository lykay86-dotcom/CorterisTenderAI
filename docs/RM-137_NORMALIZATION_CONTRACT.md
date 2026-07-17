# RM-137 — канонический контракт нормализации

## Ownership

`UnifiedTender` остаётся единственной публичной доменной моделью.
`app.tenders.collector.normalizer.TenderNormalizer` является единственной pure/offline
границей канонической нормализации. `NormalizedTender` — существующий внутренний результат
Collector; он расширяется metadata, но не становится второй root-моделью.

Версия контракта: `TENDER_NORMALIZATION_CONTRACT_VERSION = 1`.

## Результат

Успешный результат содержит canonical `UnifiedTender`, существующие identity aliases,
comparison fields, versioned semantic fingerprint, stable bounded diagnostics и safe
field-level provenance. Порядок diagnostics/provenance детерминирован.

Диагностика различает: missing, invalid, unsupported/unmapped, conflict, lossy transform,
unsafe URL, naive/ambiguous datetime и invalid money. Она содержит только stable code,
severity, canonical field, allowlisted source path, provider ID, bounded message и
recoverability; raw values, query, credentials, response bodies и private paths запрещены.

Provenance содержит provider ID, canonical/source field, transform ID, outcome и безопасную
source identity. Normalization никогда не присваивает `verified=True`; существующий
verification owner остаётся единственным владельцем trust/conflict resolution.

## Field policies

- Required identity: trim boundary whitespace, Unicode NFC, leading zeros сохраняются; нельзя
  генерировать purchase number из URL/title. Пустой required identity fail-closed.
- Text: NFC, CRLF/CR -> LF, unsafe control chars удаляются, boundary whitespace trim,
  ограничение длины. Title/customer не переписываются и не классифицируются по keywords.
- Money: canonical amount только finite non-negative `Decimal`; `float` не принимается strict
  tender boundary; zero отличается от missing; currency — отдельный explicit ISO code.
- Datetime: в normalized output только aware value, canonical instant UTC; naive/ambiguous
  optional value становится missing с diagnostic, без локализации по timezone машины.
- Status/procedure: только typed enum; unknown остаётся `UNKNOWN`.
- Law/region/classifiers: консервативный trim/NFC; common boundary ничего не угадывает.
- URL: offline; только absolute HTTP(S), без userinfo/control chars; query/fragment удаляются из
  safe provenance/fingerprint, но source URL сохраняется совместимо, если он безопасен.
- Collections: bounded, exact dedup, stable order; classifier leading zeros сохраняются.
- Raw metadata: не является source of truth; normalization metadata содержит только безопасные
  значения и не копирует secrets в diagnostics/provenance.

## Semantic fingerprint

Существующий `content_hash` остаётся владельцем normalized semantic fingerprint. Его payload
включает contract version и canonical decision-relevant values. Decimal — lossless string,
datetime — aware UTC ISO 8601, keys/collections — stable. Volatile timestamps, diagnostic text,
raw metadata и query parameters не входят.

`duplicate_hash`, identity key, document checksum и analysis fingerprint остаются отдельными
семантиками и не смешиваются.

## Side effects and failures

Normalizer не выполняет network/DNS/redirect, credential read, filesystem/SQLite, UI, current
time, AI, scoring или recommendation. Invalid optional field удаляется с diagnostic. Invalid
required identity отклоняет только запись на существующей batch boundary; исключение не должно
ронять соседние записи. Никакой default не превращает unknown в факт.

## Compatibility

Collector schema 14 и Registry schema 1 не меняются. Legacy payload readers продолжают читать
schema v1/unversioned JSON, включая исторические naive timestamps; strict invariants применяются
при новом normalization, без destructive rewrite. Manual provider remains disabled unless the
existing RM-136 health/admission contract разрешает запуск.
