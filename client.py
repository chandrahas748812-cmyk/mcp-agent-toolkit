"""Minimal stdio MCP client: spawns server.py and speaks JSON-RPC over pipes."""

import json
import subprocess
import sys


class MCPClient:
    def __init__(self, server_path):
        self.proc = subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self._next_id = 0

    def request(self, method, params=None):
        self._next_id += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": self._next_id,
             "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        response = json.loads(self.proc.stdout.readline())
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return response["result"]

    def initialize(self):
        return self.request("initialize")

    def list_tools(self):
        return self.request("tools/list")["tools"]

    def call_tool(self, name, arguments=None):
        result = self.request("tools/call",
                              {"name": name, "arguments": arguments or {}})
        return json.loads(result["content"][0]["text"])

    def list_resources(self):
        return self.request("resources/list")["resources"]

    def read_resource(self, uri):
        return self.request("resources/read", {"uri": uri})["contents"][0]["text"]

    def list_prompts(self):
        return self.request("prompts/list")["prompts"]

    def get_prompt(self, name, arguments=None):
        return self.request("prompts/get",
                            {"name": name, "arguments": arguments or {}})["messages"]

    def close(self):
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        self.proc.wait(timeout=5)
