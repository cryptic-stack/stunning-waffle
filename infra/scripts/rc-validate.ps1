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

if (-not $env:AUTH_MODE) { $env:AUTH_MODE = "header" }
if (-not $env:VITE_AUTH_USER_ID) { $env:VITE_AUTH_USER_ID = "rc-validator" }
if (-not $env:VITE_AUTH_USER_EMAIL) { $env:VITE_AUTH_USER_EMAIL = "rc-validator@example.com" }
if (-not $env:VITE_AUTH_USER_NAME) { $env:VITE_AUTH_USER_NAME = "RC Validator" }
if (-not $env:PLAYWRIGHT_AUTH_USER_ID) { $env:PLAYWRIGHT_AUTH_USER_ID = $env:VITE_AUTH_USER_ID }
if (-not $env:PLAYWRIGHT_AUTH_USER_EMAIL) { $env:PLAYWRIGHT_AUTH_USER_EMAIL = $env:VITE_AUTH_USER_EMAIL }
if (-not $env:PLAYWRIGHT_AUTH_USER_NAME) { $env:PLAYWRIGHT_AUTH_USER_NAME = $env:VITE_AUTH_USER_NAME }

$keepStackUp = ($env:KEEP_STACK_UP -eq "true")

try {
  Write-Output "==> Prebuilding worker images"
  Invoke-CheckedCommand `
    -FailureMessage "Worker prebuild failed" `
    -Command { powershell -ExecutionPolicy Bypass -File infra/scripts/prebuild-workers.ps1 }

  Write-Output "==> Starting release-candidate stack"
  Invoke-CheckedCommand `
    -FailureMessage "Release-candidate stack startup failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml up --build -d }

  Write-Output "==> Waiting for API readiness"
  $ready = $null
  for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
    try {
      $ready = Invoke-RestMethod -Uri "http://localhost:8000/readyz"
      break
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  if (-not $ready -or $ready.status -ne "ok") {
    throw "API did not become ready for RC validation."
  }
  $ready | ConvertTo-Json -Depth 6 | Write-Output

  Write-Output "==> Linting API"
  Invoke-CheckedCommand `
    -FailureMessage "API lint failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml run --rm api python -m ruff check app tests }

  Write-Output "==> Auditing dependencies"
  Invoke-CheckedCommand `
    -FailureMessage "Dependency audit failed" `
    -Command { powershell -ExecutionPolicy Bypass -File infra/scripts/dependency-audit.ps1 }

  Write-Output "==> Testing API"
  Invoke-CheckedCommand `
    -FailureMessage "API tests failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml run --rm api pytest }

  Write-Output "==> Linting frontend"
  Invoke-CheckedCommand `
    -FailureMessage "Frontend lint failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm lint }

  Write-Output "==> Typechecking frontend"
  Invoke-CheckedCommand `
    -FailureMessage "Frontend typecheck failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm typecheck }

  Write-Output "==> Testing frontend"
  Invoke-CheckedCommand `
    -FailureMessage "Frontend tests failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm test }

  Write-Output "==> Building frontend"
  Invoke-CheckedCommand `
    -FailureMessage "Frontend build failed" `
    -Command { docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm build }

  Write-Output "==> Running runtime smoke"
  Invoke-CheckedCommand `
    -FailureMessage "Runtime smoke failed" `
    -Command { powershell -ExecutionPolicy Bypass -File infra/scripts/e2e-smoke.ps1 }

  Write-Output "==> Running viewer end-to-end checks"
  Invoke-CheckedCommand `
    -FailureMessage "Viewer end-to-end checks failed" `
    -Command { powershell -ExecutionPolicy Bypass -File infra/scripts/e2e-viewer.ps1 }

  Write-Output "RC validation passed."
}
finally {
  if (-not $keepStackUp) {
    docker compose -f infra/compose/docker-compose.yml down --remove-orphans | Out-Null
  }
}
