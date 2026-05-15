"""Setup Agentic Retrieval resources on Azure AI Search.

Creates Knowledge Sources and Knowledge Base on jingw01295070-search
using api-version 2026-04-01.
"""

import json
import os
import requests
import sys

SEARCH_ENDPOINT = "https://jingw01295070-search.search.windows.net"
SEARCH_API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
AI_ENDPOINT = "https://jingw0129-5070-resource.cognitiveservices.azure.com/"
AI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
STORAGE_CONN_STR = os.environ["AZURE_STORAGE_CONN_STR"]

API_VERSION = "2026-04-01"
HEADERS = {"api-key": SEARCH_API_KEY, "Content-Type": "application/json"}


def api(method, path, body=None):
    url = f"{SEARCH_ENDPOINT}/{path}?api-version={API_VERSION}"
    r = getattr(requests, method)(url, headers=HEADERS, json=body, timeout=30)
    return r.status_code, r.json() if r.text else {}


def step(label):
    print(f"\n{'='*60}\n{label}\n{'='*60}")


# ── Step 0: Check index semantic config ──────────────────────
step("Step 0: Check index semantic configuration")
code, data = api("get", "indexes/enterprise-knowledge")
if code == 200:
    semantic = data.get("semantic", {})
    default_cfg = semantic.get("defaultConfiguration")
    configs = semantic.get("configurations", [])
    print(f"  Default semantic config: {default_cfg}")
    for cfg in configs:
        print(f"  Config: {cfg.get('name')} | fields: {[f.get('fieldName','') for f in cfg.get('prioritizedFields',{}).get('contentFields',[])]}")
    
    # If no default, set one
    if not default_cfg and configs:
        cfg_name = configs[0]["name"]
        print(f"\n  Setting default semantic config to: {cfg_name}")
        semantic["defaultConfiguration"] = cfg_name
        data["semantic"] = semantic
        # Remove read-only fields
        for key in ["@odata.context", "@odata.etag"]:
            data.pop(key, None)
        code2, data2 = api("put", "indexes/enterprise-knowledge", data)
        print(f"  Update result: {code2}")
        if code2 != 200:
            print(f"  Error: {json.dumps(data2, indent=2)[:300]}")
    elif not default_cfg and not configs:
        print("  ERROR: No semantic configurations exist on this index!")
        print("  Need to create one first.")
        sys.exit(1)
else:
    print(f"  ERROR getting index: {code}")
    print(json.dumps(data, indent=2)[:300])
    sys.exit(1)


# ── Step 1: List existing Knowledge Sources ──────────────────
step("Step 1: List existing Knowledge Sources")
code, data = api("get", "knowledgesources")
print(f"  Status: {code}")
existing_ks = []
for ks in data.get("value", []):
    name = ks.get("name", "")
    kind = ks.get("kind", "")
    print(f"  Found: {name} ({kind})")
    existing_ks.append(name)


# ── Step 2: Create Search Index Knowledge Source ─────────────
step("Step 2: Create Search Index Knowledge Source")
ks_index_name = "ks-enterprise-index"
if ks_index_name in existing_ks:
    print(f"  Already exists: {ks_index_name}")
else:
    body = {
        "name": ks_index_name,
        "kind": "searchIndex",
        "description": "Enterprise knowledge index - 68 docs, hybrid vector+semantic",
        "searchIndexParameters": {
            "searchIndexName": "enterprise-knowledge",
        }
    }
    code, data = api("post", "knowledgesources", body)
    print(f"  Create result: {code}")
    if code not in (200, 201):
        print(f"  Error: {json.dumps(data, indent=2)[:300]}")


# ── Step 3: Create Blob Storage Knowledge Source ─────────────
step("Step 3: Create Blob Storage Knowledge Source")
ks_blob_name = "ks-enterprise-docs"
if ks_blob_name in existing_ks:
    print(f"  Already exists: {ks_blob_name}")
else:
    body = {
        "name": ks_blob_name,
        "kind": "azureBlob",
        "description": "Enterprise docs from Blob Storage - 14 markdown files",
        "azureBlobParameters": {
            "connectionString": STORAGE_CONN_STR,
            "containerName": "enterprise-docs",
            "ingestionParameters": {
                "embeddingModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": AI_ENDPOINT,
                        "deploymentId": "text-embedding-3-large",
                        "apiKey": AI_API_KEY,
                        "modelName": "text-embedding-3-large"
                    }
                },
                "chatCompletionModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": AI_ENDPOINT,
                        "deploymentId": "gpt-5.2",
                        "apiKey": AI_API_KEY,
                        "modelName": "gpt-5"
                    }
                }
            }
        }
    }
    code, data = api("post", "knowledgesources", body)
    print(f"  Create result: {code}")
    if code in (200, 201):
        created = data.get("azureBlobParameters", {}).get("createdResources", {})
        print(f"  Created resources: {json.dumps(created, indent=2)}")
    else:
        print(f"  Error: {json.dumps(data, indent=2)[:500]}")


# ── Step 4: List Knowledge Sources after creation ────────────
step("Step 4: Verify Knowledge Sources")
code, data = api("get", "knowledgesources")
for ks in data.get("value", []):
    print(f"  {ks.get('name')} | {ks.get('kind')} | {ks.get('description','')[:60]}")


# ── Step 5: List existing Knowledge Bases ────────────────────
step("Step 5: List existing Knowledge Bases")
code, data = api("get", "knowledgebases")
print(f"  Status: {code}")
existing_kb = []
for kb in data.get("value", []):
    name = kb.get("name", "")
    print(f"  Found: {name}")
    existing_kb.append(name)
if not existing_kb:
    print("  (none)")


# ── Step 6: Create Knowledge Base ────────────────────────────
step("Step 6: Create Knowledge Base")
kb_name = "kb-enterprise"
if kb_name in existing_kb:
    print(f"  Already exists: {kb_name}")
else:
    body = {
        "name": kb_name,
        "description": "Enterprise Knowledge Base - Agentic Retrieval with query planning",
        "knowledgeSources": [
            {"name": ks_index_name},
            {"name": ks_blob_name},
        ],
        "models": [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": AI_ENDPOINT,
                    "deploymentId": "gpt-5.2",
                    "apiKey": AI_API_KEY,
                    "modelName": "gpt-5"
                }
            }
        ]
    }
    code, data = api("post", "knowledgebases", body)
    print(f"  Create result: {code}")
    if code in (200, 201):
        print(f"  Knowledge Base created: {data.get('name')}")
    else:
        print(f"  Error: {json.dumps(data, indent=2)[:500]}")


# ── Step 7: Final verification ───────────────────────────────
step("Step 7: Final Verification")
code, data = api("get", "knowledgesources")
ks_count = len(data.get("value", []))
code2, data2 = api("get", "knowledgebases")
kb_count = len(data2.get("value", []))
print(f"  Knowledge Sources: {ks_count}")
print(f"  Knowledge Bases: {kb_count}")
print(f"\n  DONE!")
