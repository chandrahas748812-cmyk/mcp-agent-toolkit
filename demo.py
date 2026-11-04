"""End-to-end demo: two questions through the mock agent (no API keys)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import run_agent  # noqa: E402
from client import MCPClient  # noqa: E402


def main():
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "server.py")
    client = MCPClient(server_path)
    try:
        client.initialize()
        for question in ("What is MCP and how does tool calling work?",
                         "What time is it right now?"):
            print("Q: %s" % question)
            outcome = run_agent(client, question)
            for tool, args, _result in outcome["trace"]:
                print("  -> tool: %s %s" % (tool, args))
            print("A: %s\n" % outcome["answer"])
    finally:
        client.close()


if __name__ == "__main__":
    main()
