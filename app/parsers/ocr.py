from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


class OCRUnavailable(RuntimeError):
    pass


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def recognize_image(path: Path, language: str = "rus+eng") -> str:
    if not tesseract_available():
        raise OCRUnavailable(
            "Tesseract не установлен. Установите Tesseract OCR и русские языковые данные."
        )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ocr"
        process = subprocess.run(
            ["tesseract", str(path), str(out), "-l", language, "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or "Ошибка Tesseract")
        return out.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")
