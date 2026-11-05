$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $PSScriptRoot 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$skillSource = Join-Path $PSScriptRoot 'skills\organize-downloads\*'
$skillZip = Join-Path $dist 'organize-downloads.skill.zip'
$providerSource = Join-Path $PSScriptRoot 'providers\device-info\*'
$providerZip = Join-Path $dist 'device-info.provider.zip'

Remove-Item -LiteralPath $skillZip -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $providerZip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $skillSource -DestinationPath $skillZip
Compress-Archive -Path $providerSource -DestinationPath $providerZip

Write-Host "Created $skillZip"
Write-Host "Created $providerZip"
