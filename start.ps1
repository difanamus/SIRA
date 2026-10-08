param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Jalankan setup.ps1 terlebih dahulu.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Frontend belum dibangun. Jalankan setup.ps1.' }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Pilih port 1024-65535.' }
$env:SIRA_ORIGIN = 'http://127.0.0.1:' + $Port
Write-Host ('SIRA: http://127.0.0.1:' + $Port)
Write-Host 'Tekan Ctrl+C untuk menghentikan aplikasi. Gunakan satu proses backend untuk prototype ini.'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port --no-access-log
