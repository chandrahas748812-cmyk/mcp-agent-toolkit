"""Tests: tool dispatch, resource reads, prompt template, agent tool-use flow."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import MockLLM, run_agent  # noqa: E402
from client import MCPClient  # noqa: E402

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "server.py")


class ToolkitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MCPClient(SERVER)
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_tools_list(self):
        names = {t["name"] for t in self.client.list_tools()}
        self.assertEqual(names, {"doc-search", "time", "memory"})

    def test_doc_search_dispatch(self):
        result = self.client.call_tool(
            "doc-search", {"query": "Model Context Protocol tools", "top_k": 2})
        self.assertTrue(result["results"])
        self.assertEqual(result["results"][0]["id"], "mcp-overview")

    def test_time_tool(self):
        result = self.client.call_tool("time", {})
        self.assertIn("T", result["utc_now"])

    def test_memory_set_get(self):
        self.assertTrue(self.client.call_tool(
            "memory", {"action": "set", "key": "t-key", "value": "t-val"})["ok"])
        got = self.client.call_tool(
            "memory", {"action": "get", "key": "t-key"})
        self.assertEqual(got["value"], "t-val")

    def test_unknown_tool_errors(self):
        with self.assertRaises(RuntimeError):
            self.client.call_tool("nope", {})

    def test_resources(self):
        resources = self.client.list_resources()
        self.assertEqual(len(resources), 2)
        text = self.client.read_resource("docs://mcp-overview")
        self.assertIn("Model Context Protocol", text)

    def test_prompt_template(self):
        messages = self.client.get_prompt(
            "qa-with-citations", {"question": "What is MCP?"})
        self.assertEqual(messages[-1]["content"]["text"], "What is MCP?")
        self.assertIn("Cite", messages[0]["content"]["text"])

    def test_agent_doc_flow_cites(self):
        outcome = run_agent(self.client,
                            "What is MCP and how does tool calling work?",
                            llm=MockLLM())
        self.assertTrue(any(t == "doc-search" for t, _a, _r in outcome["trace"]))
        self.assertIn("[mcp-overview]", outcome["answer"])

    def test_agent_time_flow(self):
        outcome = run_agent(self.client, "What time is it?", llm=MockLLM())
        self.assertTrue(any(t == "time" for t, _a, _r in outcome["trace"]))
        self.assertIn("UTC time", outcome["answer"])


if __name__ == "__main__":
    unittest.main()
