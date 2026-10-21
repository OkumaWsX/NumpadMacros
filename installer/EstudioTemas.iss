; Instalador del Estudio de Temas para Windows (Inno Setup 6)
; Compilar:  ISCC.exe /DAppVersion=1.0.0 installer\EstudioTemas.iss
; Antes hay que tener:  tools\estudio\dist\EstudioTemas-NumpadMacros.exe  (salida de PyInstaller)
;
; Se instala solo para el usuario actual: no pide permisos de administrador.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Estudio de Temas"
#define AppExe "EstudioTemas-NumpadMacros.exe"

[Setup]
AppId={{3B7E2C9A-41D6-4F8B-9E25-6A0C17D4B8F3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=OkumaWsX
AppPublisherURL=https://www.instagram.com/okumawsx
AppSupportURL=https://discord.gg/hcutJcBx9
AppUpdatesURL=https://github.com/OkumaWsX/NumpadMacros/releases
DefaultDirName={autopf}\Estudio de Temas
DefaultGroupName=Numpad Macros
DisableProgramGroupPage=yes
DisableWelcomePage=no
OutputDir=..\dist-installer
OutputBaseFilename=EstudioTemas-Setup-{#AppVersion}
SetupIconFile=..\assets\icon-estudio.ico
WizardImageFile=..\assets\wizard.bmp
WizardSmallImageFile=..\assets\wizard_small.bmp
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} · Numpad Macros
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
ChangesAssociations=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
es.GroupShortcuts=Accesos directos:
es.TaskDesktop=Crear un acceso directo en el escritorio
es.TaskAssoc=Abrir los proyectos .nptproj con el Estudio de Temas
es.LaunchApp=Abrir el Estudio de Temas

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:GroupShortcuts}"
Name: "assoc"; Description: "{cm:TaskAssoc}"; GroupDescription: "{cm:GroupShortcuts}"

[Files]
Source: "..\tools\estudio\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tools\estudio\LEEME.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\COPYING"; DestDir: "{app}"; DestName: "COPYING.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Proyectos .nptproj (solo para este usuario)
Root: HKCU; Subkey: "Software\Classes\.nptproj"; ValueType: string; ValueData: "EstudioTemas.Proyecto"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKCU; Subkey: "Software\Classes\EstudioTemas.Proyecto"; ValueType: string; ValueData: "Proyecto del Estudio de Temas"; Flags: uninsdeletekey; Tasks: assoc
Root: HKCU; Subkey: "Software\Classes\EstudioTemas.Proyecto\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"; Tasks: assoc
Root: HKCU; Subkey: "Software\Classes\EstudioTemas.Proyecto\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#AppExe}"; Flags: runhidden; RunOnceId: "CerrarEstudio"
