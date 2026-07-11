"""Manual connectivity check for the native asynchronous EIS provider."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.provider_base import TenderSearchQuery


async def _run(search_text: str) -> int:
    async with create_collector_network_runtime() as runtime:
        provider = create_default_async_providers(runtime)[0]
        health = await provider.check_health()
        print(f"provider={health.provider_id}")
        print(f"status={health.status.value}")
        print(f"latency_ms={health.latency_ms}")
        print(f"message={health.message}")
        print(f"mode={provider.connection_mode}")

        if not search_text.strip():
            return 0 if health.status.value in {"available", "degraded"} else 2

        result = await provider.search(
            TenderSearchQuery(
                keywords=(search_text.strip(),),
                page=1,
                page_size=10,
                extra={"incremental": False},
            )
        )
        print(f"items={len(result.items)}")
        print(f"total={result.total}")
        for item in result.items[:5]:
            print(
                f"- {item.procurement_number}: {item.title} "
                f"[{item.source_url}]"
            )
        for warning in result.warnings:
            print(f"warning={warning}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Проверка публичного асинхронного подключения к ЕИС. "
            "CAPTCHA и ограничения сайта не обходятся."
        )
    )
    parser.add_argument(
        "--search",
        default="",
        help="Необязательная тестовая поисковая фраза.",
    )
    arguments = parser.parse_args()
    return asyncio.run(_run(arguments.search))


if __name__ == "__main__":
    raise SystemExit(main())
