"""
Agent Tool Definitions and Executors.

Wraps existing backend services as callable tools for the AI agent.
Each tool has a JSON schema (for LLM function calling) and an execute function.
"""

import json
from app.services.cost_engine.calculator import estimate_cost
from app.services.recommender import recommend_models, MODEL_CATALOG
from app.services.cost_engine.gpu_catalog import GPU_SPECS


AGENT_TOOLS = [
    {
        "name": "estimate_cost",
        "description": "Calculate the monthly cost to self-host an LLM model on a cloud provider. Returns GPU type, VRAM, instance type, and detailed cost breakdown.",
        "parameters": {
            "type": "object",
            "properties": {
                "parameters_billion": {"type": "number", "description": "Model size in billions of parameters (e.g. 7, 13, 70)"},
                "cloud_provider": {"type": "string", "enum": ["aws", "gcp", "azure"], "description": "Cloud provider"},
                "precision": {"type": "string", "enum": ["fp16", "bf16", "int8", "int4"], "description": "Model precision/quantization"},
                "context_length": {"type": "integer", "description": "Serving context length in tokens"},
                "expected_qps": {"type": "number", "description": "Expected queries per second"},
                "hours_per_day": {"type": "integer", "description": "Hours per day the model runs"},
            },
            "required": ["parameters_billion", "cloud_provider"],
        },
    },
    {
        "name": "compare_providers",
        "description": "Compare the cost of deploying a model across all three cloud providers (AWS, GCP, Azure).",
        "parameters": {
            "type": "object",
            "properties": {
                "parameters_billion": {"type": "number", "description": "Model size in billions of parameters"},
                "precision": {"type": "string", "enum": ["fp16", "bf16", "int8", "int4"]},
                "context_length": {"type": "integer"},
            },
            "required": ["parameters_billion"],
        },
    },
    {
        "name": "recommend_model",
        "description": "Recommend the best open-source LLM models for a specific use case within a monthly budget.",
        "parameters": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "description": "Use case: coding, chat, reasoning, general, multilingual, summarization"},
                "max_budget_monthly": {"type": "number", "description": "Maximum monthly budget in USD"},
                "cloud_provider": {"type": "string", "enum": ["aws", "gcp", "azure"]},
            },
            "required": ["use_case", "max_budget_monthly"],
        },
    },
    {
        "name": "search_models",
        "description": "Search the catalog of available open-source LLM models by name or characteristics.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (model name, use case, or size like '70B')"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_gpu_info",
        "description": "Get specifications for available GPU types (VRAM, TFLOPS, memory bandwidth).",
        "parameters": {
            "type": "object",
            "properties": {
                "gpu_type": {"type": "string", "description": "GPU name like 'A100_80GB', 'H100', 'A10G', 'T4'. Leave empty for all."},
            },
        },
    },
    {
        "name": "generate_infra",
        "description": "Generate deployment infrastructure files (Dockerfile, Kubernetes YAML, Terraform/CloudFormation/Pulumi) for deploying an LLM model on a specific cloud provider.",
        "parameters": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model name (e.g. 'Llama-3-70B')"},
                "parameters_billion": {"type": "number", "description": "Model size in billions of parameters"},
                "cloud_provider": {"type": "string", "enum": ["aws", "gcp", "azure"], "description": "Cloud provider"},
                "iac_language": {"type": "string", "enum": ["terraform", "cloudformation", "pulumi", "kubernetes"], "description": "Infrastructure-as-Code language (default: terraform)"},
                "precision": {"type": "string", "enum": ["fp16", "bf16", "int8", "int4"]},
                "context_length": {"type": "integer"},
                "region": {"type": "string", "description": "Cloud region (e.g. us-east-1)"},
            },
            "required": ["model_name", "parameters_billion", "cloud_provider"],
        },
    },
    {
        "name": "search_infra",
        "description": "Search for cloud GPU instances, pricing, and deployment best practices.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query about cloud infrastructure"},
                "cloud_provider": {"type": "string", "enum": ["aws", "gcp", "azure"]},
            },
            "required": ["query"],
        },
    },
]

# OpenAI function calling format
OPENAI_TOOLS = [
    {"type": "function", "function": {k: v for k, v in t.items()}}
    for t in AGENT_TOOLS
]

# Anthropic tool format
ANTHROPIC_TOOLS = [
    {
        "name": t["name"],
        "description": t["description"],
        "input_schema": t["parameters"],
    }
    for t in AGENT_TOOLS
]


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name and return JSON result string."""
    try:
        if name == "estimate_cost":
            result = estimate_cost(
                parameters_billion=arguments["parameters_billion"],
                precision=arguments.get("precision", "fp16"),
                context_length=arguments.get("context_length", 4096),
                cloud_provider=arguments["cloud_provider"],
                expected_qps=arguments.get("expected_qps", 1.0),
                hours_per_day=arguments.get("hours_per_day", 24),
                days_per_month=arguments.get("days_per_month", 30),
            )
            if result is None:
                return json.dumps({"error": "No suitable GPU found for this model configuration."})
            return json.dumps({
                "total_monthly_cost": result.total_cost_monthly,
                "instance_type": result.instance_type,
                "gpu_type": result.gpu_type,
                "gpu_count": result.gpu_count,
                "vram_required_gb": result.vram_required_gb,
                "compute_cost": result.compute_cost_monthly,
                "storage_cost": result.storage_cost_monthly,
                "recommendation": result.recommendation,
            })

        elif name == "compare_providers":
            params_b = arguments["parameters_billion"]
            precision = arguments.get("precision", "fp16")
            ctx = arguments.get("context_length", 4096)
            results = {}
            for provider in ["aws", "gcp", "azure"]:
                est = estimate_cost(
                    parameters_billion=params_b,
                    precision=precision,
                    context_length=ctx,
                    cloud_provider=provider,
                )
                if est:
                    results[provider] = {
                        "monthly_cost": est.total_cost_monthly,
                        "instance_type": est.instance_type,
                        "gpu_type": est.gpu_type,
                        "gpu_count": est.gpu_count,
                    }
                else:
                    results[provider] = {"error": "No suitable GPU found"}
            return json.dumps(results)

        elif name == "recommend_model":
            recs = recommend_models(
                use_case=arguments["use_case"],
                max_budget_monthly=arguments["max_budget_monthly"],
                cloud_provider=arguments.get("cloud_provider"),
            )
            return json.dumps(recs)

        elif name == "search_models":
            query = arguments.get("query", "").lower()
            matches = [
                {
                    "name": m["name"],
                    "parameters_billion": m["parameters_billion"],
                    "context_length": m["context_length"],
                    "tags": m["tags"],
                    "quality_tier": m["quality_tier"],
                }
                for m in MODEL_CATALOG
                if query in m["name"].lower()
                or query in " ".join(m["tags"])
                or query in str(m["parameters_billion"])
            ]
            return json.dumps(matches if matches else {"message": f"No models found for '{query}'. Available: {[m['name'] for m in MODEL_CATALOG]}"})

        elif name == "get_gpu_info":
            gpu_type = arguments.get("gpu_type", "").strip()
            if gpu_type:
                spec = GPU_SPECS.get(gpu_type)
                if spec:
                    return json.dumps({"name": spec.name, "vram_gb": spec.vram_gb, "tflops_fp16": spec.fp16_tflops, "memory_bandwidth_gbps": spec.memory_bandwidth_gbps})
                return json.dumps({"error": f"GPU '{gpu_type}' not found. Available: {list(GPU_SPECS.keys())}"})
            return json.dumps({k: {"name": v.name, "vram_gb": v.vram_gb, "tflops_fp16": v.fp16_tflops} for k, v in GPU_SPECS.items()})

        elif name == "generate_infra":
            from app.schemas.infra import InfraGenerateRequest
            from app.services.infra_agent import generate_infra
            req = InfraGenerateRequest(
                model_name=arguments["model_name"],
                parameters_billion=arguments["parameters_billion"],
                cloud_provider=arguments["cloud_provider"],
                iac_language=arguments.get("iac_language", "terraform"),
                precision=arguments.get("precision", "fp16"),
                context_length=arguments.get("context_length", 4096),
                region=arguments.get("region", ""),
            )
            result = generate_infra(req)
            return json.dumps({
                "deployment_id": result.deployment_id,
                "cloud_provider": result.cloud_provider,
                "iac_language": result.iac_language,
                "instance_type": result.instance_type,
                "gpu_type": result.gpu_type,
                "gpu_count": result.gpu_count,
                "estimated_monthly_cost": result.estimated_monthly_cost,
                "files_generated": [f.filename for f in result.files],
                "summary": result.summary,
            })

        elif name == "search_infra":
            from app.schemas.infra import InfraSearchRequest
            from app.services.infra_agent import search_cloud_infra
            req = InfraSearchRequest(
                query=arguments["query"],
                cloud_provider=arguments.get("cloud_provider"),
            )
            result = search_cloud_infra(req)
            return json.dumps({
                "query": result.query,
                "results": [
                    {"source": r.source, "title": r.title, "snippet": r.snippet}
                    for r in result.results
                ],
            })

        return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})
