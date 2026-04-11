$ErrorActionPreference = "Stop"

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

$frontendStatus = curl.exe -s -o NUL -w "%{http_code}" http://localhost:3000
$apiStatus = curl.exe -s -o NUL -w "%{http_code}" http://localhost:8000/healthz
$rtcConfig = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rtc/config"

Write-Output "frontend: $frontendStatus"
Write-Output "api: $apiStatus"
Write-Output ("rtc ice servers: {0}" -f $rtcConfig.ice_servers.Count)

foreach ($browser in @("chromium", "firefox")) {
  Write-Output ("launching {0} smoke session..." -f $browser)
  $session = New-SmokeSession -Browser $browser
  Write-Output ("{0} create response: {1}" -f $browser, ($session | ConvertTo-Json -Compress))

  Start-Sleep -Seconds 6
  $state = Invoke-RestMethod -Uri ("http://localhost:8000/api/v1/sessions/{0}" -f $session.session_id) -Headers @{ "X-User-Id" = "smoke-user" }
  Write-Output ("{0} state: {1}" -f $browser, ($state | ConvertTo-Json -Compress))

  if ($state.status -ne "active") {
    throw ("{0} worker did not become active" -f $browser)
  }

  $clipboard = Invoke-RestMethod `
    -Uri ("http://localhost:8000/api/v1/sessions/{0}/clipboard" -f $session.session_id) `
    -Method Post `
    -Headers @{ "X-User-Id" = "smoke-user" } `
    -ContentType "application/json" `
    -Body '{"text":"smoke clipboard"}'
  Write-Output ("{0} clipboard: {1}" -f $browser, ($clipboard | ConvertTo-Json -Compress))

  $tempFile = Join-Path $env:TEMP ("{0}-smoke.txt" -f $browser)
  Set-Content -Path $tempFile -Value ("upload for {0}" -f $browser) -NoNewline
  $upload = curl.exe -s -X POST -H "X-User-Id: smoke-user" -F "upload=@$tempFile;type=text/plain" ("http://localhost:8000/api/v1/sessions/{0}/file-upload" -f $session.session_id)
  Remove-Item -LiteralPath $tempFile -Force
  Write-Output ("{0} upload: {1}" -f $browser, $upload)

  Invoke-RestMethod `
    -Uri ("http://localhost:8000/api/v1/sessions/{0}" -f $session.session_id) `
    -Method Delete `
    -Headers @{ "X-User-Id" = "smoke-user" } | Out-Null
}
