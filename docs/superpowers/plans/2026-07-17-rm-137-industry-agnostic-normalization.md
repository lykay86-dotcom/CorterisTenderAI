# RM-137 — план отраслево-независимой нормализации

Baseline: `cf60941a94bc4023edfa73cba65885f9c6b16b8c`.

1. Зафиксировать audit/contract/plan отдельным docs-only commit.
2. Добавить expected-red tests для contract version, strict Decimal, aware UTC dates, stable
   diagnostics/provenance/fingerprint, bounded collections, safe URL и absence of side effects.
3. Расширить существующие `NormalizedTender`/`TenderNormalizer`; новый root type, repository,
   DB и search engine не создавать.
4. Канонизировать valid `UnifiedTender` консервативно: identifiers/text/collections/URLs,
   Decimal и datetimes; добавить typed bounded diagnostics и safe provenance.
5. Включить contract version в существующий `content_hash` как semantic fingerprint; оставить
   identity, duplicate hash и document checksum независимыми.
6. Направить Collector и legacy provider-result path через один normalizer. Manual API/RSS/FTP/
   FTPS покрыть offline preview fixtures, не меняя enablement/admission или transport.
7. Сохранить Collector schema 14, Registry schema 1 и legacy payload read; migration не нужна.
8. Запустить focused tests, provider/codec/dedup/registry/freshness/RM-107 neighbors, затем полный
   workflow contour: secret scan, Ruff, format, mypy, smokes, full pytest, pip-audit, diff-check.
9. Зафиксировать acceptance evidence, открыть feature PR, дождаться Windows Quality Gate 3.12/
   3.13 и exact merge-SHA gate.
10. Только после exact-SHA success выполнить отдельный docs-only closeout и активировать RM-138.

Scope guard: не добавлять parallel search, monitoring, scheduler redesign, provider/network
transport, industry ranking, AI, UI tab или storage architecture.
