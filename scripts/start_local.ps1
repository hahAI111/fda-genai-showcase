param(
    [int]$PreferredPort = 8000,
    [int]$MaxPort = 8010,
    [string]$Host = "127.0.0.1",
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PortOwner {
    param([int]$Port)
    return Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$selectedPort = $null

for ($port = $PreferredPort; $port -le $MaxPort; $port++) {
    $ownerPid = Get-PortOwner -Port $port

    if (-not $ownerPid) {
        $selectedPort = $port
        break
    }

    if ($port -eq $PreferredPort) {
        $ownerProcess = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        if ($ownerProcess -and $ownerProcess.ProcessName -match "python") {
            Write-Host "Port $port is used by Python process $ownerPid. Stopping it..."
            Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 800
            $ownerPid = Get-PortOwner -Port $port
            if (-not $ownerPid) {
                $selectedPort = $port
                break
            }
        }
    }
}

if (-not $selectedPort) {
    throw "No free port found in range $PreferredPort-$MaxPort"
}

Write-Host "Starting app on http://$Host:$selectedPort"
Write-Host "Command: $PythonExe -m uvicorn src.main:app --host $Host --port $selectedPort"

& $PythonExe -m uvicorn src.main:app --host $Host --port $selectedPort
