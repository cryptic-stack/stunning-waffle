param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

docker compose -f infra/compose/docker-compose.yml up --build -d @ComposeArgs
