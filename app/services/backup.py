from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import zipfile

class BackupService:
    def create(self, destination: Path, sources: list[Path], metadata: dict | None = None) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        output = destination / f"corteris_backup_{datetime.now():%Y%m%d_%H%M%S}.zip"
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in sources:
                if not source.exists():
                    continue
                if source.is_file():
                    archive.write(source, f"data/{source.name}")
                else:
                    for file in source.rglob("*"):
                        if file.is_file():
                            archive.write(file, f"data/{source.name}/{file.relative_to(source)}")
            archive.writestr("backup_manifest.json", json.dumps(metadata or {}, ensure_ascii=False, indent=2))
        return output

    def verify(self, archive_path: Path) -> bool:
        with zipfile.ZipFile(archive_path) as archive:
            return archive.testzip() is None and "backup_manifest.json" in archive.namelist()
