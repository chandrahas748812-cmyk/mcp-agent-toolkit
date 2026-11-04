"""Agent loop over the MCP client with a pluggable LLM interface.

Default: MockLLM, a deterministic rule-based stand-in that demonstrates
tool selection with ZERO API keys. Set MCP_LLM_ENDPOINT (an
OpenAI-compatible chat-completions URL) plus MCP_LLM_API_KEY and
optionally MCP_LLM_MODEL to use a real model instead; the mock is used
whenever those are unset.
"""

import json
import os
import urllib.request


class MockLLM:
    """Deterministic tool selection so the demo runs offline.

    Step 0 picks a tool from the question text; later steps compose the
    final answer from the tool result, citing retrieved doc ids.
    """

    def next_action(self, question, trace):
        if trace:
            tool, _args, result = trace[-1]
            if tool == "doc-search":
                results = result.get("results", [])
                if not results:
                    return ("answer", "No documents matched that question.")
                cites = ", ".join("[%s]" % r["id"] for r in results)
                summary = " ".join(r["snippet"] for r in results[:2])
                return ("answer",
                        "Based on %s: %s" % (cites, summary))
            if tool == "time":
                return ("answer",
                        "The current UTC time is %s." % result["utc_now"])
            if tool == "memory":
                if result.get("ok"):
                    return ("answer", "Stored value: %s" % result.get("value", result))
                return ("answer", "Memory lookup failed: %s" % result.get("error"))
            return ("answer", "Done.")
        q = question.lower()
        if "time" in q or "clock" in q:
            return ("tool", "time", {})
        if "remember" in q or "store" in q:
            return ("tool", "memory",
                    {"action": "set", "key": "note", "value": question})
        if "recall" in q or "what did i" in q:
            return ("tool", "memory", {"action": "get", "key": "note"})
        return ("tool", "doc-search", {"query": question, "top_k": 3})


class OpenAICompatibleLLM:
    """Thin OpenAI-compatible chat-completions client (stdlib urllib)."""

    def __init__(self, endpoint, api_key, model):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model

    def next_action(self, question, trace):
        messages = [{"role": "system",
                     "content": "You are an agent with tools: doc-search, time, "
                                "memory. Call a tool when it helps; otherwise "
                                "answer, citing [doc-id] for retrieved docs."},
                    {"role": "user", "content": question}]
        for tool, args, result in trace:
            messages.append({"role": "assistant",
                             "content": "Called %s(%s)" % (tool, json.dumps(args))})
            messages.append({"role": "user",
                             "content": "Tool result: %s" % json.dumps(result)})
        tools = [{"type": "function",
                  "function": {"name": n,
                               "description": d,
                               "parameters": {"type": "object",
                                              "properties": {}}}}
                 for n, d in [("doc-search", "Search local docs"),
                              ("time", "Current UTC time"),
                              ("memory", "Key-value store")]]
        body = json.dumps({"model": self.model, "messages": messages,
                           "tools": tools}).encode()
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer %s" % self.api_key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            choice = json.load(resp)["choices"][0]["message"]
        calls = choice.get("tool_calls") or []
        if calls:
            call = calls[0]
            return ("tool", call["function"]["name"],
                    json.loads(call["function"]["arguments"] or "{}"))
        return ("answer", choice.get("content") or "")


def default_llm():
    endpoint = os.environ.get("MCP_LLM_ENDPOINT")
    api_key = os.environ.get("MCP_LLM_API_KEY")
    if endpoint and api_key:
        return OpenAICompatibleLLM(
            endpoint, api_key,
            os.environ.get("MCP_LLM_MODEL", "gpt-4o-mini"))
    return MockLLM()


def run_agent(client, question, llm=None, max_steps=5):
    """Run the agent loop. Returns {"answer": str, "trace": [...]}."""
    llm = llm or default_llm()
    trace = []
    for _ in range(max_steps):
        action = llm.next_action(question, trace)
        if action[0] == "answer":
            return {"answer": action[1], "trace": trace}
        _kind, tool, args = action
        result = client.call_tool(tool, args)
        trace.append((tool, args, result))
    return {"answer": "Stopped after %d steps without a final answer."
                      % max_steps, "trace": trace}
