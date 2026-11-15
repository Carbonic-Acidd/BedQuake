# Copies everything in firmware/src/ to the Pico's root filesystem, plus
# firmware/.env as /.env, using mpremote.
# Usage (from anywhere): powershell -ExecutionPolicy Bypass -File firmware\tools\deploy.ps1

$ErrorActionPreference = 'Stop'

$firmware = Join-Path $PSScriptRoot '..' | Resolve-Path
$src = Join-Path $firmware 'src'
$envFile = Join-Path $firmware '.env'

# Check for secrets before touching the Pico.
if (-not (Test-Path $envFile)) {
    Write-Host "firmware/.env not found. Copy firmware/.env.example to firmware/.env,"
    Write-Host "fill in your Wi-Fi and MQTT values, then run this script again."
    exit 1
}

Write-Host "Deploying from $src to Pico root"

Get-ChildItem -Path $src | Where-Object { $_.Name -ne '__pycache__' } | ForEach-Object {
    if ($_.PSIsContainer) {
        Write-Host "Copying folder $($_.Name)/ -> :$($_.Name)/"
        & mpremote fs cp -r $_.FullName :
    } else {
        Write-Host "Copying file $($_.Name) -> :$($_.Name)"
        & mpremote fs cp $_.FullName ":$($_.Name)"
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed copying $($_.Name) (mpremote exit code $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

Write-Host "Copying secrets firmware/.env -> :.env"
& mpremote fs cp $envFile :.env
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed copying .env (mpremote exit code $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "Deploy complete"
