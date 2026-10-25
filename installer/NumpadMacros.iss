; Instalador de Numpad Macros para Windows (Inno Setup 6)
; Compilar:  ISCC.exe /DAppVersion=3.3.0 /DEstudioVersion=1.0.0 installer\NumpadMacros.iss
; Actualización automática (la lanza la propia app):
;   NumpadMacros-Windows-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /ACTUALIZAR=1
;   -> solo reemplaza el programa (no toca los drivers) y vuelve a abrir la app
; Antes hay que tener:
;   dist\NumpadMacros\              (salida de PyInstaller)
;   third_party\install-interception.exe y third_party\LGPL-3.0.txt

#ifndef AppVersion
  #define AppVersion "3.3.0"
#endif
#define AppName "Numpad Macros"
#define AppExe "NumpadMacros.exe"
#define VBCableUrl "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"
; El Estudio de Temas es un programa aparte, con sus propias Releases (etiqueta estudio-vX.Y.Z,
; cada una con su SHA256SUMS.txt). Al compilar se indica la última publicada (compilar.yml la
; consulta en GitHub); si no se indica, la de tools/estudio/estudio.py al momento de escribir esto.
#ifndef EstudioVersion
  #define EstudioVersion "1.0.0"
#endif
#define ReleaseUrl "https://github.com/OkumaWsX/NumpadMacros/releases/download/estudio-v" + EstudioVersion
#define EstudioAsset "EstudioTemas-Windows-Setup.exe"

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
es.TaskEstudio=Estudio de Temas: el editor para crear tus propios temas (se descarga de GitHub). Numpad Macros también buscará sus actualizaciones
es.TaskEstudioUpd=Estudio de Temas (ya instalado): buscar también sus actualizaciones desde Numpad Macros
es.RunEstudio=Instalando el Estudio de Temas...
es.EstudioFailed=No se pudo descargar el Estudio de Temas:%n%n%1%n%nNumpad Macros se instalará igual. Puedes instalar el Estudio después desde la pestaña «Temas».
es.DownloadEstudioTitle=Descargando el Estudio de Temas
es.DownloadEstudioDesc=Se descarga desde la página de versiones del Estudio de Temas en GitHub.
es.RunInterception=Instalando el driver Interception...
es.RunVBCable=Instalando VB-Cable: en su ventana pulsa «Install Driver»...
es.LaunchApp=Abrir Numpad Macros
es.VBFailed=No se pudo descargar VB-Cable:%n%n%1%n%nNumpad Macros se instalará igual. Puedes instalar VB-Cable después desde https://vb-audio.com/Cable/
es.DownloadTitle=Descargando VB-Cable
es.DownloadDesc=Se descarga desde la página oficial de VB-Audio.

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:GroupShortcuts}"
Name: "interception"; Description: "{cm:TaskInterception}"; GroupDescription: "{cm:GroupRecommended}"; Check: (not InterceptionInstalled) and (not IsUpdate)
Name: "vbcable"; Description: "{cm:TaskVBCable}"; GroupDescription: "{cm:GroupRecommended}"; Check: (not VBCableInstalled) and (not IsUpdate)
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:GroupOptions}"; Flags: unchecked
Name: "estudio"; Description: "{cm:TaskEstudio}"; GroupDescription: "{cm:GroupOptions}"; Flags: unchecked; Check: (not EstudioInstalled) and (not IsUpdate)
Name: "estudioupd"; Description: "{cm:TaskEstudioUpd}"; GroupDescription: "{cm:GroupOptions}"; Check: EstudioInstalled and (not IsUpdate)

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
; El Estudio se instala para el usuario (no como administrador): por eso runasoriginaluser
Filename: "{tmp}\{#EstudioAsset}"; Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"; StatusMsg: "{cm:RunEstudio}"; Flags: runasoriginaluser waituntilterminated; Tasks: estudio; Check: EstudioDownloaded
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent runasoriginaluser
; Al actualizar en silencio, la app se vuelve a abrir sola
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; Check: IsUpdate

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
  EstudioOk: Boolean;

function InterceptionInstalled: Boolean;
begin
  { install-interception.exe copia keyboard.sys y mouse.sys a System32\drivers }
  Result := FileExists(ExpandConstant('{sys}\drivers\keyboard.sys'));
end;

function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:ACTUALIZAR|0}') = '1';
end;

function VBCableInstalled: Boolean;
var
  FindRec: TFindRec;
begin
  { El driver de VB-Cable se copia como vbaudio_cable64_*.sys }
  Result := FindFirst(ExpandConstant('{sys}\drivers\vbaudio_cable*.sys'), FindRec);
  if Result then
    FindClose(FindRec);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if IsUpdate then
  begin
    { La app se cierra sola antes de actualizar; por si sigue abierta: }
    Sleep(1500);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  end;
end;

function VBCableDownloaded: Boolean;
begin
  Result := VBDownloaded;
end;

function EstudioInstalled: Boolean;
begin
  { El Estudio se instala por usuario; AppId de installer\EstudioTemas.iss }
  Result := RegKeyExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{3B7E2C9A-41D6-4F8B-9E25-6A0C17D4B8F3}_is1') or
            RegKeyExists(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{3B7E2C9A-41D6-4F8B-9E25-6A0C17D4B8F3}_is1');
end;

function EstudioDownloaded: Boolean;
begin
  Result := EstudioOk;
end;

{ Huella SHA256 de un archivo según el SHA256SUMS.txt de la Release ("" si no está) }
function HashFromSums(const Path, Name: String): String;
var
  Lines: TArrayOfString;
  I, L: Integer;
  Line: String;
begin
  Result := '';
  if not LoadStringsFromFile(Path, Lines) then
    exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    L := Length(Line);
    if (L > 66) and (Copy(Line, L - Length(Name) + 1, Length(Name)) = Name) then
    begin
      Result := LowerCase(Copy(Line, 1, 64));
      exit;
    end;
  end;
end;

procedure DownloadEstudio;
var
  Hash: String;
begin
  EstudioOk := False;
  DownloadPage.SetText(CustomMessage('DownloadEstudioTitle'), CustomMessage('DownloadEstudioDesc'));
  try
    DownloadTemporaryFile('{#ReleaseUrl}/SHA256SUMS.txt', 'SHA256SUMS.txt', '', nil);
    Hash := HashFromSums(ExpandConstant('{tmp}\SHA256SUMS.txt'), '{#EstudioAsset}');
    if Hash = '' then
      RaiseException('La versión publicada no trae la huella de seguridad del Estudio.');
    DownloadPage.Clear;
    { Con la huella, Inno verifica el archivo y lo borra si no coincide }
    DownloadPage.Add('{#ReleaseUrl}/{#EstudioAsset}', '{#EstudioAsset}', Hash);
    DownloadPage.Download;
    EstudioOk := True;
  except
    if not WizardSilent then
      MsgBox(FmtMessage(CustomMessage('EstudioFailed'), [GetExceptionMessage]), mbInformation, MB_OK);
  end;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('DownloadTitle'), CustomMessage('DownloadDesc'), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and (not IsUpdate) and
     (WizardIsTaskSelected('vbcable') or WizardIsTaskSelected('estudio')) then
  begin
    DownloadPage.Show;
    try
      if WizardIsTaskSelected('vbcable') then
      begin
        DownloadPage.SetText(CustomMessage('DownloadTitle'), CustomMessage('DownloadDesc'));
        DownloadPage.Clear;
        DownloadPage.Add('{#VBCableUrl}', 'vbcable.zip', '');
        try
          DownloadPage.Download;
          VBDownloaded := True;
        except
          VBDownloaded := False;
          if not WizardSilent then
            MsgBox(FmtMessage(CustomMessage('VBFailed'), [GetExceptionMessage]), mbInformation, MB_OK);
        end;
      end;
      { Si falla, no es grave: Numpad Macros se instala igual }
      if WizardIsTaskSelected('estudio') then
        DownloadEstudio;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { La app lee esta elección una vez al abrirse: activa (o no) la opción del Estudio de Temas,
    que además hace que busque sus actualizaciones }
  if (CurStep = ssPostInstall) and (not IsUpdate) then
    RegWriteDWordValue(HKCU, 'Software\NumpadMacros', 'EstudioTemas',
                       Ord(WizardIsTaskSelected('estudio') or WizardIsTaskSelected('estudioupd')));
end;

function NeedRestart(): Boolean;
begin
  { Los drivers de teclado y de audio funcionan después de reiniciar }
  Result := (not IsUpdate) and (WizardIsTaskSelected('interception') or VBDownloaded);
end;
