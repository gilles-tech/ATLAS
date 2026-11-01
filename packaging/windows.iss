#define AppName "Atlas Marches"
#define AppVersion "0.9.0"
[Setup]
AppId={{D8D89567-8B6F-4B35-823C-D88EA933424A}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\AtlasMarches
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=AtlasMarches-Setup-Windows
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\AtlasMarches.exe
[Files]
Source: "dist\AtlasMarches\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{autoprograms}\Atlas Marches"; Filename: "{app}\AtlasMarches.exe"
Name: "{autodesktop}\Atlas Marches"; Filename: "{app}\AtlasMarches.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Creer un raccourci bureau"; Flags: unchecked
[Run]
Filename: "{app}\AtlasMarches.exe"; Description: "Lancer Atlas Marches"; Flags: nowait postinstall skipifsilent
