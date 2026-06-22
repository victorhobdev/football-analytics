[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [int]$Port
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot "frontend"

Set-Location -LiteralPath $FrontendDir
& node node_modules/next/dist/bin/next dev --turbopack -H 127.0.0.1 -p $Port
exit $LASTEXITCODE
