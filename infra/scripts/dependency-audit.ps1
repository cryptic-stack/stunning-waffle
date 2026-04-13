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

Write-Output "==> Auditing JavaScript dependencies"
Invoke-CheckedCommand `
  -FailureMessage "JavaScript dependency audit failed" `
  -Command {
    docker run --rm `
      -v "${PWD}:/workspace" `
      -w /workspace `
      node:20-alpine@sha256:f598378b5240225e6beab68fa9f356db1fb8efe55173e6d4d8153113bb8f333c `
      sh -lc "export COREPACK_ENABLE_DOWNLOAD_PROMPT=0 && corepack enable >/dev/null && pnpm install --frozen-lockfile >/dev/null && pnpm audit --prod"
  }

Write-Output "==> Auditing API Python constraints"
Invoke-CheckedCommand `
  -FailureMessage "API Python dependency audit failed" `
  -Command {
    docker run --rm `
      -v "${PWD}/apps/api:/workspace" `
      -w /workspace `
      python:3.12-slim `
      sh -lc "export PIP_DISABLE_PIP_VERSION_CHECK=1 && python -m pip install --root-user-action=ignore --no-cache-dir pip-audit==2.9.0 >/dev/null && pip-audit -r constraints.txt"
  }

Write-Output "==> Auditing session-agent Python constraints"
Invoke-CheckedCommand `
  -FailureMessage "Session-agent Python dependency audit failed" `
  -Command {
    docker run --rm `
      -v "${PWD}/apps/session-agent:/workspace" `
      -w /workspace `
      python:3.12-slim `
      sh -lc "export PIP_DISABLE_PIP_VERSION_CHECK=1 && python -m pip install --root-user-action=ignore --no-cache-dir pip-audit==2.9.0 >/dev/null && pip-audit -r constraints.txt"
  }
