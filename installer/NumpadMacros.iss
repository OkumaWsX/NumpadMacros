; Instalador de Numpad Macros para Windows (Inno Setup 6)
; Compilar:  ISCC.exe /DAppVersion=3.2.0 installer\NumpadMacros.iss
; Antes hay que tener:
;   dist\NumpadMacros\              (salida de PyInstaller)
;   third_party\install-interception.exe y third_party\LGPL-3.0.txt

#ifndef AppVersion
  #define AppVersion "3.2.1"
#endif
#define AppName "Numpad Macros"
#define AppExe "NumpadMacros.exe"
#define VBCableUrl "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"

[Setup]
AppId={{8F3C6A52-5E0B-4C6E-9B7B-1D2A9F0E7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=OkumaWsX
AppPublisherURL=https://www.instagram.com/okumawsx
AppSupportURL=https://discord.gg/hcutJcBx9
AppUpdatesURL=https://github.com/OkumaWsX/NumpadMacros/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
OutputDir=..\dist-installer
OutputBaseFilename=NumpadMacros-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
WizardImageFile=..\assets\wizard.bmp
WizardSmallImageFile=..\assets\wizard_small.bmp
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; Instalar drivers (Interception, VB-Cable) requiere administrador
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
es.GroupShortcuts=Accesos directos:
es.GroupRecommended=Componentes recomendados:
es.GroupOptions=Opciones:
es.TaskDesktop=Crear un acceso directo en el escritorio
es.TaskInterception=Driver Interception: usar SOLO tu numpad, sin tocar los demás teclados (requiere reiniciar)
es.TaskVBCable=VB-Cable: micrófono virtual para que te escuchen en Discord, OBS o juegos (se descarga de vb-audio.com)
es.TaskAutostart=Iniciar Numpad Macros con Windows
es.RunInterception=Instalando el driver Interception...
es.RunVBCable=Instalando VB-Cable: en su ventana pulsa «Install Driver»...
es.LaunchApp=Abrir Numpad Macros
es.VBFailed=No se pudo descargar VB-Cable:%n%n%1%n%nNumpad Macros se instalará igual. Puedes instalar VB-Cable después desde https://vb-audio.com/Cable/
es.DownloadTitle=Descargando VB-Cable
es.DownloadDesc=Se descarga desde la página oficial de VB-Audio.

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:GroupShortcuts}"
Name: "interception"; Description: "{cm:TaskInterception}"; GroupDescription: "{cm:GroupRecommended}"; Check: not InterceptionInstalled
Name: "vbcable"; Description: "{cm:TaskVBCable}"; GroupDescription: "{cm:GroupRecommended}"
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:GroupOptions}"; Flags: unchecked

[Files]
Source: "..\dist\NumpadMacros\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\third_party\install-interception.exe"; DestDir: "{app}\drivers"; Flags: ignoreversion
Source: "..\third_party\LGPL-3.0.txt"; DestDir: "{app}\drivers"; DestName: "Interception-LGPL-3.0.txt"; Flags: ignoreversion
Source: "..\LEEME.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\COPYING"; DestDir: "{app}"; DestName: "COPYING.txt"; Flags: ignoreversion
Source: "vbcable.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall; Tasks: vbcable

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; El mismo valor que usa la opción «Iniciar con Windows» dentro de la app
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NumpadMacros"; ValueData: """{app}\{#AppExe}"" ""--minimizado"""; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "NumpadMacros"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\drivers\install-interception.exe"; Parameters: "/install"; StatusMsg: "{cm:RunInterception}"; Flags: runhidden waituntilterminated; Tasks: interception
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{tmp}\vbcable.ps1"" -Zip ""{tmp}\vbcable.zip"""; StatusMsg: "{cm:RunVBCable}"; Flags: runhidden waituntilterminated; Tasks: vbcable; Check: VBCableDownloaded
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#AppExe}"; Flags: runhidden; RunOnceId: "CerrarApp"
; Solo se quita Interception si lo instaló este instalador
Filename: "{app}\drivers\install-interception.exe"; Parameters: "/uninstall"; Flags: runhidden waituntilterminated; Tasks: interception; RunOnceId: "QuitarInterception"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
var
  DownloadPage: TDownloadWizardPage;
  VBDownloaded: Boolean;

function InterceptionInstalled: Boolean;
begin
  { install-interception.exe copia keyboard.sys y mouse.sys a System32\drivers }
  Result := FileExists(ExpandConstant('{sys}\drivers\keyboard.sys'));
end;

function VBCableDownloaded: Boolean;
begin
  Result := VBDownloaded;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('DownloadTitle'), CustomMessage('DownloadDesc'), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected('vbcable') then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('{#VBCableUrl}', 'vbcable.zip', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        VBDownloaded := True;
      except
        VBDownloaded := False;
        if not WizardSilent then
          MsgBox(FmtMessage(CustomMessage('VBFailed'), [GetExceptionMessage]), mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

function NeedRestart(): Boolean;
begin
  { Los drivers de teclado y de audio funcionan después de reiniciar }
  Result := WizardIsTaskSelected('interception') or VBDownloaded;
end;
