param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)]
    [scriptblock]$Command,

    [Parameter(Mandatory = $true)]
    [string]$FailureMessage
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw ("{0} (exit code {1})" -f $FailureMessage, $LASTEXITCODE)
  }
}

if (-not $env:AUTH_MODE) {
  $env:AUTH_MODE = "dev"
}

Invoke-CheckedCommand `
  -FailureMessage "Worker prebuild failed" `
  -Command { powershell -ExecutionPolicy Bypass -File infra/scripts/prebuild-workers.ps1 }

Invoke-CheckedCommand `
  -FailureMessage "Compose startup failed" `
  -Command { docker compose -f infra/compose/docker-compose.yml up --build -d @ComposeArgs }
