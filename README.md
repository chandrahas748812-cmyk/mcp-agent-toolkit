# MCP Agent Toolkit

A small, runnable Model Context Protocol (MCP) toolkit in pure-stdlib
Python: an MCP server, a client, and an agent loop that answers questions
by calling the server's tools and citing what it retrieved.

**Portfolio / learning project.** This is a from-scratch teaching
implementation built to learn the MCP pattern. It is not employer work,
contains no proprietary data, and the sample corpus is invented
placeholder text.

## What MCP is

MCP is an open protocol for connecting AI models to external data
sources and tools. Instead of wiring each model to each data source by
hand, a server exposes a standard interface — **tools** (functions the
model can call), **resources** (documents/data it can read), and
**prompts** (reusable templates) — and any compatible client can
discover and use them over JSON-RPC.

## Architecture

```
Question
   │
   ▼
Agent loop (agent.py) ── MockLLM or OpenAI-compatible LLM
   │  decides: call a tool, or answer
   ▼
MCP client (client.py) ── stdio JSON-RPC ──► MCP server (server.py)
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                         doc-search            time                 memory
                      (sample corpus)      (UTC clock)         (key-value store)
                              │
                              ▼
                      resources: docs://mcp-overview, docs://tool-calling…
                      prompt: qa-with-citations (answer + cite [doc-id])
   │
   ▼
Answer with citations, e.g. "Based on [mcp-overview]: …"
```

## Run it (no API keys needed)

```bash
cd mcp-agent-toolkit
python demo.py            # mock LLM path: doc question + time question
python -m unittest discover -s tests -v
```

The default LLM is a deterministic mock (`MockLLM` in `agent.py`) that
picks tools from the question text, so the demo runs fully offline.

## Using a real model (optional)

```bash
export MCP_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
export MCP_LLM_API_KEY="your-key"          # never commit this; see .gitignore
export MCP_LLM_MODEL="gpt-4o-mini"         # optional, this is the default
python demo.py
```

When those variables are set, `agent.py` uses the OpenAI-compatible
endpoint with function-calling; otherwise it falls back to the mock.
No key is ever required to run the project.

## How this maps to production

In production agent systems (e.g. a Bedrock-style agent with MCP tool
calling), the same shape holds at larger scale: the agent plans, calls
allow-listed tools, and grounds answers in retrieved context. What
changes is the plumbing — remote MCP servers over HTTP/SSE instead of
stdio, auth on every tool call, retrieval over a real hybrid
(BM25 + dense) index instead of keyword overlap, guardrails and
human-in-the-loop gates on side-effecting tools, and eval harnesses
measuring citation accuracy and tool-selection precision.

## Interview talking points

- **Why MCP over bespoke tool glue?** One standard interface means any
  client can use any server; tools are discoverable, typed, and
  versioned instead of hand-wired per integration.
- **Tool-use loop:** model proposes a call → client executes → result
  re-enters context → repeat until the model can answer with evidence.
- **Citations as a guardrail:** answers must reference retrieved doc
  ids, which makes hallucinations checkable rather than just plausible.
- **Safety:** allow-list tools, validate arguments server-side, keep
  side effects explicit; a read-only doc-search tool and a clock are
  safe defaults, a memory/write tool is where review gates belong.
- **What I would add next:** HTTP transport, auth, a real hybrid
  retriever, and an eval set scoring citation precision.

## Files

| File | Purpose |
| --- | --- |
| `server.py` | stdio JSON-RPC MCP server: 3 tools, 2 resources, 1 prompt |
| `client.py` | Subprocess client for the server |
| `agent.py` | Agent loop + pluggable LLM (mock default, OpenAI-compatible hook) |
| `demo.py` | Offline end-to-end demo |
| `data/sample_docs.json` | Invented sample corpus |
| `tests/test_toolkit.py` | Tool dispatch, resource, prompt, and agent-flow tests |
