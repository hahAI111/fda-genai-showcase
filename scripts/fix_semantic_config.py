"""Fix semantic configuration on enterprise-knowledge index."""
import os
import requests, json

endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://jingw01295070-search.search.windows.net")
api_key = os.environ["AZURE_SEARCH_API_KEY"]
headers = {"api-key": api_key, "Content-Type": "application/json"}

# Step 1: Get current index definition
r = requests.get(f"{endpoint}/indexes/enterprise-knowledge?api-version=2024-07-01", headers=headers, timeout=15)
data = r.json()

print("Current semantic config:")
print(json.dumps(data.get("semantic", {}), indent=2))
print()
print("Fields:")
for f in data.get("fields", []):
    name = f["name"]
    ftype = f["type"]
    searchable = f.get("searchable", False)
    print(f"  {name:20} {ftype:30} searchable={searchable}")

# Step 2: Fix semantic configuration with proper fields
data["semantic"] = {
    "defaultConfiguration": "enterprise-semantic-config",
    "configurations": [
        {
            "name": "enterprise-semantic-config",
            "prioritizedFields": {
                "titleField": {"fieldName": "title"},
                "contentFields": [
                    {"fieldName": "content"}
                ],
                "keywordsFields": [
                    {"fieldName": "category"}
                ]
            }
        }
    ]
}

# Remove read-only fields
for key in ["@odata.context", "@odata.etag"]:
    data.pop(key, None)

print("\nUpdating index with proper semantic config...")
r2 = requests.put(
    f"{endpoint}/indexes/enterprise-knowledge?api-version=2024-07-01",
    headers=headers,
    json=data,
    timeout=30
)
print(f"Update status: {r2.status_code}")
if r2.status_code in (200, 204):
    print("SUCCESS: Semantic configuration updated!")
    # Verify
    r3 = requests.get(f"{endpoint}/indexes/enterprise-knowledge?api-version=2024-07-01", headers=headers, timeout=15)
    new_semantic = r3.json().get("semantic", {})
    print(f"Default config: {new_semantic.get('defaultConfiguration')}")
    configs = new_semantic.get("configurations", [])
    for cfg in configs:
        pf = cfg.get("prioritizedFields", {})
        title = pf.get("titleField", {}).get("fieldName", "")
        content = [f.get("fieldName", "") for f in pf.get("contentFields", [])]
        keywords = [f.get("fieldName", "") for f in pf.get("keywordsFields", [])]
        print(f"  Config: {cfg['name']}")
        print(f"    titleField: {title}")
        print(f"    contentFields: {content}")
        print(f"    keywordsFields: {keywords}")
else:
    print(f"ERROR: {r2.text[:500]}")
