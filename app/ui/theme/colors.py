"""Цветовая система интерфейса Corteris Tender AI.

Модуль не зависит от PySide6 и может использоваться в:
- Qt Style Sheets;
- виджетах;
- графиках;
- HTML-отчётах;
- тестах дизайн-системы.

Все цвета хранятся в формате ``#RRGGBB`` или ``#RRGGBBAA``.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Final, Iterator, Mapping

_HEX_COLOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")


class ThemeName(StrEnum):
    """Поддерживаемые темы интерфейса."""

    DARK = "dark"
    LIGHT = "light"


class SemanticColor(StrEnum):
    """Семантические роли цветов для статусов и уведомлений."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """Полная палитра одной темы Corteris Tender AI."""

    name: ThemeName

    # Бренд
    brand_primary: str
    brand_primary_hover: str
    brand_primary_pressed: str
    brand_secondary: str
    brand_accent: str
    brand_accent_soft: str

    # Основные поверхности
    app_background: str
    sidebar_background: str
    topbar_background: str
    panel_background: str
    card_background: str
    elevated_background: str
    input_background: str
    hover_background: str
    selected_background: str

    # Текст
    text_primary: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    text_on_brand: str
    text_on_danger: str

    # Границы и разделители
    border_default: str
    border_subtle: str
    border_strong: str
    focus_ring: str
    divider: str

    # Статусы
    info: str
    info_background: str
    success: str
    success_background: str
    warning: str
    warning_background: str
    danger: str
    danger_background: str
    neutral: str
    neutral_background: str

    # Графики
    chart_1: str
    chart_2: str
    chart_3: str
    chart_4: str
    chart_5: str
    chart_6: str
    chart_grid: str
    chart_axis: str

    # Дополнительные состояния
    overlay: str
    shadow: str
    scrollbar: str
    scrollbar_hover: str

    def __post_init__(self) -> None:
        """Проверяет корректность всех цветовых значений."""
        for item in fields(self):
            if item.name == "name":
                continue
            value = getattr(self, item.name)
            if not isinstance(value, str) or not _HEX_COLOR_PATTERN.fullmatch(value):
                raise ValueError(
                    f"Некорректный цвет {item.name!r}: {value!r}. Ожидается #RRGGBB или #RRGGBBAA."
                )

    def __iter__(self) -> Iterator[tuple[str, str]]:
        """Позволяет перебирать палитру как пары ``имя, значение``."""
        for item in fields(self):
            if item.name != "name":
                yield item.name, getattr(self, item.name)

    def as_dict(self) -> dict[str, str]:
        """Возвращает копию палитры в виде словаря."""
        return dict(self)

    def qss_variables(self, prefix: str = "corteris") -> dict[str, str]:
        """Возвращает имена токенов, удобные для генератора QSS."""
        normalized_prefix = prefix.strip().replace(" ", "-").lower()
        if not normalized_prefix:
            raise ValueError("Префикс QSS не может быть пустым.")
        return {f"{normalized_prefix}-{name.replace('_', '-')}": value for name, value in self}

    def semantic(self, role: SemanticColor) -> tuple[str, str]:
        """Возвращает основной и фоновый цвет семантической роли."""
        mapping = {
            SemanticColor.INFO: (self.info, self.info_background),
            SemanticColor.SUCCESS: (self.success, self.success_background),
            SemanticColor.WARNING: (self.warning, self.warning_background),
            SemanticColor.DANGER: (self.danger, self.danger_background),
            SemanticColor.NEUTRAL: (self.neutral, self.neutral_background),
        }
        return mapping[role]


DARK_PALETTE: Final[ThemePalette] = ThemePalette(
    name=ThemeName.DARK,
    brand_primary="#1D81CF",
    brand_primary_hover="#2C93E2",
    brand_primary_pressed="#176AA9",
    brand_secondary="#62B5DD",
    brand_accent="#41C7F4",
    brand_accent_soft="#163D52",
    app_background="#0E1420",
    sidebar_background="#111A28",
    topbar_background="#131D2B",
    panel_background="#151F2E",
    card_background="#182332",
    elevated_background="#1D2A3B",
    input_background="#111A27",
    hover_background="#202E40",
    selected_background="#173B59",
    text_primary="#F4F7FB",
    text_secondary="#C1CBD8",
    text_muted="#8492A6",
    text_disabled="#586477",
    text_on_brand="#FFFFFF",
    text_on_danger="#FFFFFF",
    border_default="#2B3A4D",
    border_subtle="#223043",
    border_strong="#40536B",
    focus_ring="#41C7F4",
    divider="#263548",
    info="#56B4E9",
    info_background="#153348",
    success="#4FD18B",
    success_background="#143A2B",
    warning="#F6C85F",
    warning_background="#433518",
    danger="#F26B6B",
    danger_background="#482126",
    neutral="#9AA7B8",
    neutral_background="#293443",
    chart_1="#41C7F4",
    chart_2="#4FD18B",
    chart_3="#F6C85F",
    chart_4="#A98BFF",
    chart_5="#F28E5B",
    chart_6="#65A7FF",
    chart_grid="#2A394C",
    chart_axis="#8D9AAF",
    overlay="#05080DB8",
    shadow="#00000066",
    scrollbar="#34465C",
    scrollbar_hover="#4A6079",
)


LIGHT_PALETTE: Final[ThemePalette] = ThemePalette(
    name=ThemeName.LIGHT,
    brand_primary="#1D81CF",
    brand_primary_hover="#176FAA",
    brand_primary_pressed="#125C8E",
    brand_secondary="#4EA4D1",
    brand_accent="#159ED1",
    brand_accent_soft="#DDF4FC",
    app_background="#F3F6FA",
    sidebar_background="#FFFFFF",
    topbar_background="#FFFFFF",
    panel_background="#F8FAFC",
    card_background="#FFFFFF",
    elevated_background="#FFFFFF",
    input_background="#F5F7FA",
    hover_background="#EBF2F8",
    selected_background="#DCEEFE",
    text_primary="#182334",
    text_secondary="#46566A",
    text_muted="#748399",
    text_disabled="#A6B0BE",
    text_on_brand="#FFFFFF",
    text_on_danger="#FFFFFF",
    border_default="#D5DEE9",
    border_subtle="#E5EBF2",
    border_strong="#A9B8CA",
    focus_ring="#1D81CF",
    divider="#DFE6EE",
    info="#2176AE",
    info_background="#E0F1FB",
    success="#218C5A",
    success_background="#DFF4E9",
    warning="#A86A00",
    warning_background="#FFF1CF",
    danger="#C63C43",
    danger_background="#FDE4E5",
    neutral="#607086",
    neutral_background="#E9EEF4",
    chart_1="#1D81CF",
    chart_2="#218C5A",
    chart_3="#D28B13",
    chart_4="#7458C8",
    chart_5="#C85C32",
    chart_6="#3977D4",
    chart_grid="#DCE4ED",
    chart_axis="#6D7B8E",
    overlay="#10182066",
    shadow="#1E263926",
    scrollbar="#C1CCD9",
    scrollbar_hover="#99A9BA",
)


PALETTES: Final[Mapping[ThemeName, ThemePalette]] = MappingProxyType(
    {
        ThemeName.DARK: DARK_PALETTE,
        ThemeName.LIGHT: LIGHT_PALETTE,
    }
)


def get_palette(theme: ThemeName | str) -> ThemePalette:
    """Возвращает палитру по имени темы.

    Args:
        theme: ``ThemeName`` или строка ``"dark"``/``"light"``.

    Raises:
        ValueError: если передано неизвестное имя темы.
    """
    try:
        normalized = theme if isinstance(theme, ThemeName) else ThemeName(theme.lower())
    except (ValueError, AttributeError) as exc:
        allowed = ", ".join(item.value for item in ThemeName)
        raise ValueError(f"Неизвестная тема {theme!r}. Доступны: {allowed}.") from exc
    return PALETTES[normalized]


def with_alpha(color: str, alpha: int) -> str:
    """Возвращает цвет ``#RRGGBBAA`` с заданной прозрачностью 0–255."""
    if not _HEX_COLOR_PATTERN.fullmatch(color):
        raise ValueError(f"Некорректный цвет: {color!r}.")
    if not 0 <= alpha <= 255:
        raise ValueError("alpha должен быть в диапазоне 0–255.")
    return f"{color[:7]}{alpha:02X}"


def contrast_text(background: str) -> str:
    """Подбирает чёрный или белый текст по относительной яркости фона."""
    if not _HEX_COLOR_PATTERN.fullmatch(background):
        raise ValueError(f"Некорректный цвет: {background!r}.")

    red = int(background[1:3], 16)
    green = int(background[3:5], 16)
    blue = int(background[5:7], 16)

    # Простая оценка воспринимаемой яркости для UI.
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#111827" if luminance >= 160 else "#FFFFFF"


__all__ = [
    "DARK_PALETTE",
    "LIGHT_PALETTE",
    "PALETTES",
    "SemanticColor",
    "ThemeName",
    "ThemePalette",
    "contrast_text",
    "get_palette",
    "with_alpha",
]
