"""Tests for agent tool definitions and execution."""

import json
import pytest
from app.services.agent_tools import execute_tool, OPENAI_TOOLS


class TestAgentTools:
    def test_openai_tools_structure(self):
        assert len(OPENAI_TOOLS) > 0
        for tool in OPENAI_TOOLS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]

    def test_estimate_cost_tool(self):
        result = execute_tool("estimate_cost", {
            "parameters_billion": 8.0,
            "precision": "fp16",
            "context_length": 4096,
            "cloud_provider": "aws",
        })
        parsed = json.loads(result)
        assert "total_monthly_cost" in parsed

    def test_recommend_model_tool(self):
        result = execute_tool("recommend_model", {
            "use_case": "chat",
            "max_budget_monthly": 5000,
        })
        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_models_tool(self):
        result = execute_tool("search_models", {"query": "llama"})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list) and len(parsed) > 0

    def test_get_gpu_info_tool(self):
        result = execute_tool("get_gpu_info", {})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert len(parsed) > 0

    def test_compare_providers_tool(self):
        result = execute_tool("compare_providers", {
            "parameters_billion": 8.0,
        })
        parsed = json.loads(result)
        assert "aws" in parsed or "error" in str(parsed)

    def test_unknown_tool(self):
        result = execute_tool("nonexistent_tool", {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown" in parsed["error"]
