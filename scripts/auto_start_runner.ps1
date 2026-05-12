param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$WebAppName,

    [string]$RunDays = "20"
)

$today = (Get-Date).Day
$allowed = $RunDays.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
if (-not ($allowed -contains "$today")) {
    Write-Host "Today ($today) not in RunDays=$RunDays, skip start."
    exit 0
}

$appState = az webapp show --resource-group $ResourceGroup --name $WebAppName --query state -o tsv
if ($appState -eq "Running") {
    Write-Host "App already running."
    exit 0
}

Write-Host "Starting app for demo day..."
az webapp start --resource-group $ResourceGroup --name $WebAppName | Out-Null
Write-Host "Started."
