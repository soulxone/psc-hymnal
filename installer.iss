; Inno Setup script for PSC Hymnal
; Builds a no-admin, per-user installer: dist\PSC-Hymnal-Setup.exe
; Compile with:  ISCC.exe installer.iss   (run from the hymnal_app folder)

#define MyAppName "PSC Hymnal"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "Pleasant Springs Church"
#define MyAppURL "https://ps-church.com"
#define MyAppExeName "PSC Hymnal.exe"

[Setup]
; A stable AppId so future versions upgrade in place rather than installing twice.
AppId={{7C9A1E3B-5D24-4F8A-9B17-2E6C0A4D9F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Per-user install — no administrator rights / UAC prompt required.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\PSC Hymnal
DisableProgramGroupPage=yes
DisableDirPage=auto

; Output
OutputDir=dist
OutputBaseFilename=PSC-Hymnal-Setup
SetupIconFile=hymnal.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Packaging
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The entire one-folder PyInstaller build (exe + _internal: DLLs, hymns.json, audio/).
Source: "dist\PSC Hymnal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Note: the uninstaller removes everything under {app}. User data lives in
; %APPDATA%\PSC Hymnal (settings, playlists, ESV cache, drop-in audio) and is
; intentionally left untouched, so it survives uninstall/reinstall.
