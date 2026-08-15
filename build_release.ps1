$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSCommandPath
& (Join-Path $projectRoot "build_windows.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $projectRoot "build_installer.ps1")
exit $LASTEXITCODE
