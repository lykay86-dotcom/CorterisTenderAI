# Сборка Windows EXE
Требуется Windows 10/11 x64, Python 3.12 x64 и Inno Setup 6.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_exe.ps1
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" .\installer\setup.iss
```

Готовый установщик: `installer\output\CorterisTenderAI_Setup_x64.exe`. Python конечному пользователю не нужен. Сборку Windows EXE следует выполнять на Windows, поскольку bootloader PyInstaller платформозависим.
