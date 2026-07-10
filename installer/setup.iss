; Corteris Tender AI - Inno Setup (supports OneFile and OneDir)

#define AppName "Corteris Tender AI"
#define AppVersion "1.5.1"
#define AppPublisher "CORTERIS"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Corteris Tender AI
DefaultGroupName={#AppName}
OutputDir=output
OutputBaseFilename=CorterisTenderAI_Setup_x64
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
; OneFile build
Source: "..\dist\CorterisTenderAI.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; OneDir build
Source: "..\dist\CorterisTenderAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\Corteris Tender AI"; Filename: "{app}\CorterisTenderAI.exe"
Name: "{autodesktop}\Corteris Tender AI"; Filename: "{app}\CorterisTenderAI.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; Flags: unchecked
