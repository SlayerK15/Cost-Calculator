"""Tests for the Infrastructure Agent API and service."""

import pytest
from httpx import AsyncClient


# ═══════════════════════════════════════════════════════════════
# POST /api/infra/generate — deployment file generation
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_terraform_aws(client: AsyncClient):
    """Generate Terraform files for AWS."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "terraform",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["cloud_provider"] == "aws"
    assert data["iac_language"] == "terraform"
    assert data["gpu_count"] >= 1
    assert len(data["files"]) >= 3  # Dockerfile + k8s + terraform + ci/cd + quickstart
    filenames = [f["filename"] for f in data["files"]]
    assert "Dockerfile" in filenames
    assert "kubernetes.yaml" in filenames
    assert "main.tf" in filenames
    assert any("deploy" in f for f in filenames)  # CI/CD


@pytest.mark.asyncio
async def test_generate_terraform_gcp(client: AsyncClient):
    """Generate Terraform files for GCP."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Mistral-7B",
        "parameters_billion": 7,
        "cloud_provider": "gcp",
        "iac_language": "terraform",
        "region": "us-central1",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["cloud_provider"] == "gcp"
    assert data["region"] == "us-central1"
    tf_file = next(f for f in data["files"] if f["filename"] == "main.tf")
    assert "google" in tf_file["content"].lower()


@pytest.mark.asyncio
async def test_generate_terraform_azure(client: AsyncClient):
    """Generate Terraform files for Azure."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-70B",
        "parameters_billion": 70,
        "cloud_provider": "azure",
        "iac_language": "terraform",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["cloud_provider"] == "azure"
    tf_file = next(f for f in data["files"] if f["filename"] == "main.tf")
    assert "azurerm" in tf_file["content"].lower()


@pytest.mark.asyncio
async def test_generate_cloudformation_aws(client: AsyncClient):
    """Generate CloudFormation for AWS."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "cloudformation",
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    assert "cloudformation.yaml" in filenames
    cfn_file = next(f for f in data["files"] if f["filename"] == "cloudformation.yaml")
    assert "AWSTemplateFormatVersion" in cfn_file["content"]


@pytest.mark.asyncio
async def test_generate_cloudformation_non_aws_fallback(client: AsyncClient):
    """CloudFormation on non-AWS falls back to Terraform."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "gcp",
        "iac_language": "cloudformation",
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    # Should have a notice file and a terraform fallback
    assert "main.tf" in filenames


@pytest.mark.asyncio
async def test_generate_pulumi_aws(client: AsyncClient):
    """Generate Pulumi Python for AWS."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "pulumi",
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    assert "__main__.py" in filenames
    assert "Pulumi.yaml" in filenames
    assert "requirements.txt" in filenames
    pulumi_file = next(f for f in data["files"] if f["filename"] == "__main__.py")
    assert "pulumi" in pulumi_file["content"].lower()


@pytest.mark.asyncio
async def test_generate_pulumi_gcp(client: AsyncClient):
    """Generate Pulumi Python for GCP."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Mistral-7B",
        "parameters_billion": 7,
        "cloud_provider": "gcp",
        "iac_language": "pulumi",
    })
    assert resp.status_code == 200
    data = resp.json()
    pulumi_file = next(f for f in data["files"] if f["filename"] == "__main__.py")
    assert "gcp" in pulumi_file["content"].lower() or "gke" in pulumi_file["content"].lower()


@pytest.mark.asyncio
async def test_generate_pulumi_azure(client: AsyncClient):
    """Generate Pulumi Python for Azure."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "azure",
        "iac_language": "pulumi",
    })
    assert resp.status_code == 200
    data = resp.json()
    pulumi_file = next(f for f in data["files"] if f["filename"] == "__main__.py")
    assert "azure" in pulumi_file["content"].lower()


@pytest.mark.asyncio
async def test_generate_kubernetes_only(client: AsyncClient):
    """Generate K8s YAML only (no IaC)."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "kubernetes",
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    assert "kubernetes.yaml" in filenames
    assert "Dockerfile" in filenames
    # No terraform or pulumi files
    assert "main.tf" not in filenames
    assert "__main__.py" not in filenames


@pytest.mark.asyncio
async def test_generate_with_monitoring(client: AsyncClient):
    """Monitoring YAML is included when enabled."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "terraform",
        "enable_monitoring": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    assert "monitoring.yaml" in filenames


@pytest.mark.asyncio
async def test_generate_without_monitoring(client: AsyncClient):
    """No monitoring YAML when disabled."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "terraform",
        "enable_monitoring": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    filenames = [f["filename"] for f in data["files"]]
    assert "monitoring.yaml" not in filenames


@pytest.mark.asyncio
async def test_generate_includes_cost_estimate(client: AsyncClient):
    """Response includes estimated monthly cost."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "terraform",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "estimated_monthly_cost" in data
    assert isinstance(data["estimated_monthly_cost"], (int, float))


@pytest.mark.asyncio
async def test_generate_includes_summary(client: AsyncClient):
    """Response includes a human-readable summary."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
        "iac_language": "terraform",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "Llama-3-8B" in data["summary"]
    assert "AWS" in data["summary"]


@pytest.mark.asyncio
async def test_generate_large_model(client: AsyncClient):
    """Generate for a large 70B model."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-70B",
        "parameters_billion": 70,
        "cloud_provider": "aws",
        "iac_language": "terraform",
        "precision": "fp16",
    })
    assert resp.status_code == 200
    data = resp.json()
    # Large model should get a GPU with sufficient VRAM
    assert data["gpu_type"] is not None
    assert len(data["files"]) >= 3


@pytest.mark.asyncio
async def test_generate_validation_missing_fields(client: AsyncClient):
    """Missing required fields returns 422."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Llama-3-8B",
        # missing parameters_billion and cloud_provider
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_validation_invalid_params(client: AsyncClient):
    """Invalid parameter values return 422."""
    resp = await client.post("/api/infra/generate", json={
        "model_name": "Test",
        "parameters_billion": -1,
        "cloud_provider": "aws",
    })
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# POST /api/infra/search — infrastructure search
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_gpu_types(client: AsyncClient):
    """Search for GPU types returns relevant results."""
    resp = await client.post("/api/infra/search", json={"query": "A100"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "A100"
    assert len(data["results"]) > 0
    assert any("A100" in r["title"] for r in data["results"])


@pytest.mark.asyncio
async def test_search_pricing(client: AsyncClient):
    """Search for pricing returns cost information."""
    resp = await client.post("/api/infra/search", json={"query": "pricing aws"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0
    assert any("pricing" in r["source"].lower() or "price" in r["snippet"].lower() or "$" in r["snippet"] for r in data["results"])


@pytest.mark.asyncio
async def test_search_best_practices(client: AsyncClient):
    """Search for best practices returns guidance."""
    resp = await client.post("/api/infra/search", json={"query": "terraform best practices"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0
    assert any("best practice" in r["title"].lower() for r in data["results"])


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient):
    """Search with garbage query returns fallback result."""
    resp = await client.post("/api/infra/search", json={"query": "xyznonexistent123"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) >= 1  # Fallback "no match" result


@pytest.mark.asyncio
async def test_search_with_provider_filter(client: AsyncClient):
    """Search filtered by cloud provider."""
    resp = await client.post("/api/infra/search", json={
        "query": "gpu instance",
        "cloud_provider": "gcp",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0


# ═══════════════════════════════════════════════════════════════
# Service unit tests (direct function calls)
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_service_generate_infra_returns_deployment_id():
    """generate_infra returns a valid UUID deployment_id."""
    from app.schemas.infra import InfraGenerateRequest
    from app.services.infra_agent import generate_infra
    req = InfraGenerateRequest(
        model_name="Test-Model",
        parameters_billion=7,
        cloud_provider="aws",
    )
    result = generate_infra(req)
    assert len(result.deployment_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_service_search_infra_returns_sorted():
    """search_cloud_infra returns results sorted by relevance."""
    from app.schemas.infra import InfraSearchRequest
    from app.services.infra_agent import search_cloud_infra
    result = search_cloud_infra(InfraSearchRequest(query="A100 pricing"))
    relevances = [r.relevance for r in result.results]
    assert relevances == sorted(relevances, reverse=True)


@pytest.mark.asyncio
async def test_service_pulumi_generation():
    """Pulumi generation produces valid Python code."""
    from app.services.infra_agent import generate_pulumi_python
    code = generate_pulumi_python(
        deployment_id="test-1234-5678-abcd",
        model_name="TestModel",
        instance_type="g4dn.xlarge",
        gpu_type="T4",
        gpu_count=1,
        cloud_provider="aws",
        region="us-east-1",
    )
    assert "import pulumi" in code
    assert "pulumi_aws" in code
    assert "eks" in code.lower()


@pytest.mark.asyncio
async def test_service_monitoring_yaml():
    """Monitoring YAML includes ServiceMonitor and Grafana dashboard."""
    from app.services.infra_agent import generate_monitoring_yaml
    yaml_content = generate_monitoring_yaml("test-deployment-id")
    assert "ServiceMonitor" in yaml_content
    assert "grafana" in yaml_content.lower()
    assert "test-deployment-id" in yaml_content


# ═══════════════════════════════════════════════════════════════
# Agent tool integration
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_agent_tool_generate_infra():
    """The generate_infra agent tool works correctly."""
    import json
    from app.services.agent_tools import execute_tool
    result = json.loads(execute_tool("generate_infra", {
        "model_name": "Llama-3-8B",
        "parameters_billion": 8,
        "cloud_provider": "aws",
    }))
    assert "deployment_id" in result
    assert "files_generated" in result
    assert len(result["files_generated"]) > 0
    assert "summary" in result


@pytest.mark.asyncio
async def test_agent_tool_search_infra():
    """The search_infra agent tool works correctly."""
    import json
    from app.services.agent_tools import execute_tool
    result = json.loads(execute_tool("search_infra", {
        "query": "H100 gpu",
    }))
    assert "results" in result
    assert len(result["results"]) > 0
