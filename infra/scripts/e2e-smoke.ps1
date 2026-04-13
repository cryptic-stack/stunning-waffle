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

function New-SmokeSession {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Browser
  )

  $body = @{
    browser = $Browser
    resolution = @{
      width = 1280
      height = 720
    }
    timeout_seconds = 120
    idle_timeout_seconds = 60
    allow_file_upload = $true
  } | ConvertTo-Json -Depth 4

  return Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/sessions" `
    -Method Post `
    -Headers @{ "X-User-Id" = "smoke-user" } `
    -ContentType "application/json" `
    -Body $body
}

function New-SmokeDesktopSession {
  param(
    [Parameter(Mandatory = $true)]
    [string]$DesktopProfile
  )

  $body = @{
    session_kind = "desktop"
    desktop_profile = $DesktopProfile
    resolution = @{
      width = 1280
      height = 720
    }
    timeout_seconds = 120
    idle_timeout_seconds = 60
    allow_file_upload = $true
  } | ConvertTo-Json -Depth 4

  return Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/sessions" `
    -Method Post `
    -Headers @{ "X-User-Id" = "smoke-user" } `
    -ContentType "application/json" `
    -Body $body
}

function Invoke-SmokeRuntime {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("browser", "desktop")]
    [string]$RuntimeKind,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeName
  )

  Write-Output ("launching {0} smoke session..." -f $RuntimeName)
  if ($RuntimeKind -eq "browser") {
    $session = New-SmokeSession -Browser $RuntimeName
  }
  else {
    $session = New-SmokeDesktopSession -DesktopProfile $RuntimeName
  }
  Write-Output ("{0} create response: {1}" -f $RuntimeName, ($session | ConvertTo-Json -Compress))

  $state = $null
  for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
    Start-Sleep -Seconds 2
    $state = Invoke-RestMethod -Uri ("http://localhost:8000/api/v1/sessions/{0}" -f $session.session_id) -Headers @{ "X-User-Id" = "smoke-user" }
    if ($state.status -eq "active") {
      break
    }
  }
  Write-Output ("{0} state: {1}" -f $RuntimeName, ($state | ConvertTo-Json -Compress))

  if ($state.status -ne "active") {
    throw ("{0} worker did not become active" -f $RuntimeName)
  }

  $clipboard = Invoke-RestMethod `
    -Uri ("http://localhost:8000/api/v1/sessions/{0}/clipboard" -f $session.session_id) `
    -Method Post `
    -Headers @{ "X-User-Id" = "smoke-user" } `
    -ContentType "application/json" `
    -Body '{"text":"smoke clipboard"}'
  Write-Output ("{0} clipboard: {1}" -f $RuntimeName, ($clipboard | ConvertTo-Json -Compress))

  $tempFile = Join-Path $env:TEMP ("{0}-smoke.txt" -f $RuntimeName)
  Set-Content -Path $tempFile -Value ("upload for {0}" -f $RuntimeName) -NoNewline
  $upload = & curl.exe -s -X POST -H "X-User-Id: smoke-user" -F "upload=@$tempFile;type=text/plain" ("http://localhost:8000/api/v1/sessions/{0}/file-upload" -f $session.session_id)
  if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $tempFile -Force
    throw ("{0} upload request failed (exit code {1})" -f $RuntimeName, $LASTEXITCODE)
  }
  Remove-Item -LiteralPath $tempFile -Force
  Write-Output ("{0} upload: {1}" -f $RuntimeName, $upload)

  $downloads = Invoke-RestMethod `
    -Uri ("http://localhost:8000/api/v1/sessions/{0}/downloads" -f $session.session_id) `
    -Headers @{ "X-User-Id" = "smoke-user" }
  Write-Output ("{0} downloads: {1}" -f $RuntimeName, ($downloads | ConvertTo-Json -Compress))
  if (-not $downloads.items -or -not $downloads.items[0].filename) {
    throw ("{0} downloads are missing uploaded file" -f $RuntimeName)
  }

  $downloadStatus = & curl.exe -s -o NUL -w "%{http_code}" -H "X-User-Id: smoke-user" ("http://localhost:8000/api/v1/sessions/{0}/downloads/{1}" -f $session.session_id, $downloads.items[0].filename)
  if ($LASTEXITCODE -ne 0) {
    throw ("{0} download request failed (exit code {1})" -f $RuntimeName, $LASTEXITCODE)
  }
  if ($downloadStatus -ne "200") {
    throw ("{0} download endpoint returned {1}" -f $RuntimeName, $downloadStatus)
  }

  $screenshotHeaders = & curl.exe -s -D - -o NUL -H "X-User-Id: smoke-user" ("http://localhost:8000/api/v1/sessions/{0}/screenshot" -f $session.session_id)
  if ($LASTEXITCODE -ne 0) {
    throw ("{0} screenshot request failed (exit code {1})" -f $RuntimeName, $LASTEXITCODE)
  }
  $normalizedHeaders = ($screenshotHeaders | Out-String).ToLowerInvariant()
  if ($normalizedHeaders -notmatch "content-type:\s*image/png") {
    throw ("{0} screenshot did not return PNG" -f $RuntimeName)
  }

  Invoke-RestMethod `
    -Uri ("http://localhost:8000/api/v1/sessions/{0}" -f $session.session_id) `
    -Method Delete `
    -Headers @{ "X-User-Id" = "smoke-user" } | Out-Null
}

$frontendStatus = & curl.exe -s -o NUL -w "%{http_code}" http://localhost:3000
if ($LASTEXITCODE -ne 0) {
  throw ("Frontend health request failed (exit code {0})" -f $LASTEXITCODE)
}
$apiStatus = & curl.exe -s -o NUL -w "%{http_code}" http://localhost:8000/healthz
if ($LASTEXITCODE -ne 0) {
  throw ("API health request failed (exit code {0})" -f $LASTEXITCODE)
}
$rtcConfig = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rtc/config"

Write-Output "frontend: $frontendStatus"
Write-Output "api: $apiStatus"
Write-Output ("rtc ice servers: {0}" -f $rtcConfig.ice_servers.Count)

foreach ($browser in @("chromium", "firefox")) {
  Invoke-SmokeRuntime -RuntimeKind "browser" -RuntimeName $browser
}

foreach ($profile in @("ubuntu-xfce", "kali-xfce")) {
  Invoke-SmokeRuntime -RuntimeKind "desktop" -RuntimeName $profile
}
