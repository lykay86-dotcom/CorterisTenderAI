# ruff: noqa: E402
"""One-request, read-only live canary for the public EIS search parser."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tenders.collector.network_runtime import create_collector_network_runtime
from app.tenders.collector.codec import tender_to_payload
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.providers.eis_async import AsyncEisTenderProvider


async def _run(search_text: str, limit: int) -> int:
    async with create_collector_network_runtime() as runtime:
        provider = AsyncEisTenderProvider(
            runtime.http_client,
            network_settings=runtime.settings.get("eis"),
        )
        try:
            result = await provider.search(
                TenderSearchQuery(
                    keywords=(search_text.strip(),) if search_text.strip() else (),
                    page=1,
                    page_size=limit,
                    extra={"incremental": False},
                )
            )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "provider": "eis",
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

        diagnostics = None
        if result.items:
            diagnostics = result.items[0].raw_metadata.get("eis_parse_diagnostics")
        print(
            json.dumps(
                {
                    "provider": provider.descriptor.id,
                    "connection_mode": provider.connection_mode,
                    "parser_version": provider.parser_version,
                    "ok": True,
                    "total": result.total,
                    "count": len(result.items),
                    "diagnostics": diagnostics,
                    "items": [tender_to_payload(item) for item in result.items[:limit]],
                    "warnings": list(result.warnings),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only EIS parser canary: one public search request, no registry, AI, "
            "document downloads or protection bypass."
        )
    )
    parser.add_argument("--search", default="оборудование")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=10)
    args = parser.parse_args()
    return asyncio.run(_run(args.search, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
