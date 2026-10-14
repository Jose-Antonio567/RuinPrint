#define MyAppName "RuinPrint"
#define MyAppVersion "1.0.0"
#define MyAppExeName "RuinPrint.exe"

[Setup]
AppId={{CB4E12B0-14D6-4C77-9ED4-13C48B6BA33C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=RuinPrint
SetupIconFile=..\assets\ruinprint.ico
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\release
OutputBaseFilename=RuinPrint_Setup_{#MyAppVersion}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "..\dist\RuinPrint\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "data\*"
Source: "..\dist\RuinPrint\data\settings.ini"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
Source: "..\dist\RuinPrint\data\user_presets.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
