param([string]$PythonPath = 'python', [switch]$SkipAdmin)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path 'tmp\install' | Out-Null
$env:TEMP = (Resolve-Path -LiteralPath 'tmp\install').Path
$env:TMP = $env:TEMP
$env:npm_config_cache = Join-Path $PSScriptRoot 'tmp\npm-cache'
& $PythonPath -c 'import sys; assert sys.version_info[:2] == (3,12), "Gunakan Python 3.12 (64-bit) untuk lockfile Windows yang diuji."'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 diperlukan. Gunakan -PythonPath untuk memilih executable.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $PythonPath -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat virtual environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependensi Python gagal.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
& '.\.venv\Scripts\python.exe' -c 'from backend.app.config import Settings; import tiktoken; print("Tokenizer:", tiktoken.get_encoding("cl100k_base").name)'
if ($LASTEXITCODE -ne 0) { throw 'Unduhan tabel tokenizer gagal.' }
Push-Location -LiteralPath 'frontend'
try {
    & npm.cmd ci --no-fund --no-audit
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi frontend gagal. Pasang Node.js versi yang didukung Vite.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Build frontend gagal.' }
} finally { Pop-Location }
if (-not $SkipAdmin) {
    & '.\.venv\Scripts\python.exe' -m backend.setup_admin
    if ($LASTEXITCODE -ne 0) { throw 'Setup admin belum berhasil.' }
}
Write-Host 'Setup selesai. Pasang OCR melalui scripts/setup-ocr.ps1, isi konfigurasi relay, kemudian jalankan start.ps1.'
