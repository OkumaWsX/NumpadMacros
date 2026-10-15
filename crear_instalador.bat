@echo off
rem Crea el instalador NumpadMacros-Setup.exe en tu PC.
rem Necesita: Python 3.12 e Inno Setup 6 (https://jrsoftware.org/isdl.php) instalados.
cd /d "%~dp0"
if not exist third_party\install-interception.exe (
  echo Falta third_party\install-interception.exe
  echo Descarga Interception.zip de https://github.com/oblitum/Interception/releases/latest y copia:
  echo   "command line installer\install-interception.exe"  a  third_party\
  echo   "licenses\non-commercial-usage\LGPL 3.0.txt"         a  third_party\LGPL-3.0.txt
  echo   "library\x64\interception.dll"                        a  esta carpeta
  pause & exit /b 1
)
py -m pip install --disable-pip-version-check -q -r requirements.txt pyinstaller==6.22.3 pillow || goto :err
py -m PyInstaller --noconfirm NumpadMacros.spec || goto :err
for /f %%v in ('py -c "import npm; print(npm.__version__)"') do set VER=%%v
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /Q /DAppVersion=%VER% installer\NumpadMacros.iss || goto :err
echo.
echo Listo: dist-installer\NumpadMacros-Setup-%VER%.exe
pause
exit /b 0
:err
echo Hubo un error.
pause
exit /b 1
