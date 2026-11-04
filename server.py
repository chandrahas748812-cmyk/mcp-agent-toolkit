"""MCP server over stdio speaking newline-delimited JSON-RPC 2.0.

Exposes:
  * 3 tools: doc-search (local sample corpus), time (UTC clock), memory
    (in-process key-value store).
  * 2 resources: sample documents served from data/sample_docs.json.
  * 1 prompt template: qa-with-citations.

Run:  python server.py   (reads requests on stdin, writes responses on stdout)
This is a portfolio/learning project. The sample corpus is invented
placeholder text; nothing here comes from any employer.
"""

import json
import os
import sys
from datetime import datetime, timezone

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_docs.json")


def load_docs():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["docs"]


DOCS = load_docs()
MEMORY = {}


def _tokenize(text):
    return [t.strip(".,!?;:\"'()[]") for t in text.lower().split() if t.strip()]


def tool_doc_search(args):
    query = args.get("query", "")
    top_k = int(args.get("top_k", 3))
    qtokens = set(_tokenize(query))
    scored = []
    for doc in DOCS:
        tokens = set(_tokenize(doc["title"] + " " + doc["text"]))
        score = len(qtokens & tokens)
        if score:
            idx = doc["text"].lower().find(next(iter(qtokens & tokens), ""))
            snippet = doc["text"][max(0, idx - 40):idx + 160] if idx >= 0 else doc["text"][:200]
            scored.append({"id": doc["id"], "title": doc["title"],
                           "score": score, "snippet": snippet})
    scored.sort(key=lambda r: -r["score"])
    return {"results": scored[:top_k]}


def tool_time(_args):
    return {"utc_now": datetime.now(timezone.utc).isoformat()}


def tool_memory(args):
    action = args.get("action")
    if action == "set":
        MEMORY[args["key"]] = args["value"]
        return {"ok": True, "key": args["key"]}
    if action == "get":
        key = args["key"]
        if key not in MEMORY:
            return {"ok": False, "error": "key not found: %s" % key}
        return {"ok": True, "key": key, "value": MEMORY[key]}
    if action == "list":
        return {"ok": True, "keys": sorted(MEMORY)}
    return {"ok": False, "error": "unknown action: %r" % (action,)}


TOOLS = {
    "doc-search": {
        "name": "doc-search",
        "description": "Search the local sample document corpus by keyword overlap.",
        "inputSchema": {"type": "object",
                        "properties": {"query": {"type": "string"},
                                       "top_k": {"type": "integer"}},
                        "required": ["query"]},
    },
    "time": {
        "name": "time",
        "description": "Return the current UTC time in ISO format.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "memory": {
        "name": "memory",
        "description": "In-process key-value store. Actions: set, get, list.",
        "inputSchema": {"type": "object",
                        "properties": {"action": {"type": "string"},
                                       "key": {"type": "string"},
                                       "value": {"type": "string"}},
                        "required": ["action"]},
    },
}

TOOL_HANDLERS = {"doc-search": tool_doc_search, "time": tool_time,
                 "memory": tool_memory}


def handle(request):
    method = request.get("method")
    params = request.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "mcp-agent-toolkit", "version": "0.1.0"}}
    if method == "tools/list":
        return {"tools": list(TOOLS.values())}
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOL_HANDLERS:
            raise ValueError("unknown tool: %s" % name)
        result = TOOL_HANDLERS[name](params.get("arguments") or {})
        return {"content": [{"type": "text", "text": json.dumps(result)}]}
    if method == "resources/list":
        return {"resources": [
            {"uri": "docs://%s" % d["id"], "name": d["title"],
             "mimeType": "text/plain"} for d in DOCS]}
    if method == "resources/read":
        uri = params.get("uri", "")
        doc_id = uri.split("docs://", 1)[-1]
        for d in DOCS:
            if d["id"] == doc_id:
                return {"contents": [{"uri": uri, "mimeType": "text/plain",
                                      "text": d["text"]}]}
        raise ValueError("unknown resource: %s" % uri)
    if method == "prompts/list":
        return {"prompts": [{"name": "qa-with-citations",
                             "description": "Answer a question citing retrieved docs.",
                             "arguments": [{"name": "question", "required": True}]}]}
    if method == "prompts/get":
        question = (params.get("arguments") or {}).get("question", "")
        return {"messages": [
            {"role": "system",
             "content": {"type": "text",
                         "text": "Answer using only the retrieved documents. "
                                 "Cite sources as [doc-id] after each claim."}},
            {"role": "user",
             "content": {"type": "text", "text": question}}]}
    raise ValueError("unknown method: %s" % method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in request:  # JSON-RPC notification: no response
            continue
        try:
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "result": handle(request)}
        except Exception as exc:  # noqa: BLE001 - surface as JSON-RPC error
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "error": {"code": -32603, "message": str(exc)}}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
