#define AppName "Atlas Marchés"
#define AppVersion "0.9.0"
[Setup]
AppId={{8D2BCE6A-1BE6-4E32-BA0B-5137CBBE8F3A}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\AtlasMarches
DefaultGroupName=Atlas Marchés
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=AtlasMarches-Setup-win64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\AtlasMarches.exe
[Files]
Source: "..\dist\AtlasMarches\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Atlas Marchés"; Filename: "{app}\AtlasMarches.exe"
Name: "{autodesktop}\Atlas Marchés"; Filename: "{app}\AtlasMarches.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked
[Run]
Filename: "{app}\AtlasMarches.exe"; Description: "Lancer Atlas Marchés"; Flags: nowait postinstall skipifsilent
