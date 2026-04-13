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

$playwrightBaseUrl = if ($env:PLAYWRIGHT_BASE_URL) { $env:PLAYWRIGHT_BASE_URL } else { "http://host.docker.internal:3000" }
$playwrightApiBaseUrl = if ($env:PLAYWRIGHT_API_BASE_URL) { $env:PLAYWRIGHT_API_BASE_URL } else { "http://host.docker.internal:8000" }
$playwrightAuthUserId = if ($env:PLAYWRIGHT_AUTH_USER_ID) { $env:PLAYWRIGHT_AUTH_USER_ID } else { "" }
$playwrightAuthUserEmail = if ($env:PLAYWRIGHT_AUTH_USER_EMAIL) { $env:PLAYWRIGHT_AUTH_USER_EMAIL } else { "" }
$playwrightAuthUserName = if ($env:PLAYWRIGHT_AUTH_USER_NAME) { $env:PLAYWRIGHT_AUTH_USER_NAME } else { "" }

$sessionStatus = curl.exe -s -o NUL -w "%{http_code}" "$playwrightApiBaseUrl/api/v1/sessions"
if (($sessionStatus -eq "401" -or $sessionStatus -eq "403") -and -not $playwrightAuthUserId) {
  throw "Viewer e2e requires AUTH_MODE=dev, or a frontend rebuilt with VITE_AUTH_USER_ID plus PLAYWRIGHT_AUTH_USER_ID set for header-mode validation."
}

Invoke-CheckedCommand `
  -FailureMessage "Viewer end-to-end container run failed" `
  -Command {
    docker run --rm `
      --add-host host.docker.internal:host-gateway `
      -e "PLAYWRIGHT_BASE_URL=$playwrightBaseUrl" `
      -e "PLAYWRIGHT_API_BASE_URL=$playwrightApiBaseUrl" `
      -e "PLAYWRIGHT_AUTH_USER_ID=$playwrightAuthUserId" `
      -e "PLAYWRIGHT_AUTH_USER_EMAIL=$playwrightAuthUserEmail" `
      -e "PLAYWRIGHT_AUTH_USER_NAME=$playwrightAuthUserName" `
      -v "${PWD}:/workspace" `
      -w /workspace/apps/frontend `
      mcr.microsoft.com/playwright:v1.59.1-noble `
      sh -lc "export COREPACK_ENABLE_DOWNLOAD_PROMPT=0 && corepack enable && pnpm install --frozen-lockfile && pnpm test:e2e"
  }
