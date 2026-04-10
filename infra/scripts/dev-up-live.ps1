param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml up --build -d frontend api @ComposeArgs
