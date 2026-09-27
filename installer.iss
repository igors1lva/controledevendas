; Script de Instalação Inno Setup para Central de Vendas - Gestão e Controle Interno
; Compilador: Inno Setup 6

#define MyAppName "Central de Vendas"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "Central de Vendas"
#define MyAppExeName "CentralDeVendas.exe"
#define MyAppAssocName "Central de Vendas - Gestão e Controle Interno"

[Setup]
AppId={{E72F18A3-569A-4B6A-91D0-37BC47A1192C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Central de Vendas - Gestão e Controle Interno (Software Não-Fiscal)
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=dist_installer
OutputBaseFilename=Setup_CentralDeVendas
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\vendas.ico
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
InfoBeforeFile=termo_nao_fiscal.txt

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
; Garante permissões de escrita para usuários no diretório do app (para SQLite e Relatórios Excel)
Name: "{app}"; Permissions: users-modify authusers-modify

[Files]
Source: "dist\CentralDeVendas.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "termo_nao_fiscal.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\vendas.ico"
Name: "{autoprograms}\{#MyAppName}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\assets\vendas.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
