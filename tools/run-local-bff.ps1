[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [int]$Port
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "api"

Set-Location -LiteralPath $ApiDir
& python -m uvicorn src.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
