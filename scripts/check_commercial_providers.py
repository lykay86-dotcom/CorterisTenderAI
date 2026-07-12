"""Show commercial-provider readiness without making network requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.tenders.providers.commercial_catalog import (
    create_commercial_provider_catalog,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Проверить локальную готовность коммерческих провайдеров "
            "без обращения к внешним площадкам."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести структурированный JSON без секретов.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings_path = (
        get_settings().data_dir / "commercial_providers.json"
    )
    catalog = create_commercial_provider_catalog(
        settings_path=settings_path
    )
    payload = catalog.public_payload()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Corteris Tender Collector — коммерческие источники")
    print(f"Настройки: {settings_path}")
    print("Сетевые запросы не выполняются.\n")
    for item in payload:
        print(
            f"[{item['state']}] {item['display_name']} "
            f"({item['provider_id']})"
        )
        print(f"  {item['message']}")
        print(
            "  API key: "
            + ("настроен" if item["api_key_configured"] else "не настроен")
        )
        print(f"  Рабочее подключение: {item['working']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
