$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $repoRoot

try {
  $images = @(
    @{ Tag = "foss-browserlab-chromium-worker:latest"; Dockerfile = "images/chromium/Dockerfile" },
    @{ Tag = "foss-browserlab-firefox-worker:latest"; Dockerfile = "images/firefox/Dockerfile" },
    @{ Tag = "foss-browserlab-brave-worker:latest"; Dockerfile = "images/brave/Dockerfile" },
    @{ Tag = "foss-browserlab-edge-worker:latest"; Dockerfile = "images/edge/Dockerfile" },
    @{ Tag = "foss-browserlab-vivaldi-worker:latest"; Dockerfile = "images/vivaldi/Dockerfile" },
    @{ Tag = "foss-browserlab-ubuntu-xfce-worker:latest"; Dockerfile = "images/ubuntu-xfce/Dockerfile" },
    @{ Tag = "foss-browserlab-kali-xfce-worker:latest"; Dockerfile = "images/kali-xfce/Dockerfile" }
  )

  foreach ($image in $images) {
    Write-Host ("building {0}..." -f $image.Tag)
    docker build -t $image.Tag -f $image.Dockerfile .
  }
}
finally {
  Pop-Location
}
