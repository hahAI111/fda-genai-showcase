"""Fix Knowledge Source to properly reference the semantic config.

The index already has a valid semantic config named 'default' with:
- titleField: title
- prioritizedContentFields: [content]
- defaultConfiguration: default

The issue: ks-enterprise-index was created without specifying the
semantic config name. Need to delete and recreate with the right params.
"""
import os
import requests, json

ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://jingw01295070-search.search.windows.net")
API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
AI_ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "https://jingw0129-5070-resource.cognitiveservices.azure.com/")
AI_KEY = os.environ["AZURE_OPENAI_API_KEY"]
STORAGE_CONN = os.environ["AZURE_STORAGE_CONN_STR"]
API_VER = "2026-04-01"
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}


def api(method, path, body=None):
    url = f"{ENDPOINT}/{path}?api-version={API_VER}"
    r = getattr(requests, method)(url, headers=HEADERS, json=body, timeout=30)
    return r.status_code, r.json() if r.text else {}


def step(label):
    print(f"\n{'='*60}\n{label}\n{'='*60}")


# ── Step 1: Verify semantic config is correct ────────────────
step("Step 1: Verify index semantic config (via 2026-04-01)")
code, data = api("get", "indexes/enterprise-knowledge")
semantic = data.get("semantic", {})
default_cfg = semantic.get("defaultConfiguration")
print(f"  Default: {default_cfg}")
for cfg in semantic.get("configurations", []):
    print(f"  Config name: {cfg.get('name')}")
    pf = cfg.get("prioritizedFields", {})
    print(f"    titleField: {pf.get('titleField', {}).get('fieldName', 'NONE')}")
    content_fields = pf.get("prioritizedContentFields", pf.get("contentFields", []))
    print(f"    contentFields: {[f.get('fieldName','') for f in content_fields]}")


# ── Step 2: Delete old ks-enterprise-index ────────────────────
step("Step 2: Delete old Knowledge Source")
code, data = api("delete", "knowledgesources/ks-enterprise-index")
print(f"  Delete result: {code}")


# ── Step 3: Recreate with semanticConfigurationName ──────────
step("Step 3: Recreate Knowledge Source with semantic config")
body = {
    "name": "ks-enterprise-index",
    "kind": "searchIndex",
    "description": "Enterprise knowledge - 68 docs, hybrid vector+semantic search",
    "searchIndexParameters": {
        "searchIndexName": "enterprise-knowledge",
        "semanticConfigurationName": "default",
        "searchFields": [
            {"name": "title"},
            {"name": "content"}
        ],
        "sourceDataFields": [
            {"name": "source_url"},
            {"name": "category"}
        ]
    }
}
code, data = api("post", "knowledgesources", body)
print(f"  Create result: {code}")
if code in (200, 201):
    print(f"  SUCCESS! Name: {data.get('name')}")
    print(f"  Kind: {data.get('kind')}")
    params = data.get("searchIndexParameters", {})
    print(f"  Index: {params.get('searchIndexName')}")
    print(f"  Semantic config: {params.get('semanticConfigurationName')}")
else:
    print(f"  Error: {json.dumps(data, indent=2)[:500]}")


# ── Step 4: Create Knowledge Base ────────────────────────────
step("Step 4: Create Knowledge Base")
# First check if it exists
code, data = api("get", "knowledgebases")
existing_kb = [kb.get("name") for kb in data.get("value", [])]

kb_name = "kb-enterprise"
if kb_name in existing_kb:
    print(f"  Already exists: {kb_name}")
else:
    # Try different body structures for KB
    body = {
        "name": kb_name,
        "description": "Enterprise Knowledge Base - Agentic Retrieval",
        "knowledgeSources": ["ks-enterprise-index", "ks-enterprise-docs"],
        "models": {
            "queryPlannerModel": {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": AI_ENDPOINT,
                    "deploymentId": "gpt-4.1-mini",
                    "apiKey": AI_KEY,
                    "modelName": "gpt-5-mini"
                }
            }
        }
    }
    code, data = api("post", "knowledgebases", body)
    print(f"  Attempt 1 (models.queryPlannerModel): {code}")
    if code in (200, 201):
        print(f"  SUCCESS! KB created: {data.get('name')}")
    else:
        print(f"  Error: {json.dumps(data, indent=2)[:400]}")
        
        # Try alternative structure
        body2 = {
            "name": kb_name,
            "description": "Enterprise Knowledge Base - Agentic Retrieval",
            "knowledgeSources": ["ks-enterprise-index", "ks-enterprise-docs"],
            "queryPlannerModel": {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": AI_ENDPOINT,
                    "deploymentId": "gpt-4.1-mini",
                    "apiKey": AI_KEY,
                    "modelName": "gpt-5-mini"
                }
            }
        }
        code2, data2 = api("post", "knowledgebases", body2)
        print(f"\n  Attempt 2 (flat queryPlannerModel): {code2}")
        if code2 in (200, 201):
            print(f"  SUCCESS! KB created: {data2.get('name')}")
        else:
            print(f"  Error: {json.dumps(data2, indent=2)[:400]}")
            
            # Try minimal - just name and sources
            body3 = {
                "name": kb_name,
                "description": "Enterprise Knowledge Base",
                "knowledgeSources": ["ks-enterprise-index"]
            }
            code3, data3 = api("post", "knowledgebases", body3)
            print(f"\n  Attempt 3 (minimal): {code3}")
            if code3 in (200, 201):
                print(f"  SUCCESS! KB created: {data3.get('name')}")
            else:
                print(f"  Error: {json.dumps(data3, indent=2)[:400]}")


# ── Step 5: Final verification ───────────────────────────────
step("Step 5: Final Verification")
code, data = api("get", "knowledgesources")
print(f"Knowledge Sources ({len(data.get('value', []))}):")
for ks in data.get("value", []):
    print(f"  {ks.get('name')} | {ks.get('kind')}")

code2, data2 = api("get", "knowledgebases")
print(f"\nKnowledge Bases ({len(data2.get('value', []))}):")
for kb in data2.get("value", []):
    print(f"  {kb.get('name')}")
    print(f"  Sources: {kb.get('knowledgeSources', [])}")
