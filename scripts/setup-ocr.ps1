$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskTarget = Join-Path $taskRoot 'tools\tesseract'
$taskBinary = Join-Path $taskTarget 'tesseract.exe'
New-Item -ItemType Directory -Force -Path 'tmp\install' | Out-Null
$taskInstaller = Join-Path $taskRoot 'tmp\install\tesseract-setup.exe'
if (-not (Test-Path -LiteralPath $taskBinary)) {
    if (Test-Path -LiteralPath $taskTarget) { throw 'Folder target OCR sudah ada tetapi executable tidak ditemukan. Periksa manual; skrip tidak menghapus atau menimpa folder tersebut.' }
    $taskUrl = 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
    Invoke-WebRequest -Uri $taskUrl -OutFile $taskInstaller
    $taskExpected = 'bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4'
    if ((Get-FileHash -LiteralPath $taskInstaller -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected) { throw 'Hash installer tidak cocok; instalasi dihentikan.' }
    $taskProcess = Start-Process -FilePath $taskInstaller -ArgumentList @('/S','/CURRENTUSER',('/D='+$taskTarget)) -WindowStyle Hidden -Wait -PassThru
    if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskBinary)) { throw 'Instalasi OCR belum berhasil. Gunakan petunjuk manual pada README.' }
}
$taskModels = @{
    ind = '1f6596041ffb4cd5094e5f98764db43cfde04edb8f02b988f90ebc1353ac73b8'
    eng = '8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba'
}
foreach ($taskLanguage in $taskModels.Keys) {
    $taskModel = Join-Path $taskTarget ('tessdata\'+$taskLanguage+'.traineddata')
    if (-not (Test-Path -LiteralPath $taskModel) -or (Get-FileHash -LiteralPath $taskModel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskModels[$taskLanguage]) {
        Invoke-WebRequest -Uri ('https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/4.1.0/'+$taskLanguage+'.traineddata') -OutFile $taskModel
        if ((Get-FileHash -LiteralPath $taskModel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskModels[$taskLanguage]) { throw ('Hash model '+$taskLanguage+' tidak cocok.') }
    }
}
& $taskBinary --list-langs
if ($LASTEXITCODE -ne 0) { throw 'OCR belum siap.' }
Write-Host 'OCR siap. Engine ini terdeteksi otomatis oleh SIRA. tools/ tidak masuk Git.'
