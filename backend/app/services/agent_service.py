"""
AI Agent Service.

Orchestrates LLM calls with function calling for the platform chatbot.
Supports OpenAI and Anthropic APIs via httpx.
"""

import json
import httpx
from typing import AsyncGenerator

from app.core.config import get_settings
from app.services.agent_tools import (
    OPENAI_TOOLS,
    ANTHROPIC_TOOLS,
    execute_tool,
)

SYSTEM_PROMPT = """You are the AI assistant for the LLM Cloud Cost & Deployment Platform. You help users:

- Estimate costs for self-hosting open-source LLM models on AWS, GCP, and Azure
- Compare costs across cloud providers
- Recommend the best model for their use case and budget
- Explain GPU requirements, VRAM calculations, and pricing
- Guide users through platform features (cost calculator, model builder, deployment)

You have access to real cost calculation tools. Use them to give accurate, data-driven answers.
Always provide specific numbers and recommendations when possible.
Keep responses concise and actionable.

When a user asks about cost, always use the estimate_cost or compare_providers tool to get real numbers.
When recommending models, use the recommend_model tool."""


class AgentService:
    def __init__(self):
        settings = get_settings()
        self.provider = settings.AGENT_LLM_PROVIDER
        self.api_key = settings.AGENT_LLM_API_KEY
        self.model = settings.AGENT_LLM_MODEL
        self.base_url = settings.AGENT_LLM_BASE_URL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        message: str,
        context: dict,
        history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat message with tool calling support.
        Yields text chunks for streaming.
        """
        # If no API key configured, use offline mode
        if not self.api_key:
            async for chunk in self._offline_chat(message, context):
                yield chunk
            return

        if self.provider == "anthropic":
            async for chunk in self._chat_anthropic(message, context, history):
                yield chunk
        else:
            async for chunk in self._chat_openai(message, context, history):
                yield chunk

    async def _chat_openai(
        self,
        message: str,
        context: dict,
        history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """Call OpenAI-compatible API with function calling."""
        base = self.base_url or "https://api.openai.com"
        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nCurrent user context: {json.dumps(context)}"

        messages = [{"role": "system", "content": system}]
        for h in history[-10:]:  # Last 10 messages for context
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        # Non-streaming call to handle tool calls
        resp = await self.client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "tools": OPENAI_TOOLS,
                "tool_choice": "auto",
            },
        )
        data = resp.json()

        if "error" in data:
            yield f"Error: {data['error'].get('message', 'Unknown error')}"
            return

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})

        # Handle tool calls
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            messages.append(msg)  # Add assistant message with tool calls

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                result = execute_tool(tool_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Second call with tool results
            resp2 = await self.client.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
            data2 = resp2.json()
            final_msg = data2.get("choices", [{}])[0].get("message", {}).get("content", "")
            yield final_msg
        else:
            yield msg.get("content", "I couldn't generate a response.")

    async def _chat_anthropic(
        self,
        message: str,
        context: dict,
        history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """Call Anthropic API with tool use."""
        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nCurrent user context: {json.dumps(context)}"

        messages = []
        for h in history[-10:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        resp = await self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "system": system,
                "messages": messages,
                "tools": ANTHROPIC_TOOLS,
                "max_tokens": 1024,
            },
        )
        data = resp.json()

        if "error" in data:
            yield f"Error: {data['error'].get('message', 'Unknown error')}"
            return

        # Process content blocks
        content_blocks = data.get("content", [])
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

        if tool_uses:
            # Execute tools and make follow-up call
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for tu in tool_uses:
                result = execute_tool(tu["name"], tu.get("input", {}))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result,
                })
            messages.append({"role": "user", "content": tool_results})

            resp2 = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "system": system,
                    "messages": messages,
                    "max_tokens": 1024,
                },
            )
            data2 = resp2.json()
            for block in data2.get("content", []):
                if block.get("type") == "text":
                    yield block["text"]
        else:
            for block in content_blocks:
                if block.get("type") == "text":
                    yield block["text"]

    async def _offline_chat(
        self,
        message: str,
        context: dict,
    ) -> AsyncGenerator[str, None]:
        """
        Offline mode — handle common queries using tools directly,
        without calling an external LLM API.
        """
        msg_lower = message.lower()

        # Try to detect intent and use tools directly
        if any(w in msg_lower for w in ["cost", "price", "how much", "estimate"]):
            # Try to extract model size
            params = _extract_params(msg_lower)
            provider = _extract_provider(msg_lower) or "aws"
            if params:
                result = execute_tool("estimate_cost", {
                    "parameters_billion": params,
                    "cloud_provider": provider,
                })
                data = json.loads(result)
                if "error" not in data:
                    yield (
                        f"**Cost Estimate for {params}B model on {provider.upper()}:**\n\n"
                        f"- **Monthly cost:** ${data['total_monthly_cost']:,.2f}\n"
                        f"- **Instance:** {data['instance_type']} ({data['gpu_type']} × {data['gpu_count']})\n"
                        f"- **VRAM required:** {data['vram_required_gb']:.1f} GB\n"
                        f"- **Compute:** ${data['compute_cost']:,.2f}/mo\n\n"
                        f"💡 {data['recommendation']}"
                    )
                    return
                yield f"I couldn't find a suitable GPU for a {params}B model. Try a smaller model or different precision."
                return

        if any(w in msg_lower for w in ["recommend", "suggest", "best model", "which model"]):
            use_case = "general"
            for uc in ["coding", "chat", "reasoning", "multilingual", "summarization"]:
                if uc in msg_lower:
                    use_case = uc
                    break

            budget = 1000  # default
            for word in msg_lower.split():
                word = word.replace("$", "").replace(",", "")
                try:
                    val = float(word)
                    if 50 <= val <= 100000:
                        budget = val
                        break
                except ValueError:
                    pass

            result = execute_tool("recommend_model", {
                "use_case": use_case,
                "max_budget_monthly": budget,
            })
            recs = json.loads(result)
            if recs:
                lines = [f"**Top models for {use_case} under ${budget:,.0f}/mo:**\n"]
                for r in recs[:3]:
                    lines.append(
                        f"- **{r['model_name']}** ({r['parameters_billion']}B) — "
                        f"${r['monthly_cost']:,.0f}/mo on {r['cloud_provider'].upper()} "
                        f"[{r['quality_tier']}]"
                    )
                yield "\n".join(lines)
                return

        if any(w in msg_lower for w in ["compare", "aws vs", "gcp vs", "azure vs"]):
            params = _extract_params(msg_lower)
            if params:
                result = execute_tool("compare_providers", {"parameters_billion": params})
                data = json.loads(result)
                lines = [f"**Multi-cloud comparison for {params}B model:**\n"]
                for prov, info in data.items():
                    if "error" in info:
                        lines.append(f"- **{prov.upper()}:** No suitable GPU")
                    else:
                        lines.append(f"- **{prov.upper()}:** ${info['monthly_cost']:,.0f}/mo ({info['instance_type']}, {info['gpu_type']} × {info['gpu_count']})")
                yield "\n".join(lines)
                return

        if any(w in msg_lower for w in ["gpu", "a100", "h100", "t4", "a10"]):
            result = execute_tool("get_gpu_info", {})
            data = json.loads(result)
            lines = ["**Available GPUs:**\n"]
            for key, info in data.items():
                lines.append(f"- **{info['name']}** — {info['vram_gb']}GB VRAM, {info['tflops_fp16']} TFLOPS FP16")
            yield "\n".join(lines)
            return

        # Default helpful response
        yield (
            "I can help you with:\n\n"
            "- **Cost estimates** — \"How much does it cost to run Llama 70B on AWS?\"\n"
            "- **Model recommendations** — \"Best coding model under $500/mo\"\n"
            "- **Provider comparison** — \"Compare 8B model across clouds\"\n"
            "- **GPU info** — \"What GPUs are available?\"\n\n"
            "Try asking one of these questions!"
        )


def _extract_params(text: str) -> float | None:
    """Try to extract model size in billions from text."""
    import re
    # Match patterns like "70B", "7b", "8 billion", "70 billion"
    m = re.search(r'(\d+(?:\.\d+)?)\s*[bB](?:illion)?', text)
    if m:
        return float(m.group(1))
    # Match known model names
    for model in ["405", "123", "70", "72", "46.7", "27", "14", "13", "9", "8", "7", "3.8", "1.1"]:
        if model in text:
            return float(model)
    return None


def _extract_provider(text: str) -> str | None:
    """Try to extract cloud provider from text."""
    if "aws" in text or "amazon" in text:
        return "aws"
    if "gcp" in text or "google cloud" in text:
        return "gcp"
    if "azure" in text or "microsoft" in text:
        return "azure"
    return None
