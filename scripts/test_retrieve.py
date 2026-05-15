"""Test Agentic Retrieval Retrieve API."""
import os
import requests, json

ENDPOINT = "https://jingw01295070-search.search.windows.net"
API_KEY = os.environ["AZURE_SEARCH_API_KEY"]
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}

url = f"{ENDPOINT}/knowledgebases('kb-enterprise')/retrieve?api-version=2026-04-01"

body = {
    "maxRuntimeInSeconds": 60,
    "maxOutputSizeInTokens": 50000,
    "includeActivity": True,
    "knowledgeSourceParams": [
        {
            "knowledgeSourceName": "ks-enterprise-index",
            "includeReferences": True,
            "includeReferenceSourceData": True,
            "kind": "searchIndex",
        }
    ],
    "intents": [
        {"search": "What is the data retention policy?", "type": "semantic"}
    ],
}

r = requests.post(url, headers=HEADERS, json=body, timeout=60)
print(f"Status: {r.status_code}")
data = r.json()

# Print response content
for msg in data.get("response", []):
    for c in msg.get("content", []):
        if c.get("type") == "text":
            text = c["text"]
            print(f"Response text ({len(text)} chars):")
            print(text[:500])
            print("...")

# Print activity
activities = data.get("activity", [])
print(f"\nActivity ({len(activities)} records):")
for a in activities:
    atype = a.get("type")
    aid = a.get("id", "?")
    if atype == "searchIndex":
        args = a.get("searchIndexArguments", {})
        search_text = args.get("search", "")
        count = a.get("count", 0)
        ms = a.get("elapsedMs", 0)
        print(f"  [{aid}] {atype}: search={search_text!r} count={count} {ms}ms")
    elif atype == "modelQueryPlanning":
        print(f"  [{aid}] {atype}: in={a.get('inputTokens',0)} out={a.get('outputTokens',0)} {a.get('elapsedMs',0)}ms")
    elif atype == "agenticReasoning":
        print(f"  [{aid}] {atype}: tokens={a.get('reasoningTokens',0)}")
    elif atype == "modelAnswerSynthesis":
        print(f"  [{aid}] {atype}: in={a.get('inputTokens',0)} out={a.get('outputTokens',0)} {a.get('elapsedMs',0)}ms")
    else:
        print(f"  [{aid}] {atype}")

# Print references
refs = data.get("references", [])
print(f"\nReferences ({len(refs)}):")
for ref in refs[:5]:
    sd = ref.get("sourceData", {})
    title = sd.get("title", "")
    score = ref.get("rerankerScore", 0)
    rtype = ref.get("type", "")
    rid = ref.get("id", "")
    print(f"  [{rid}] {rtype} score={score} title={title!r}")
