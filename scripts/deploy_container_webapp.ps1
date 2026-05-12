param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$WebAppName,

    [Parameter(Mandatory = $true)]
    [string]$AcrName,

    [string]$ImageName = "enterprise-genai-content-studio",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv
if (-not $acrLoginServer) {
    throw "Failed to resolve ACR login server for $AcrName"
}

$imageRef = "$acrLoginServer/$ImageName`:$ImageTag"
Write-Host "Updating web app container to: $imageRef"

az webapp config container set `
    --resource-group $ResourceGroup `
    --name $WebAppName `
    --container-image-name $imageRef | Out-Null

Write-Host "Restarting app..."
az webapp restart --resource-group $ResourceGroup --name $WebAppName | Out-Null

Write-Host "Checking app state..."
az webapp show `
    --resource-group $ResourceGroup `
    --name $WebAppName `
    --query "{state:state, defaultHostName:defaultHostName, linuxFxVersion:siteConfig.linuxFxVersion}" `
    -o table
