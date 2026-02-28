#define MyAppName "WorldRec"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\\dist\\WorldRec"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\\artifacts"
#endif

[Setup]
AppId={{8DDBD0E8-45E2-471B-BE17-5E8A0385154A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=WorldRec
DefaultDirName={localappdata}\Programs\WorldRec
DefaultGroupName=WorldRec
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=WorldRec-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\WorldRec.exe

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WorldRec"; Filename: "{app}\WorldRec.exe"
Name: "{autodesktop}\WorldRec"; Filename: "{app}\WorldRec.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WorldRec.exe"; Description: "WorldRecを起動する"; Flags: nowait postinstall skipifsilent

