[CmdletBinding()]
param(
  [int]$BffPort = 8010,
  [int]$FrontendPort = 3001
)

$ErrorActionPreference = "Stop"

$ScriptPath = Join-Path $PSScriptRoot "tools\start-local.ps1"

if (-not (Test-Path -LiteralPath $ScriptPath)) {
  throw "Script nao encontrado: $ScriptPath"
}

& $ScriptPath -BffPort $BffPort -FrontendPort $FrontendPort
