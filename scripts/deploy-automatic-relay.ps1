param([switch]$Disable, [int]$Days = 0)
$ErrorActionPreference = 'Stop'
$siraRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $siraRoot
if ($Days -lt 0 -or $Days -gt 30) { throw 'Days harus 0 (pertahankan masa akses) atau 1-30.' }
$siraNode = (Get-Command node -ErrorAction Stop).Source
$siraWrangler = Join-Path $siraRoot 'worker\node_modules\wrangler\bin\wrangler.js'
if (-not (Test-Path -LiteralPath $siraWrangler)) { throw 'Pasang dependensi worker terlebih dahulu: cd worker; npm ci' }
New-Item -ItemType Directory -Force -Path 'tmp','data' | Out-Null
$env:WRANGLER_SEND_METRICS = 'false'
$env:WRANGLER_LOG_PATH = Join-Path $siraRoot 'tmp\wrangler-automatic-install.log'
$siraDeploymentsPath = Join-Path $siraRoot 'tmp\automatic-install-deployments.json'
$siraVersionPath = Join-Path $siraRoot 'tmp\automatic-install-version.json'
Push-Location -LiteralPath 'worker'
try {
    & $siraNode $siraWrangler deployments list --json | Set-Content -LiteralPath $siraDeploymentsPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'Pembacaan deployment Cloudflare gagal; belum ada perubahan.' }
    $siraDeployment = Get-Content -LiteralPath $siraDeploymentsPath -Raw | ConvertFrom-Json | Select-Object -Last 1
    if (@($siraDeployment.versions).Count -ne 1) { throw 'Deployment bertahap perlu ditinjau manual; skrip tidak menggantinya.' }
    & $siraNode $siraWrangler versions view ($siraDeployment.versions[0].version_id) --json | Set-Content -LiteralPath $siraVersionPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'Pembacaan konfigurasi aktif gagal; belum ada perubahan.' }
    $siraVersion = Get-Content -LiteralPath $siraVersionPath -Raw | ConvertFrom-Json
    $siraVars = [ordered]@{}
    foreach ($siraBinding in $siraVersion.resources.bindings) {
        if ($siraBinding.type -eq 'plain_text') {
            # PowerShell 7 may deserialize ISO JSON strings into DateTime.
            $siraVars[$siraBinding.name] = if ($siraBinding.text -is [DateTime]) {
                $siraBinding.text.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            } else { [string]$siraBinding.text }
        }
    }
    if ($siraVars['RELAY_ENABLED'] -ne 'true') { throw 'Relay utama belum aktif. Selesaikan konfigurasi pemilik terlebih dahulu.' }
    if ($Days -gt 0) { $siraVars['RELAY_EXPIRES_AT'] = [DateTime]::UtcNow.AddDays($Days).ToString('yyyy-MM-ddTHH:mm:ssZ') }
    if (-not $Disable -and [DateTimeOffset]::Parse($siraVars['RELAY_EXPIRES_AT']) -le [DateTimeOffset]::UtcNow) {
        throw 'Masa akses sudah berakhir. Gunakan -Days untuk menentukan masa pengujian baru.'
    }
    $siraVars['INSTALLATION_ACCESS_ENABLED'] = if ($Disable) { 'false' } else { 'true' }
    if (-not $Disable) {
        Write-Host 'Akses demo instalasi akan tersedia publik selama masa pengujian, dengan aturan relay yang sama.'
        $siraTokenPath = Join-Path $siraRoot 'data\installation-token.txt'
        if (-not (Test-Path -LiteralPath $siraTokenPath)) {
            $siraBytes = New-Object byte[] 32
            $siraRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
            try { $siraRandom.GetBytes($siraBytes) } finally { $siraRandom.Dispose() }
            [IO.File]::WriteAllText($siraTokenPath, [Convert]::ToBase64String($siraBytes).TrimEnd('=').Replace('+','-').Replace('/','_'))
        }
        $siraDemoToken = (Get-Content -LiteralPath $siraTokenPath -Raw).Trim()
        if ($siraDemoToken -notmatch '^[A-Za-z0-9_-]{40,100}$') { throw 'Token demo lokal tidak valid.' }
        $siraDemoToken | & $siraNode $siraWrangler secret put INSTALLATION_TOKEN
        if ($LASTEXITCODE -ne 0) { throw 'Pemasangan token demo gagal. Tidak ada key OpenAI yang diubah.' }
        $siraDemoToken = $null
    }
    # Preserve every active non-secret binding, including expiry and quota policy.
    # Secrets remain on Cloudflare; the owner's private token is never read/uploaded.
    $siraConfigLines = Get-Content -LiteralPath 'wrangler.toml'
    $siraRelease = [Collections.Generic.List[string]]::new()
    $siraInVars = $false
    foreach ($siraLine in $siraConfigLines) {
        if ($siraLine.Trim() -eq '[vars]') {
            $siraRelease.Add('[vars]')
            foreach ($siraName in $siraVars.Keys) {
                if ($siraName -notmatch '^[A-Z_]+$') { throw 'Nama variabel relay tidak valid.' }
                $siraEncoded = $siraVars[$siraName] | ConvertTo-Json -Compress
                $siraRelease.Add($siraName + ' = ' + $siraEncoded)
            }
            $siraRelease.Add('')
            $siraInVars = $true
            continue
        }
        if ($siraInVars -and $siraLine.Trim().StartsWith('[')) { $siraInVars = $false }
        if (-not $siraInVars) { $siraRelease.Add($siraLine) }
    }
    $siraReleasePath = Join-Path $siraRoot 'worker\.wrangler-auto-install.toml'
    [IO.File]::WriteAllLines($siraReleasePath, $siraRelease, [Text.UTF8Encoding]::new($false))
    & $siraNode $siraWrangler deploy --config $siraReleasePath
    if ($LASTEXITCODE -ne 0) { throw 'Deployment belum berhasil. Periksa status Cloudflare sebelum mengulang.' }
    Write-Host ('Instalasi otomatis: ' + $siraVars['INSTALLATION_ACCESS_ENABLED'])
    Write-Host ('Masa akses UTC: ' + $siraVars['RELAY_EXPIRES_AT'])
} finally { Pop-Location }
