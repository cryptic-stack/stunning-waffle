param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

docker compose -f infra/compose/docker-compose.yml down --remove-orphans @ComposeArgs
if ($LASTEXITCODE -ne 0) {
  throw ("Compose shutdown failed (exit code {0})" -f $LASTEXITCODE)
}
