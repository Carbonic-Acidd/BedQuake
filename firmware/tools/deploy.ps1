# Copies everything in firmware/src/ to the Pico's root filesystem using mpremote.
# Usage (from anywhere): powershell -ExecutionPolicy Bypass -File firmware\tools\deploy.ps1

$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot '..\src' | Resolve-Path
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

Write-Host "Deploy complete"
