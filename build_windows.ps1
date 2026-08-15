$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSCommandPath
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$buildDirectory = Join-Path $projectRoot "build"
$distDirectory = Join-Path $projectRoot "dist"
$portableDirectory = Join-Path $distDirectory "RuinPrint"
$sourceDataDirectory = Join-Path $projectRoot "data"
$targetDataDirectory = Join-Path $portableDirectory "data"
$specFile = Join-Path $projectRoot "packaging\RuinPrint.spec"

if (-not (Test-Path -LiteralPath $python)) { throw "Python da virtualenv não foi encontrado: $python" }

# Only PyInstaller artifacts inside this project are removed; source data is never targeted.
foreach ($target in @($buildDirectory, $portableDirectory)) {
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

Push-Location $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean $specFile
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminou com código $LASTEXITCODE." }
}
finally { Pop-Location }

if (-not (Test-Path -LiteralPath $portableDirectory)) { throw "A pasta da build não foi criada: $portableDirectory" }
New-Item -ItemType Directory -Path $targetDataDirectory -Force | Out-Null
foreach ($fileName in @("settings.ini", "user_presets.json")) {
    $sourceFile = Join-Path $sourceDataDirectory $fileName
    if (Test-Path -LiteralPath $sourceFile) {
        Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $targetDataDirectory $fileName) -Force
    }
}
Write-Host "Build portátil criada em: $portableDirectory"
