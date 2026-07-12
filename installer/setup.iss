; Corteris Tender AI - Inno Setup, one-file PyInstaller build

#define AppName "Corteris Tender AI"
#define AppVersion "1.5.1"
#define AppPublisher "ООО КОРТЕРИС"
#define AppExeName "CorterisTenderAI.exe"
#define AppId "{{E82B9934-04E5-4F2F-9A73-7FB3AD0C891C}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Corteris Tender AI
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=CorterisTenderAI_Setup_x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
SetupLogging=yes
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no

[Files]
; The PyInstaller spec produces one executable. Keeping only this source avoids
; Inno Setup error "No files found" for a non-existent OneDir wildcard.
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent
