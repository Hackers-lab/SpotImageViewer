; Inno Setup Script for Spot Image Viewer
; Generated for automated packaging & silent self-updating

#define MyAppName "Spot Image Viewer"
#define MyAppVersion "19.4"
#define MyAppPublisher "WBSEDCL / Pramod Kumar Verma"
#define MyAppExeName "SpotImageViewerV19.4.exe"
#define MyAppURL "https://github.com/Hackers-lab/SpotImageViewer"

[Setup]
AppId={{D814B2C3-A449-4180-877B-1BFD53702164}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\SpotImageViewer
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=..\Output
OutputBaseFilename=SpotImageViewer_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\spot_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source directory produced by PyInstaller (spec build)
Source: "..\dist\SpotImageViewerV19.4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
