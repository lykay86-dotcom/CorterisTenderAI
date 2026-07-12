from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.tenders.safe_archive import (
    ArchiveMemberStatus,
    SafeArchiveExtractor,
)


def _zip(path: Path, entries: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_extracts_safe_files_and_blocks_traversal(tmp_path) -> None:
    source = tmp_path / "docs.zip"
    _zip(source, {
        "ТЗ/техническое задание.txt": "СКУД".encode("utf-8"),
        "../../outside.txt": b"attack",
        "run.cmd": b"echo attack",
    })

    result = SafeArchiveExtractor().extract_many((source,), tmp_path / "out")

    assert result.extracted_count == 1
    assert result.blocked_count == 2
    assert result.extracted_files[0].read_text(encoding="utf-8") == "СКУД"
    assert not (tmp_path / "outside.txt").exists()


def test_blocks_suspicious_compression_ratio(tmp_path) -> None:
    source = tmp_path / "bomb.zip"
    _zip(source, {"large.txt": b"A" * 200_000})

    result = SafeArchiveExtractor(
        max_compression_ratio=5,
    ).extract_many((source,), tmp_path / "out")

    assert result.extracted_count == 0
    assert result.blocked_count == 1
    assert "коэффициент" in result.members[0].message


def test_extracts_nested_zip_with_depth_limit(tmp_path) -> None:
    nested_bytes = BytesIO()
    with ZipFile(nested_bytes, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("requirements.txt", "лицензия МЧС")
    source = tmp_path / "outer.zip"
    _zip(source, {"nested.zip": nested_bytes.getvalue()})

    result = SafeArchiveExtractor(max_depth=1).extract_many(
        (source,), tmp_path / "out"
    )

    assert any(path.name == "requirements.txt" for path in result.extracted_files)


def test_repeated_extraction_reuses_same_paths(tmp_path) -> None:
    source = tmp_path / "docs.zip"
    _zip(source, {"ТЗ.txt": "видеонаблюдение".encode("utf-8")})
    extractor = SafeArchiveExtractor()

    first = extractor.extract_many((source,), tmp_path / "out")
    second = extractor.extract_many((source,), tmp_path / "out")

    assert first.extracted_files == second.extracted_files
    assert len(list((tmp_path / "out").rglob("ТЗ*.txt"))) == 1
