$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSCommandPath
$releaseDirectory = Join-Path $projectRoot "release"
$portableSource = Join-Path $projectRoot "dist\RuinPrint"
$portableExecutable = Join-Path $portableSource "RuinPrint.exe"
$installerSource = Join-Path $releaseDirectory "RuinPrint_Setup_1.0.0.exe"
$packageDirectory = Join-Path $releaseDirectory "RuinPrint_1.0.0"
$packageInstaller = Join-Path $packageDirectory "RuinPrint_Setup_1.0.0.exe"
$packagePortable = Join-Path $packageDirectory "Portable"
$readmePath = Join-Path $packageDirectory "LEIA-ME.txt"

if (-not (Test-Path -LiteralPath $portableExecutable)) {
    throw "A build Portable não existe. Execute build_windows.ps1 primeiro."
}
if (-not (Test-Path -LiteralPath $installerSource)) {
    throw "O instalador não existe. Execute build_installer.ps1 primeiro."
}

# Only the assembled distribution folder is recreated. The source build and installer remain intact.
if (Test-Path -LiteralPath $packageDirectory) {
    Remove-Item -LiteralPath $packageDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $packageDirectory -Force | Out-Null

Copy-Item -LiteralPath $installerSource -Destination $packageInstaller -Force
Copy-Item -LiteralPath $portableSource -Destination $packagePortable -Recurse -Force

@'
RuinPrint 1.0.0

INSTALAÇÃO RECOMENDADA
1. Execute RuinPrint_Setup_1.0.0.exe.
2. Conclua a instalação.
3. Abra RuinPrint pelo Menu Iniciar ou atalho criado.

VERSÃO PORTÁTIL
Se não puder instalar:
1. Abra a pasta Portable.
2. Execute RuinPrint.exe.
3. Não remova arquivos de _internal.

IMPORTANTE
A pasta data contém presets e configurações da versão portátil.
'@ | Set-Content -LiteralPath $readmePath -Encoding utf8

Write-Host "Pacote final preparado em: $packageDirectory"
