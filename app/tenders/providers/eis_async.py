"""Native asynchronous connector for the official public EIS pages.

The provider intentionally identifies itself as ``public_html_async``.  It
uses only public, unauthenticated pages and does not claim access to an
official API or XML change feed.  CAPTCHA and access-protection pages are
reported to the user and are never bypassed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Sequence

from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpError,
)
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.eis_checkpoint import (
    EisCheckpointCoordinator,
    EisCheckpointPolicy,
)
from app.tenders.collector.network_settings import (
    ProviderNetworkSettings,
    default_collector_network_settings,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderDocument, TenderSource, UnifiedTender
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderProviderError,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.providers.eis import (
    EisAccessBlockedError,
    EisHtmlParser,
    EisParseError,
    EisProviderConfig,
    build_eis_search_url,
    eis_documents_url,
    matches_eis_query,
)
from app.tenders.providers.eis_parser.detail_router import (
    detect_law,
    merge_tender_details,
    parse_detail,
    resolve_detail_url,
)
from app.tenders.providers.eis_parser.documents_parser import DOCUMENTS_PARSER_VERSION
from app.tenders.providers.eis_parser.models import EisHealthReport
from app.tenders.providers.eis_parser.search_parser import SEARCH_PARSER_VERSION
from app.tenders.providers.eis_parser.snapshots import EisSnapshotWriter
from app.tenders.providers.eis_parser.validation import validate_eis_url


class AsyncEisTenderProvider(AsyncTenderProvider):
    """Non-blocking EIS provider using the shared HTML parser."""

    descriptor = ProviderDescriptor(
        id="eis",
        display_name="ЕИС Закупки",
        source=TenderSource.EIS,
        homepage_url="https://zakupki.gov.ru/",
        capabilities=ProviderCapabilities(
            search=True,
            tender_details=True,
            documents=True,
            authentication=False,
            public_api=False,
            incremental_updates=True,
            rate_limit_per_minute=30,
        ),
        priority=10,
        implementation_status="public_html_async",
    )
    connection_mode = "public_html_async"
    parser_version = SEARCH_PARSER_VERSION
    documents_parser_version = DOCUMENTS_PARSER_VERSION

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        config: EisProviderConfig | None = None,
        network_settings: ProviderNetworkSettings | None = None,
        checkpoint_repository: CollectorStateRepository | None = None,
        checkpoint_policy: EisCheckpointPolicy | None = None,
        snapshot_directory: Path | None = None,
    ) -> None:
        self.http_client = http_client
        self.config = config or EisProviderConfig()
        self.network_settings = network_settings or (
            default_collector_network_settings().get("eis")
        )
        self.parser = EisHtmlParser(base_url=self.config.base_url)
        self.checkpoints = EisCheckpointCoordinator(
            checkpoint_repository,
            policy=checkpoint_policy,
        )
        self.snapshots = EisSnapshotWriter(snapshot_directory)

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        prepared = self.checkpoints.prepare(query)
        url, rounded_page_size = build_eis_search_url(
            prepared.query,
            self.config,
        )
        response = await self._get(
            url,
            cancellation_token=cancellation_token,
        )
        self.snapshots.save_html("search", response.text())
        try:
            parsed = self.parser.parse_search(response.text())
        except EisAccessBlockedError:
            raise
        except EisParseError:
            raise
        except Exception as exc:
            raise EisParseError(f"Не удалось разобрать ответ поиска ЕИС: {exc}") from exc

        warnings = list(parsed.warnings)
        warnings.extend(prepared.warnings)
        warnings.append(
            "Использован публичный HTML-интерфейс ЕИС в нативном "
            "асинхронном режиме; это не официальный API."
        )
        if rounded_page_size != prepared.query.page_size:
            warnings.append(
                f"Размер страницы ЕИС округлён: {prepared.query.page_size} → {rounded_page_size}."
            )
        if prepared.query.regions:
            warnings.append(
                "Региональный фильтр применяется к данным карточки; "
                "тендеры без региона сохраняются."
            )

        items = tuple(item for item in parsed.items if matches_eis_query(item, prepared.query))[
            : prepared.query.page_size
        ]
        result = TenderSearchResult(
            provider_id=self.descriptor.id,
            items=items,
            total=parsed.total,
            page=prepared.query.page,
            page_size=prepared.query.page_size,
            next_page_token=(
                str(prepared.query.page + 1)
                if parsed.total is None or prepared.query.page * rounded_page_size < parsed.total
                else ""
            ),
            warnings=tuple(dict.fromkeys(warnings)),
        )
        self.checkpoints.mark_success(prepared, result)
        return result

    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        normalized = external_id.strip()
        if not normalized:
            raise ValueError("external_id must not be empty")

        result = await self.search(
            TenderSearchQuery(
                keywords=(normalized,),
                page=1,
                page_size=10,
                extra={
                    "exact_search": True,
                    "incremental": False,
                },
            ),
            cancellation_token=cancellation_token,
        )
        for item in result.items:
            if normalized in {
                item.external_id,
                item.procurement_number,
            }:
                law = detect_law(search_law=item.law, url=item.source_url)
                detail_url = resolve_detail_url(
                    external_id=normalized,
                    source_url=item.source_url,
                    law=law,
                    base_url=self.config.base_url,
                )
                response = await self._get(
                    detail_url,
                    cancellation_token=cancellation_token,
                )
                page_kind = "notice_223" if law.value == "223-FZ" else "notice_44"
                self.snapshots.save_html(page_kind, response.text())
                try:
                    details = parse_detail(
                        response.text(),
                        source_url=detail_url,
                        law=law,
                    )
                except Exception as exc:
                    self.snapshots.save_error(page_kind, exc)
                    raise
                return merge_tender_details(item, details)
        raise TenderProviderError(f"Закупка ЕИС {normalized} не найдена")

    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        tender = await self.get_tender(
            external_id,
            cancellation_token=cancellation_token,
        )
        response = await self._get(
            eis_documents_url(tender.source_url),
            cancellation_token=cancellation_token,
        )
        try:
            return self.parser.parse_documents(response.text())
        except EisAccessBlockedError:
            raise
        except EisParseError:
            raise
        except Exception as exc:
            raise EisParseError(f"Не удалось разобрать документы ЕИС: {exc}") from exc

    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        started = perf_counter()
        checked_at = _utc_now()
        report = await self.check_health_components(cancellation_token=cancellation_token)

        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=report.status,
            checked_at=checked_at,
            message=(
                "public_html_async; "
                f"network={report.network_status.value}: {report.network_message}; "
                f"parser={report.parser_status.value}: {report.parser_message}"
            ),
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
        )

    async def check_health_components(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> EisHealthReport:
        """Run one read-only search probe and report network/parser health separately."""

        url, _ = build_eis_search_url(
            TenderSearchQuery(page=1, page_size=10, extra={"incremental": False}),
            self.config,
        )
        try:
            response = await self._get(
                url,
                cancellation_token=cancellation_token,
                raise_for_status=False,
            )
        except EisAccessBlockedError as exc:
            return EisHealthReport(
                network_status=ProviderHealthStatus.DEGRADED,
                parser_status=ProviderHealthStatus.DEGRADED,
                network_message=str(exc),
                parser_message="access protection page was not parsed",
            )
        except TenderProviderError as exc:
            return EisHealthReport(
                network_status=ProviderHealthStatus.UNAVAILABLE,
                parser_status=ProviderHealthStatus.UNKNOWN,
                network_message=str(exc),
                parser_message="parser probe was not run",
            )
        if response.status_code != 200:
            if response.status_code == 403:
                return EisHealthReport(
                    network_status=ProviderHealthStatus.DEGRADED,
                    parser_status=ProviderHealthStatus.DEGRADED,
                    network_message="HTTP 403 access protection",
                    parser_message="access protection page was not parsed",
                )
            return EisHealthReport(
                network_status=ProviderHealthStatus.UNAVAILABLE,
                parser_status=ProviderHealthStatus.UNKNOWN,
                network_message=f"HTTP {response.status_code}",
                parser_message="parser probe was not run",
            )
        try:
            parsed = self.parser.parse_search(response.text())
        except TenderProviderError as exc:
            return EisHealthReport(
                network_status=ProviderHealthStatus.AVAILABLE,
                parser_status=ProviderHealthStatus.DEGRADED,
                network_message="public search page returned HTTP 200",
                parser_message=str(exc),
            )
        return EisHealthReport(
            network_status=ProviderHealthStatus.AVAILABLE,
            parser_status=ProviderHealthStatus.AVAILABLE,
            network_message="public search page returned HTTP 200",
            parser_message="search page contract is valid",
            diagnostics=parsed.diagnostics,
        )

    def validate_configuration(self) -> tuple[str, ...]:
        return (
            "Используется официальный публичный веб-интерфейс ЕИС "
            "без авторизации и без обхода CAPTCHA.",
            "Режим public_html_async не является официальным API; "
            "при изменении верстки потребуется обновление парсера.",
            "Инкрементальный checkpoint использует скользящее окно "
            "публикации и не заменяет официальный журнал изменений.",
        )

    async def _get(
        self,
        url: str,
        *,
        cancellation_token: CollectorCancellationToken | None,
        raise_for_status: bool = True,
    ):
        safe_url = validate_eis_url(url, base_url=self.config.base_url)
        try:
            return await self.http_client.get(
                safe_url,
                provider_id=self.descriptor.id,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                    "Accept-Encoding": "identity",
                    "Cache-Control": "no-cache",
                },
                timeouts=self.network_settings.timeouts,
                retry_policy=self.network_settings.retry,
                cancellation_token=cancellation_token,
                raise_for_status=raise_for_status,
            )
        except AsyncHttpError as exc:
            detail = str(exc)
            if exc.status_code == 403:
                raise EisAccessBlockedError(
                    "ЕИС отклонила публичный запрос (HTTP 403); "
                    "автоматический обход защиты не выполняется"
                )
            elif "timeout" in detail.casefold():
                detail = f"истёк сетевой тайм-аут ЕИС после {exc.attempts} попыток: {detail}"
            raise TenderProviderError(f"Ошибка подключения к ЕИС: {detail}") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = ["AsyncEisTenderProvider"]
