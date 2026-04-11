param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

if (-not $env:AUTH_MODE) {
  $env:AUTH_MODE = "dev"
}

powershell -ExecutionPolicy Bypass -File infra/scripts/prebuild-workers.ps1
docker compose -f infra/compose/docker-compose.yml up --build -d @ComposeArgs
