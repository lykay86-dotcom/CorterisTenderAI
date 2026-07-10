AIBOS Security 1.2.1 Step 1 Patch

1. Close the application.
2. Back up your project folder.
3. Extract this archive into the project root with file replacement.
4. Run tests:
   .\.venv\Scripts\python.exe -m pytest -q
5. Build:
   .\scripts\build_exe.ps1

On first launch, the old database is backed up and migrated automatically.
Do not delete the existing database.
