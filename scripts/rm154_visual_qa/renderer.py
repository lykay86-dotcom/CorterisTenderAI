"""Qt offscreen capture for typed RM-154 visual cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QThread, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from .contracts import RendererFingerprint, VisualCase
from .core import normalize_png_bytes, privacy_findings
from .environment import collect_renderer_fingerprint, register_and_fingerprint_fonts
from .fixtures import build_visual


@dataclass(frozen=True, slots=True)
class Capture:
    case: VisualCase
    png: bytes
    renderer: RendererFingerprint
    qtimers: int
    active_qtimers: int
    qthreads: int


def _resource_counts(widget: object) -> tuple[int, int, int]:
    timers = widget.findChildren(QTimer)  # type: ignore[attr-defined]
    threads = widget.findChildren(QThread)  # type: ignore[attr-defined]
    return len(timers), sum(timer.isActive() for timer in timers), len(threads)


def capture_case(case: VisualCase, *, root: Path, runtime_root: Path) -> Capture:
    app = QApplication.instance() or QApplication([])
    register_and_fingerprint_fonts()
    renderer = collect_renderer_fingerprint(root)
    built = build_visual(case, runtime_root)
    try:
        findings = privacy_findings(built.privacy_values)
        if findings:
            raise RuntimeError("visual fixture privacy violation: " + ", ".join(findings))
        built.widget.resize(case.viewport.width, case.viewport.height)
        built.widget.clearFocus()
        built.widget.show()
        for _ in range(3):
            app.processEvents()
        if not built.widget.isVisible():
            raise RuntimeError(f"visual fixture did not become visible: {case.case_id}")

        image = QImage(built.widget.size(), QImage.Format.Format_RGB32)
        image.fill(0)
        built.widget.render(image, QPoint())
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("could not open in-memory PNG buffer")
        if not image.save(buffer, "PNG"):
            raise RuntimeError("Qt failed to encode visual PNG")
        png = normalize_png_bytes(bytes(buffer.data()))
        qtimers, active_qtimers, qthreads = _resource_counts(built.widget)
        return Capture(case, png, renderer, qtimers, active_qtimers, qthreads)
    finally:
        built.dispose(app)
