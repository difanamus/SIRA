param([string]$PythonPath = '', [switch]$SkipAdmin)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path 'tmp\install' | Out-Null
$env:TEMP = (Resolve-Path -LiteralPath 'tmp\install').Path
$env:TMP = $env:TEMP
$env:npm_config_cache = Join-Path $PSScriptRoot 'tmp\npm-cache'

# Returns the executable path when the command is Python 3.12 64-bit, otherwise $null.
# Code is sent through stdin so quotes survive Windows PowerShell 5.1.
function Get-Python312([string[]]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $exe = $Command[0]
        $extra = @($Command | Select-Object -Skip 1)
        $probe = "import struct, sys`nprint('%d.%d-%d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8))`nprint(sys.executable)"
        $output = @($probe | & $exe @extra - 2>$null)
        if ($LASTEXITCODE -eq 0 -and $output.Count -ge 2 -and $output[0].Trim() -eq '3.12-64') { return $output[1].Trim() }
    } catch {
    } finally {
        $ErrorActionPreference = $previous
    }
    return $null
}

function Stop-Setup([string]$Message) {
    Write-Host ''
    Write-Host $Message -ForegroundColor Yellow
    exit 1
}

$python = $null
if ($PythonPath) {
    $python = Get-Python312 @($PythonPath)
    if (-not $python) {
        Stop-Setup ("'" + $PythonPath + "' bukan Python 3.12 (64-bit). Periksa lokasinya, misalnya dengan: py -0p")
    }
} elseif (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    # Rerun of setup: keep the existing environment when it is already Python 3.12.
    $python = Get-Python312 @('.venv\Scripts\python.exe')
    if (-not $python) {
        Stop-Setup "Folder .venv sudah ada tetapi bukan Python 3.12. Hapus folder .venv, lalu jalankan ulang .\setup.ps1"
    }
} else {
    $candidates = @(, @('python'))
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += , @('py', '-3.12') }
    if ($env:LOCALAPPDATA) { $candidates += , @(Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe') }
    if ($env:ProgramFiles) { $candidates += , @(Join-Path $env:ProgramFiles 'Python312\python.exe') }
    foreach ($candidate in $candidates) {
        if ($candidate.Count -eq 1 -and $candidate[0] -like '*\*' -and -not (Test-Path -LiteralPath $candidate[0])) { continue }
        $python = Get-Python312 $candidate
        if ($python) { break }
    }
    if (-not $python) {
        Stop-Setup @"
Python 3.12 (64-bit) belum ditemukan di komputer ini.
SIRA memakai Python 3.12. Versi lain (misalnya 3.13 atau 3.14) boleh tetap terpasang berdampingan.

  1. Buka https://www.python.org/downloads/windows/
     lalu unduh "Windows installer (64-bit)" untuk Python 3.12 (misalnya 3.12.10).
  2. Pasang dengan pengaturan bawaan, lalu tutup dan buka kembali PowerShell.
  3. Jalankan ulang: .\setup.ps1

Jika Python 3.12 sudah terpasang di lokasi lain:
  .\setup.ps1 -PythonPath 'C:\lokasi\Python312\python.exe'
"@
    }
}
Write-Host ('Python 3.12 ditemukan: ' + $python)

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat virtual environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependensi Python gagal.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
@'
from backend.app.config import Settings
import tiktoken
print("Tokenizer:", tiktoken.get_encoding("cl100k_base").name)
'@ | & '.\.venv\Scripts\python.exe' -
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
& '.\.venv\Scripts\python.exe' -m backend.setup_relay
if ($LASTEXITCODE -ne 0) { throw 'Koneksi AI otomatis belum berhasil; baca pesan di atas lalu jalankan setup kembali.' }
Write-Host 'Setup selesai dan konfigurasi AI siap. Jalankan .\start.ps1 untuk membuka SIRA.'
Write-Host 'Opsional: .\scripts\setup-ocr.ps1 hanya diperlukan jika akan meng-upload PDF hasil scan.'
