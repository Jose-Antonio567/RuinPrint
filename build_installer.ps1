$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSCommandPath
$portableExe = Join-Path $projectRoot "dist\RuinPrint\RuinPrint.exe"
$installerScript = Join-Path $projectRoot "installer\RuinPrint.iss"
$releaseDirectory = Join-Path $projectRoot "release"
$installerOutput = Join-Path $releaseDirectory "RuinPrint_Setup_1.0.0.exe"

if (-not (Test-Path -LiteralPath $portableExe)) {
    throw "A build Windows não existe. Execute build_windows.ps1 primeiro."
}

$isccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$searchRoots = @(
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)},
    (Join-Path $env:LOCALAPPDATA "Programs")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$isccCandidatePaths = @(
    $isccCommand.Source,
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)

foreach ($root in $searchRoots) {
    $isccCandidatePaths += Get-ChildItem -LiteralPath $root -Directory -Filter "Inno Setup *" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "ISCC.exe" }
}

$isccCandidates = $isccCandidatePaths |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    ForEach-Object {
        $absolutePath = (Resolve-Path -LiteralPath $_).Path
        $match = [regex]::Match($absolutePath, "Inno Setup\s+(\d+(?:\.\d+)*)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        $versionText = if ($match.Success) { $match.Groups[1].Value } else { "0.0" }
        if ($versionText -notmatch "\.") { $versionText += ".0" }
        [PSCustomObject]@{
            Path = $absolutePath
            Version = [version]$versionText
        }
    } |
    Sort-Object -Property @{Expression = "Version"; Descending = $true}, @{Expression = "Path"; Descending = $false} |
    Select-Object -Unique Path, Version

if (-not $isccCandidates) {
    throw "Inno Setup 7 ou compatível não foi encontrado. Instale-o e execute este script novamente."
}

$iscc = $isccCandidates[0].Path
New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null
if (Test-Path -LiteralPath $installerOutput) { Remove-Item -LiteralPath $installerOutput -Force }

& $iscc $installerScript
if ($LASTEXITCODE -ne 0) { throw "ISCC terminou com código $LASTEXITCODE." }
if (-not (Test-Path -LiteralPath $installerOutput)) { throw "O instalador não foi criado: $installerOutput" }

Write-Host "Instalador criado em: $installerOutput"
