param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$WebAppName,

    [int]$IdleMinutes = 90,
    [int]$WindowMinutes = 30,
    [string]$SkipDays = "20"
)

$today = (Get-Date).Day
$skipSet = $SkipDays.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
if ($skipSet -contains "$today") {
    Write-Host "Skip day hit ($today). Keep app running for demo window."
    exit 0
}

$app = az webapp show --resource-group $ResourceGroup --name $WebAppName --query "{id:id,state:state}" -o json | ConvertFrom-Json
if ($app.state -eq "Stopped") {
    Write-Host "App already stopped."
    exit 0
}

$startTime = (Get-Date).AddMinutes(-1 * $WindowMinutes).ToUniversalTime().ToString("o")
$endTime = (Get-Date).ToUniversalTime().ToString("o")

$totalRequests = az monitor metrics list --resource $app.id --metric Requests --interval "PT${WindowMinutes}M" --aggregation Total --start-time $startTime --end-time $endTime --query "value[0].timeseries[0].data[].total" -o tsv |
    ForEach-Object { if ($_ -ne "") { [double]$_ } } |
    Measure-Object -Sum |
    Select-Object -ExpandProperty Sum

if (-not $totalRequests) {
    $totalRequests = 0
}

if ($totalRequests -eq 0) {
    Write-Host "No requests in last ${WindowMinutes}m. Stopping app to save cost..."
    az webapp stop --resource-group $ResourceGroup --name $WebAppName | Out-Null
    Write-Host "Stopped."
} else {
    Write-Host "Requests detected ($totalRequests). Keep running."
}
