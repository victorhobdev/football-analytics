[CmdletBinding()]
param(
  [int]$BffPort = 8010,
  [int]$FrontendPort = 3001
)

# Script para subir ambiente local completo (BFF + frontend + stack docker) com foco em desenvolvimento iterativo
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "api"
$FrontendDir = Join-Path $RepoRoot "frontend"
$RootEnvPath = Join-Path $RepoRoot ".env"
$FrontendEnvPath = Join-Path $FrontendDir ".env.local"
$ArtifactsDir = Join-Path $RepoRoot "artifacts\local-run"
$BffOutLog = Join-Path $ArtifactsDir "start-local.bff.out.log"
$BffErrLog = Join-Path $ArtifactsDir "start-local.bff.err.log"
$FrontendOutLog = Join-Path $ArtifactsDir "start-local.frontend.out.log"
$FrontendErrLog = Join-Path $ArtifactsDir "start-local.frontend.err.log"
$BffPidFile = Join-Path $ArtifactsDir "start-local.bff.pid"
$FrontendPidFile = Join-Path $ArtifactsDir "start-local.frontend.pid"
$ServingSnapshotPath = Join-Path $RepoRoot "artifacts\football_serving_20260426.dump"
$WorldCupDeltaPath = Join-Path $RepoRoot "artifacts\wc_delta_20260426.tgz"
$WorldCupLoadSqlPath = Join-Path $RepoRoot "db\bootstrap\load_world_cup_delta.sql"
$CoachRefreshSqlPath = Join-Path $RepoRoot "db\bootstrap\refresh_local_coach_assignments.sql"
$BffRunnerPath = Join-Path $RepoRoot "tools\run-local-bff.ps1"
$FrontendRunnerPath = Join-Path $RepoRoot "tools\run-local-frontend.ps1"
$RepoRootLower = $RepoRoot.ToLowerInvariant()

function Write-Step {
  param([string]$Message)
  Write-Host "[start-local] $Message"
}

function Assert-Command {
  param(
    [string]$Name,
    [string]$Hint
  )

  try {
    Get-Command $Name -ErrorAction Stop | Out-Null
  } catch {
    throw "$Hint"
  }
}

function Load-DotEnv {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Arquivo obrigatorio nao encontrado: $Path"
  }

  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }

    if ($trimmed -notmatch '^\s*([^=\s]+)\s*=\s*(.*)\s*$') {
      continue
    }

    $key = $matches[1]
    $value = $matches[2].Trim()

    if (
      ($value.StartsWith('"') -and $value.EndsWith('"')) -or
      ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
      $value = $value.Substring(1, $value.Length - 2)
    }

    [Environment]::SetEnvironmentVariable($key, $value, "Process")
  }
}

function Set-DotEnvValue {
  param(
    [string]$Path,
    [string]$Key,
    [string]$Value
  )

  $lines = @()
  if (Test-Path -LiteralPath $Path) {
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($existingLine in Get-Content -LiteralPath $Path) {
      $lines.Add($existingLine)
    }
  } else {
    $lines = [System.Collections.Generic.List[string]]::new()
  }

  $pattern = '^\s*' + [regex]::Escape($Key) + '\s*='
  $updated = $false

  for ($index = 0; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -match $pattern) {
      $lines[$index] = "$Key=$Value"
      $updated = $true
      break
    }
  }

  if (-not $updated) {
    $lines.Add("$Key=$Value")
  }

  Set-Content -LiteralPath $Path -Value $lines -Encoding ascii
}

function Get-ListeningProcess {
  param([int]$Port)

  $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1

  if (-not $connection) {
    return $null
  }

  return Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
}

function Test-OwnedProcess {
  param(
    $ProcessInfo,
    [string[]]$OwnedPatterns = @()
  )

  if (-not $ProcessInfo -or -not $ProcessInfo.CommandLine) {
    return $false
  }

  $commandLine = $ProcessInfo.CommandLine.ToLowerInvariant()
  if ($commandLine.Contains($RepoRootLower)) {
    return $true
  }

  foreach ($pattern in $OwnedPatterns) {
    if ($commandLine -like $pattern.ToLowerInvariant()) {
      return $true
    }
  }

  return $false
}

function Stop-OwnedProcess {
  param(
    [string]$Label,
    [int]$Port,
    [string]$PidFile,
    [string[]]$OwnedPatterns = @()
  )

  if (Test-Path -LiteralPath $PidFile) {
    $pidValue = (Get-Content -LiteralPath $PidFile | Select-Object -First 1).Trim()
    if ($pidValue -match '^\d+$') {
      $processFromPid = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
      if (Test-OwnedProcess -ProcessInfo $processFromPid -OwnedPatterns $OwnedPatterns) {
        Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
        Write-Step "Processo antigo de $Label encerrado via PID $pidValue."
      }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
  }

  $processOnPort = Get-ListeningProcess -Port $Port
  if (-not $processOnPort) {
    return
  }

  if (Test-OwnedProcess -ProcessInfo $processOnPort -OwnedPatterns $OwnedPatterns) {
    Stop-Process -Id $processOnPort.ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Step "Processo antigo de $Label encerrado na porta $Port."
    return
  }

  throw "Porta $Port ja esta em uso por processo externo ao repo: PID $($processOnPort.ProcessId) [$($processOnPort.Name)]."
}

function Clear-FrontendCache {
  $nextDir = Join-Path $FrontendDir ".next"
  if (-not (Test-Path -LiteralPath $nextDir)) {
    return
  }

  for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
      Remove-Item -LiteralPath $nextDir -Recurse -Force
      Write-Step "Cache .next limpo para evitar runtime stale."
      return
    } catch {
      if ($attempt -eq 3) {
        throw
      }
      Start-Sleep -Seconds 2
    }
  }
}

function Wait-HttpReady {
  param(
    [string]$Label,
    [string]$Uri,
    [int]$TimeoutSec = 120,
    [System.Diagnostics.Process]$Process = $null,
    [string[]]$LogPaths = @()
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ($Process) {
      $Process.Refresh()
      if ($Process.HasExited) {
        foreach ($logPath in $LogPaths) {
          if (Test-Path -LiteralPath $logPath) {
            Write-Host ""
            Write-Host "Ultimas linhas de $logPath"
            Get-Content -LiteralPath $logPath -Tail 80
          }
        }
        throw "$Label encerrou antes de responder em $Uri (exit code $($Process.ExitCode))."
      }
    }

    try {
      $response = Invoke-WebRequest -UseBasicParsing $Uri -TimeoutSec 15
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $response
      }
    } catch {
    }

    Start-Sleep -Seconds 2
  }

  foreach ($logPath in $LogPaths) {
    if (Test-Path -LiteralPath $logPath) {
      Write-Host ""
      Write-Host "Ultimas linhas de $logPath"
      Get-Content -LiteralPath $logPath -Tail 80
    }
  }
  throw "$Label nao respondeu em ate $TimeoutSec s: $Uri"
}

function Wait-PostgresReady {
  param([int]$TimeoutSec = 120)

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    docker compose exec -T postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "select 1;" 2>$null |
      Out-Null
    if ($LASTEXITCODE -eq 0) {
      return
    }

    Start-Sleep -Seconds 2
  }

  throw "Postgres nao respondeu apos $TimeoutSec s."
}

function Test-ServingDatabaseReady {
  $result = docker compose exec -T postgres psql `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB `
    -Atc "select to_regclass('mart.fact_matches') is not null;" 2>$null

  return $LASTEXITCODE -eq 0 -and ($result | Select-Object -First 1).Trim() -eq "t"
}

function Initialize-ServingDatabase {
  if (Test-ServingDatabaseReady) {
    Write-Step "Banco serving ja esta carregado."
    return
  }

  if (-not (Test-Path -LiteralPath $ServingSnapshotPath)) {
    throw "Banco serving vazio e snapshot nao encontrado: $ServingSnapshotPath"
  }

  Write-Step "Banco serving vazio. Restaurando snapshot local (primeira execucao pode levar alguns minutos)."
  docker cp $ServingSnapshotPath "football_postgres:/tmp/football_serving.dump"
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao copiar snapshot para o container PostgreSQL."
  }

  docker compose exec -T postgres pg_restore `
    --clean `
    --if-exists `
    --no-owner `
    --no-acl `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB `
    /tmp/football_serving.dump
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao restaurar snapshot serving."
  }

  docker compose exec -T postgres rm -f /tmp/football_serving.dump

  if (-not (Test-ServingDatabaseReady)) {
    throw "Snapshot restaurado, mas mart.fact_matches continua indisponivel."
  }

  Write-Step "Snapshot serving restaurado com sucesso."
}

function Sync-SnapshotMigrationHistory {
  if (-not (Test-ServingDatabaseReady)) {
    return
  }

  $snapshotMigrationCeiling = 20260426094000L
  $migrationVersions = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "db\migrations") -Filter "*.sql" |
    ForEach-Object {
      if ($_.BaseName -match '^(\d+)_') {
        [long]$matches[1]
      }
    } |
    Where-Object { $_ -le $snapshotMigrationCeiling } |
    Sort-Object -Unique

  if (-not $migrationVersions) {
    return
  }

  $valueRows = ($migrationVersions | ForEach-Object { "('$($_)')" }) -join ","
  $syncSql = @"
create table if not exists public.schema_migrations (
  version varchar(255) primary key
);
insert into public.schema_migrations (version)
values $valueRows
on conflict (version) do nothing;
"@

  $syncSql | docker compose exec -T postgres psql `
    -v ON_ERROR_STOP=1 `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao sincronizar historico de migracoes do snapshot."
  }

  Write-Step "Historico de migracoes do snapshot sincronizado."
}

function Get-DatabaseScalar {
  param([Parameter(Mandatory = $true)][string]$Sql)

  $result = docker compose exec -T postgres psql `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB `
    -Atc $Sql 2>$null
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao consultar readiness do banco."
  }
  return ($result | Select-Object -First 1).Trim()
}

function Initialize-WorldCupDelta {
  $worldCupEditions = [int](Get-DatabaseScalar -Sql "
    select count(*)
    from raw.competition_seasons
    where competition_key = 'fifa_world_cup_mens';
  ")
  if ($worldCupEditions -gt 0) {
    Write-Step "Delta da Copa do Mundo ja esta carregado."
    return
  }

  if (-not (Test-Path -LiteralPath $WorldCupDeltaPath)) {
    throw "Dados da Copa ausentes e artefato nao encontrado: $WorldCupDeltaPath"
  }
  if (-not (Test-Path -LiteralPath $WorldCupLoadSqlPath)) {
    throw "SQL de carga da Copa nao encontrado: $WorldCupLoadSqlPath"
  }

  $extractRoot = Join-Path $RepoRoot ".tmp\wc_delta_load"
  if (Test-Path -LiteralPath $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

  Write-Step "Extraindo delta da Copa do Mundo."
  tar -xzf $WorldCupDeltaPath -C $extractRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao extrair delta da Copa do Mundo."
  }

  $extractedDelta = Join-Path $extractRoot "wc_delta"
  docker compose exec -T postgres rm -rf /tmp/wc_delta
  docker compose exec -T postgres mkdir -p /tmp/wc_delta
  docker cp "$extractedDelta\." "football_postgres:/tmp/wc_delta/"
  docker cp $WorldCupLoadSqlPath "football_postgres:/tmp/load_world_cup_delta.sql"
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao copiar delta da Copa para o PostgreSQL."
  }

  Write-Step "Carregando historico da Copa do Mundo (pode levar alguns minutos)."
  docker compose exec -T postgres psql `
    -v ON_ERROR_STOP=1 `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB `
    -f /tmp/load_world_cup_delta.sql
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao carregar delta da Copa do Mundo."
  }

  docker compose exec -T postgres rm -rf /tmp/wc_delta /tmp/load_world_cup_delta.sql
  Remove-Item -LiteralPath $extractRoot -Recurse -Force

  $worldCupEditions = [int](Get-DatabaseScalar -Sql "
    select count(*)
    from raw.competition_seasons
    where competition_key = 'fifa_world_cup_mens';
  ")
  if ($worldCupEditions -le 0) {
    throw "Carga da Copa terminou sem edicoes publicadas."
  }
  Write-Step "Delta da Copa carregado: $worldCupEditions edicoes."
}

function Refresh-ServingSummaries {
  $playerRows = [int](Get-DatabaseScalar -Sql "select count(*) from mart.player_serving_summary;")
  $competitionRows = [int](Get-DatabaseScalar -Sql "select count(*) from mart.competition_serving_summary;")
  $teamMonthlyRows = [int](Get-DatabaseScalar -Sql "select count(*) from mart.team_monthly_stats;")

  if ($playerRows -gt 0 -and $competitionRows -gt 0 -and $teamMonthlyRows -gt 0) {
    Write-Step "Resumos serving ja estao materializados."
    return
  }

  Write-Step "Materializando resumos serving vazios."
  docker compose exec -T airflow-scheduler dbt run `
    --project-dir /opt/airflow/dbt `
    --profiles-dir /opt/airflow/dbt `
    --select +team_monthly_stats competition_serving_summary player_match_summary player_season_summary player_serving_summary player_90_metrics coach_performance_summary `
    --threads 1
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao materializar resumos serving."
  }
}

function Refresh-CoachAssignments {
  $assignmentRows = [int](Get-DatabaseScalar -Sql "select count(*) from mart.fact_coach_match_assignment;")
  if ($assignmentRows -gt 0) {
    Write-Step "Atribuicoes de tecnicos ja estao carregadas."
    return
  }

  if (-not (Test-Path -LiteralPath $CoachRefreshSqlPath)) {
    throw "SQL de tecnicos nao encontrado: $CoachRefreshSqlPath"
  }

  Write-Step "Derivando atribuicoes seguras de tecnicos por partida."
  docker cp $CoachRefreshSqlPath "football_postgres:/tmp/refresh_local_coach_assignments.sql"
  docker compose exec -T postgres psql `
    -v ON_ERROR_STOP=1 `
    -U $env:POSTGRES_USER `
    -d $env:POSTGRES_DB `
    -f /tmp/refresh_local_coach_assignments.sql
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao derivar atribuicoes de tecnicos."
  }
  docker compose exec -T postgres rm -f /tmp/refresh_local_coach_assignments.sql

  $assignmentRows = [int](Get-DatabaseScalar -Sql "select count(*) from mart.fact_coach_match_assignment;")
  Write-Step "Atribuicoes de tecnicos carregadas: $assignmentRows."
}

function Test-BackendDependencies {
  & python -c "import fastapi, uvicorn, psycopg, psycopg_pool" 2>$null | Out-Null
}

function Test-FrontendDependencies {
  $checkScript = @"
const path = require('node:path');
const postcssPkg = require.resolve('postcss/package.json');
const postcssDir = path.dirname(postcssPkg);
require.resolve('next/package.json');
require.resolve('picocolors/package.json', { paths: [postcssDir] });
"@

  Push-Location $FrontendDir
  try {
    & node -e $checkScript 2>$null | Out-Null
  } finally {
    Pop-Location
  }
}

function Get-PnpmCommandPath {
  $cmdCandidate = Join-Path $env:APPDATA "npm\pnpm.cmd"
  if (Test-Path -LiteralPath $cmdCandidate) {
    return $cmdCandidate
  }

  $command = Get-Command pnpm -ErrorAction Stop
  return $command.Source
}

function Get-NextEntrypointPath {
  $nextEntrypoint = Join-Path $FrontendDir "node_modules\next\dist\bin\next"
  if (-not (Test-Path -LiteralPath $nextEntrypoint)) {
    throw "Entrypoint local do Next.js nao encontrado: $nextEntrypoint. Execute pnpm install em frontend."
  }
  return "node_modules/next/dist/bin/next"
}

Assert-Command -Name "docker" -Hint "Docker nao encontrado no PATH. Instale o Docker Desktop e tente novamente."
Assert-Command -Name "python" -Hint "Python nao encontrado no PATH. Ative o ambiente correto e tente novamente."
Assert-Command -Name "node" -Hint "Node.js nao encontrado no PATH. Instale Node.js 20+ e tente novamente."
Assert-Command -Name "pnpm" -Hint "pnpm nao encontrado no PATH. Instale pnpm e tente novamente."

if (-not (Test-Path -LiteralPath $ApiDir)) {
  throw "Diretorio da API nao encontrado: $ApiDir"
}

if (-not (Test-Path -LiteralPath $FrontendDir)) {
  throw "Diretorio do frontend nao encontrado: $FrontendDir"
}

New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null

Load-DotEnv -Path $RootEnvPath

if (-not $env:POSTGRES_USER) {
  [Environment]::SetEnvironmentVariable("POSTGRES_USER", "football", "Process")
}
if (-not $env:POSTGRES_PASSWORD) {
  [Environment]::SetEnvironmentVariable("POSTGRES_PASSWORD", "football", "Process")
}
if (-not $env:POSTGRES_DB) {
  [Environment]::SetEnvironmentVariable("POSTGRES_DB", "football_dw", "Process")
}

[Environment]::SetEnvironmentVariable("POSTGRES_HOST", "127.0.0.1", "Process")
[Environment]::SetEnvironmentVariable("POSTGRES_PORT", "5432", "Process")
[Environment]::SetEnvironmentVariable(
  "FOOTBALL_PG_DSN",
  "postgresql://$($env:POSTGRES_USER):$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/$($env:POSTGRES_DB)",
  "Process"
)

Set-DotEnvValue -Path $FrontendEnvPath -Key "NEXT_PUBLIC_BFF_BASE_URL" -Value "http://127.0.0.1:$BffPort"
Set-DotEnvValue -Path $FrontendEnvPath -Key "NEXT_PUBLIC_APP_ENV" -Value "local"
[Environment]::SetEnvironmentVariable("NEXT_PUBLIC_BFF_BASE_URL", "http://127.0.0.1:$BffPort", "Process")

Write-Step "Subindo infraestrutura base Docker."
Push-Location $RepoRoot
try {
  docker compose up -d postgres minio metabase
  if ($LASTEXITCODE -ne 0) {
    throw "Falha ao subir infraestrutura base Docker."
  }
} finally {
  Pop-Location
}

Write-Step "Validando Postgres."
Push-Location $RepoRoot
try {
  Wait-PostgresReady
  Initialize-ServingDatabase
  Sync-SnapshotMigrationHistory

  Write-Step "Subindo migracoes, MinIO init e Airflow."
  docker compose up -d dbmate minio-init airflow-init airflow-webserver airflow-scheduler
  if ($LASTEXITCODE -ne 0) {
    docker compose logs --tail 100 dbmate airflow-init airflow-webserver airflow-scheduler
    throw "Falha ao subir servicos de dados/orquestracao."
  }
  Initialize-WorldCupDelta
  Refresh-ServingSummaries
  Refresh-CoachAssignments
} finally {
  Pop-Location
}

Write-Step "Construindo e subindo API + frontend no Docker."
docker compose up -d --build api frontend
if ($LASTEXITCODE -ne 0) {
  docker compose logs --tail 120 api frontend
  throw "Falha ao construir ou subir API/frontend."
}

Write-Step "Aguardando API."
$null = Wait-HttpReady `
  -Label "BFF" `
  -Uri "http://127.0.0.1:$BffPort/health" `
  -TimeoutSec 300

Write-Step "Aguardando frontend."
$null = Wait-HttpReady `
  -Label "frontend" `
  -Uri "http://127.0.0.1:$FrontendPort/api/health" `
  -TimeoutSec 300

Write-Step "Validando rota da API com banco."
$apiProbe = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$BffPort/api/v1/matches?competition=sudamericana&season=2024&pageSize=1" -TimeoutSec 30

Write-Host ""
Write-Host "Ambiente local pronto."
Write-Host "Airflow : http://127.0.0.1:8080"
Write-Host "Metabase: http://127.0.0.1:3000"
Write-Host "BFF     : http://127.0.0.1:$BffPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host ""
Write-Host "Evidencia objetiva:"
Write-Host "- Postgres validado via docker compose exec -T postgres psql -c 'select 1;'"
Write-Host "- BFF /health = 200"
Write-Host "- BFF /api/v1/matches... = $($apiProbe.StatusCode)"
Write-Host "- Frontend /api/health = 200"
Write-Host ""
Write-Host "Logs:"
Write-Host "- docker compose logs -f api frontend"
