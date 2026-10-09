# Descomprime VB-Cable (descargado de vb-audio.com por el instalador) y abre su instalador.
param([Parameter(Mandatory = $true)][string]$Zip)
$ErrorActionPreference = "Stop"
$dest = Join-Path (Split-Path $Zip) "vbcable"
Expand-Archive -Force -LiteralPath $Zip -DestinationPath $dest
$setup = Get-ChildItem -Path $dest -Recurse -Filter "VBCABLE_Setup_x64.exe" | Select-Object -First 1
if (-not $setup) {
    $setup = Get-ChildItem -Path $dest -Recurse -Filter "*Setup*x64*.exe" | Select-Object -First 1
}
if (-not $setup) { exit 2 }
# La ventana de VB-Cable se abre normal: el usuario pulsa «Install Driver»
Start-Process -FilePath $setup.FullName -WorkingDirectory $setup.DirectoryName -Wait
exit 0
