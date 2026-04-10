param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

docker compose -f infra/compose/docker-compose.yml down --remove-orphans @ComposeArgs
