"""Manual diagnostic for the official Moscow Supplier Portal API.

The script never prints the bearer token. It exits with code 2 when the token
is absent and with code 1 when the API check fails.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.providers.mos_supplier_api import (
    AsyncMosSupplierTenderProvider,
    MosSupplierApiConfig,
)


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(type(value).__name__)


async def _run(args: argparse.Namespace) -> int:
    config = MosSupplierApiConfig.from_environment()
    if not config.configured:
        print(
            "Портал поставщиков не настроен. Задайте "
            "CORTERIS_MOS_API_KEY в текущем окружении.",
            file=sys.stderr,
        )
        return 2

    runtime = create_collector_network_runtime()
    provider = AsyncMosSupplierTenderProvider(
        runtime.http_client,
        config=config,
        network_settings=runtime.settings.get("mos_supplier"),
    )
    try:
        health = await provider.check_health()
        output: dict[str, object] = {
            "provider": provider.descriptor.id,
            "status": health.status.value,
            "message": health.message,
            "latency_ms": health.latency_ms,
            "connection_mode": provider.connection_mode,
            "token": config.masked_token,
        }
        if args.id:
            output["tender"] = await provider.get_tender(args.id)
        elif args.search:
            result = await provider.search(
                TenderSearchQuery(
                    keywords=(args.search,),
                    page=1,
                    page_size=args.limit,
                    extra={"incremental": False},
                )
            )
            output["total"] = result.total
            output["items"] = result.items
            output["warnings"] = result.warnings

        rendered = json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        print(rendered)
        if args.save:
            target = Path(args.save).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            print(f"Сохранено: {target}", file=sys.stderr)
        return 0 if health.status.value == "available" else 1
    finally:
        await runtime.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверка официального API Портала поставщиков Москвы"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--search", help="Тестовый поисковый запрос")
    group.add_argument("--id", help="ID котировочной сессии")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--save",
        help="Сохранить нормализованный диагностический результат в JSON",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
