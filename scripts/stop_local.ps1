param(
    [int]$StartPort = 8000,
    [int]$EndPort = 8010
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$found = $false
for ($port = $StartPort; $port -le $EndPort; $port++) {
    $owners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $owners) {
        continue
    }

    foreach ($owner in $owners) {
        $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping PID $owner ($($proc.ProcessName)) on port $port"
            Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }
}

if (-not $found) {
    Write-Host "No running process found on ports $StartPort-$EndPort"
} else {
    Write-Host "Done."
}
