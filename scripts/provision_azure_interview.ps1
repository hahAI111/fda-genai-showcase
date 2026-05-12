$ErrorActionPreference = 'Stop'

$subscriptionId = '54eea1c8-6bc5-44b1-9cc5-3e803abfb033'
$resourceGroup = 'gpt'
$location = 'eastus'
$openAiResource = 'jingw0129-5070-resource'
$searchService = 'jingw01295070-search'
$storageAccount = 'jingw01295070store'
$containerName = 'enterprise-docs'
$imageDeployment = 'gpt-image-2'
$imageModelVersion = '2026-04-21'
$videoDeployment = 'sora-2'
$videoModelVersion = '2025-10-06'

az account set --subscription $subscriptionId

az search service create --name $searchService --resource-group $resourceGroup --location $location --sku basic
az storage account create --name $storageAccount --resource-group $resourceGroup --location $location --sku Standard_LRS --kind StorageV2
az storage container create --account-name $storageAccount --name $containerName --auth-mode login
az cognitiveservices account deployment create --name $openAiResource --resource-group $resourceGroup --deployment-name $imageDeployment --model-name gpt-image-2 --model-version $imageModelVersion --model-format OpenAI --sku-name GlobalStandard --sku-capacity 2
az cognitiveservices account deployment create --name $openAiResource --resource-group $resourceGroup --deployment-name $videoDeployment --model-name sora-2 --model-version $videoModelVersion --model-format OpenAI --sku-name GlobalStandard --sku-capacity 1
az search admin-key show --service-name $searchService --resource-group $resourceGroup
