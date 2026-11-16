; Inno Setup 6 script:  ISCC /DAppVersion=1.0.0 installer\wxwx-toolkit.iss
; The same installer is used for first install and for self-updates (silently over the old install).
; Add-ons and shared tools (ffmpeg, yt-dlp) live in %LOCALAPPDATA%\wxwx-toolkit and survive updates.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define SrcDir "..\dist\wxwx-toolkit"
#define ExeName "wxwx-toolkit.exe"

[Setup]
AppId={{3F6C2B8E-91A4-4E57-B2D0-7C5A9E1D4F23}
AppName=wxwx toolkit
AppVersion={#AppVersion}
AppVerName=wxwx toolkit {#AppVersion}
AppPublisher=yuyu
AppPublisherURL=https://github.com/ddam1k/wxwx-toolkit
AppSupportURL=https://github.com/ddam1k/wxwx-toolkit/issues
AppUpdatesURL=https://github.com/ddam1k/wxwx-toolkit/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\wxwx toolkit
DefaultGroupName=wxwx toolkit
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
DisableDirPage=auto
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=wxwx-toolkit-setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName=wxwx toolkit
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
ChangesAssociations=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SrcDir}\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; .wtp = wxwx toolkit preset: double-click opens the toolkit and hands the preset to its add-on
Root: HKA; Subkey: "Software\Classes\.wtp"; ValueType: string; ValueName: ""; ValueData: "wxwx.preset"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\wxwx.preset"; ValueType: string; ValueName: ""; ValueData: "wxwx toolkit preset"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\wxwx.preset\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#ExeName},0"
Root: HKA; Subkey: "Software\Classes\wxwx.preset\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeName}"" ""%1"""

[Icons]
Name: "{autoprograms}\wxwx toolkit"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\wxwx toolkit"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,wxwx toolkit}"; Flags: nowait postinstall skipifsilent runasoriginaluser
Filename: "{app}\{#ExeName}"; Flags: nowait skipifnotsilent runasoriginaluser

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
