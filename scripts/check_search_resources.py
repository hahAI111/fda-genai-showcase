"""Check all indexers, indexes, datasources on the search service."""
import os
import requests, json

ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://jingw01295070-search.search.windows.net")
API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}

# Indexers
r = requests.get(f"{ENDPOINT}/indexers?api-version=2024-07-01", headers=HEADERS, timeout=15)
print("=== Indexers ===")
for idx in r.json().get("value", []):
    print(f"  {idx['name']}")
    print(f"    targetIndex: {idx.get('targetIndexName', '')}")
    print(f"    dataSource:  {idx.get('dataSourceName', '')}")
    print(f"    skillset:    {idx.get('skillsetName', '')}")
    print()

# Indexes
r2 = requests.get(f"{ENDPOINT}/indexes?api-version=2024-07-01", headers=HEADERS, timeout=15)
print("=== Indexes ===")
for idx in r2.json().get("value", []):
    name = idx.get("name", "")
    fields = [f["name"] for f in idx.get("fields", [])]
    print(f"  {name}: {len(fields)} fields = {fields}")
    print()

# Data sources
r3 = requests.get(f"{ENDPOINT}/datasources?api-version=2024-07-01", headers=HEADERS, timeout=15)
print("=== Data sources ===")
for ds in r3.json().get("value", []):
    container = ds.get("container", {}).get("name", "")
    print(f"  {ds['name']} -> type={ds.get('type','')} container={container}")

# Skillsets
r4 = requests.get(f"{ENDPOINT}/skillsets?api-version=2024-07-01", headers=HEADERS, timeout=15)
print("\n=== Skillsets ===")
for ss in r4.json().get("value", []):
    skills = [s.get("@odata.type", "").split(".")[-1] for s in ss.get("skills", [])]
    print(f"  {ss['name']}: {skills}")
