param([int]$Days = 8)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if ($Days -lt 1 -or $Days -gt 30) { throw 'Masa akses uji harus 1-30 hari.' }
$taskNode = (Get-Command node -ErrorAction Stop).Source
$taskWrangler = Join-Path $taskRoot 'worker\node_modules\wrangler\bin\wrangler.js'
$env:WRANGLER_SEND_METRICS = 'false'
$env:WRANGLER_LOG_PATH = Join-Path $taskRoot 'tmp\wrangler-configure.log'
New-Item -ItemType Directory -Force -Path 'tmp','data' | Out-Null
if (-not (Test-Path -LiteralPath $taskWrangler)) {
    Push-Location -LiteralPath 'worker'
    try { & npm.cmd ci --no-fund --no-audit; if ($LASTEXITCODE -ne 0) { throw 'Instalasi Worker gagal.' } }
    finally { Pop-Location }
}
$taskConfig = Join-Path $taskRoot 'worker\wrangler.toml'
$taskExpiry = [DateTime]::UtcNow.AddDays($Days).ToString('yyyy-MM-ddTHH:mm:ssZ')
$taskRelease = Get-Content -LiteralPath $taskConfig -Raw
# First publish with access disabled, even when this script is rerun.
$taskRelease = $taskRelease -replace 'RELAY_ENABLED = "(?:true|false)"', 'RELAY_ENABLED = "false"'
$taskRelease = $taskRelease -replace 'RELAY_EXPIRES_AT = "[^"]+"', ('RELAY_EXPIRES_AT = "'+$taskExpiry+'"')
Set-Content -LiteralPath $taskConfig -Value $taskRelease -Encoding utf8
Write-Host 'Skrip ini mempublikasikan relay sira-relay ke akun Cloudflare CLI Anda.'
Write-Host 'Batas awal: 1000 request, 2 juta unit reservasi, 30 request/menit. Lihat docs/relay-setup.md.'
Write-Host 'Jika belum login, jalankan: cd worker; npx wrangler login'
$taskSecret = Read-Host 'Masukkan API key OpenAI (input disembunyikan)' -AsSecureString
$taskPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecret)
$taskTokenPath = Join-Path $taskRoot 'data\relay-token.txt'
try {
    $taskPlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPtr)
    if ($taskPlainKey.Length -lt 20 -or -not $taskPlainKey.StartsWith('sk-')) { throw 'Format API key tidak sesuai.' }
    if (-not (Test-Path -LiteralPath $taskTokenPath)) {
        $taskBytes = New-Object byte[] 32
        $taskRng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $taskRng.GetBytes($taskBytes) } finally { $taskRng.Dispose() }
        $taskToken = [Convert]::ToBase64String($taskBytes).TrimEnd('=').Replace('+','-').Replace('/','_')
        [IO.File]::WriteAllText($taskTokenPath, $taskToken)
    } else { $taskToken = (Get-Content -LiteralPath $taskTokenPath -Raw).Trim() }
    if ($taskToken -notmatch '^[A-Za-z0-9_-]{40,100}$') { throw 'Token relay lokal tidak valid. Periksa data/relay-token.txt; akses belum diaktifkan.' }
    $taskSha = [Security.Cryptography.SHA256]::Create()
    try { $taskHash = ([BitConverter]::ToString($taskSha.ComputeHash([Text.Encoding]::UTF8.GetBytes($taskToken)))).Replace('-','').ToLowerInvariant() }
    finally { $taskSha.Dispose() }
    Push-Location -LiteralPath 'worker'
    try {
        & $taskNode $taskWrangler deploy
        if ($LASTEXITCODE -ne 0) { throw 'Deployment awal gagal; relay belum diaktifkan.' }
        $taskPlainKey | & $taskNode $taskWrangler secret put OPENAI_API_KEY
        if ($LASTEXITCODE -ne 0) { throw 'Penyimpanan API key ke Secrets gagal.' }
        $taskHash | & $taskNode $taskWrangler secret put RELAY_TOKEN_HASH
        if ($LASTEXITCODE -ne 0) { throw 'Penyimpanan hash akses uji gagal.' }
        $taskRelease = $taskRelease -replace 'RELAY_ENABLED = "false"', 'RELAY_ENABLED = "true"'
        Set-Content -LiteralPath $taskConfig -Value $taskRelease -Encoding utf8
        & $taskNode $taskWrangler deploy
        if ($LASTEXITCODE -ne 0) { throw 'Aktivasi relay gagal. Periksa status melalui Cloudflare Dashboard.' }
    } finally { Pop-Location }
    $taskUrl = (Read-Host 'Tempel URL https://sira-relay....workers.dev yang ditampilkan Wrangler').Trim().TrimEnd('/')
    $taskParsed = $null
    if (-not [Uri]::TryCreate($taskUrl,[UriKind]::Absolute,[ref]$taskParsed) -or $taskParsed.Scheme -ne 'https' -or $taskParsed.Host -notlike '*.workers.dev' -or $taskParsed.AbsolutePath -ne '/' -or $taskParsed.UserInfo -or $taskParsed.Query -or $taskParsed.Fragment) { throw 'URL Worker tidak sesuai. Konfigurasi .env dapat dilengkapi manual.' }
    $taskEnvPath = Join-Path $taskRoot '.env'
    $taskEnv = if (Test-Path -LiteralPath $taskEnvPath) { Get-Content -LiteralPath $taskEnvPath -Raw } else { Get-Content -LiteralPath (Join-Path $taskRoot '.env.example') -Raw }
    foreach ($taskSetting in @{SIRA_RELAY_URL=$taskUrl;SIRA_RELAY_TOKEN=$taskToken}.GetEnumerator()) {
        $taskPattern = '(?m)^'+$taskSetting.Key+'=.*$'
        $taskLine = $taskSetting.Key+'='+$taskSetting.Value
        if ($taskEnv -match $taskPattern) { $taskEnv = [regex]::Replace($taskEnv,$taskPattern,$taskLine) }
        else { $taskEnv += "`n"+$taskLine }
    }
    [IO.File]::WriteAllText($taskEnvPath,$taskEnv,[Text.UTF8Encoding]::new($false))
    Write-Host 'Konfigurasi tersimpan pada .env lokal. API key OpenAI hanya disimpan pada Cloudflare Secrets.'
    Write-Host 'Restart SIRA, login admin, lalu gunakan Uji koneksi AI. Jangan bagikan .env atau data/.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPtr)
    $taskPlainKey = $null
    $taskSecret.Dispose()
}
