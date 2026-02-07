$certPath = "D:\Lawrence\antigravity\Futures-Trading\certs\Sinopac.pfx"
if (-not (Test-Path $certPath)) {
    Write-Host "Certificate file not found at $certPath" -ForegroundColor Red
    exit 1
}

$bytes = [System.IO.File]::ReadAllBytes($certPath)
$base64 = [System.Convert]::ToBase64String($bytes)

Write-Host "Run this command in your Zeabur terminal:" -ForegroundColor Cyan
Write-Host "mkdir -p /app/certs && echo '$base64' | base64 -d > /app/certs/Sinopac.pfx" -ForegroundColor Green
