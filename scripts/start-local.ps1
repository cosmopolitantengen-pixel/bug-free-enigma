param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000,
    [switch]$EnableComputerControl
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root "data"
$databasePath = Join-Path $dataDir "company_os.db"
$backendDir = Join-Path $root "backend"
$webDir = Join-Path $root "apps\web"

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$env:AI_COMPANY_OS_SQLITE_PATH = $databasePath
$env:NEXT_PUBLIC_API_BASE = "http://127.0.0.1:$ApiPort"
if ($EnableComputerControl) {
    $env:AI_COMPANY_OS_ENABLE_COMPUTER_CONTROL = "1"
}

function Test-Endpoint([string]$Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

$apiAlreadyRunning = Test-Endpoint "http://127.0.0.1:$ApiPort/health"
if ($apiAlreadyRunning) {
    $schema = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/database/schema" -TimeoutSec 2
    if ($schema.backend -eq "memory") {
        throw "Port $ApiPort is running an in-memory API. Stop it, then run this script again to enable SQLite persistence."
    }
}

if (-not $apiAlreadyRunning) {
    $python = (Get-Command python -ErrorAction Stop).Source
    $api = Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput (Join-Path $dataDir "runtime-api.out.log") `
        -RedirectStandardError (Join-Path $dataDir "runtime-api.err.log") `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Path (Join-Path $dataDir "runtime-api.pid") -Value $api.Id
}

if (-not (Test-Endpoint "http://127.0.0.1:$WebPort")) {
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $web = Start-Process -FilePath $npm `
        -ArgumentList "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$WebPort" `
        -WorkingDirectory $webDir `
        -RedirectStandardOutput (Join-Path $dataDir "runtime-web.out.log") `
        -RedirectStandardError (Join-Path $dataDir "runtime-web.err.log") `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Path (Join-Path $dataDir "runtime-web.pid") -Value $web.Id
}

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-Endpoint "http://127.0.0.1:$ApiPort/health") -and (Test-Endpoint "http://127.0.0.1:$WebPort")) {
        Write-Output "AI Company OS is ready: http://127.0.0.1:$WebPort"
        Write-Output "SQLite state: $databasePath"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "AI Company OS did not become ready. Check data/runtime-api.err.log and data/runtime-web.err.log."
