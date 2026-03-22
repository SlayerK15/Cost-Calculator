"""
Infrastructure Agent Service.

Generates multi-cloud deployment files in the user's preferred IaC language.
Wraps DeploymentGenerator and extends it with Pulumi support and real-time
cloud instance/pricing search via the cost engine.
"""

import uuid
import textwrap
from typing import Optional

from app.services.deployment_generator import DeploymentGenerator, ModelPipeline
from app.services.cost_engine.calculator import estimate_cost
from app.services.cost_engine.gpu_catalog import GPU_SPECS
from app.schemas.infra import (
    InfraGenerateRequest,
    InfraGenerateResponse,
    InfraFileEntry,
    InfraSearchRequest,
    InfraSearchResponse,
    InfraSearchResult,
)

# Map cloud_provider to region defaults
DEFAULT_REGIONS = {
    "aws": "us-east-1",
    "gcp": "us-central1",
    "azure": "eastus",
}

# Map cloud_provider to instance type patterns
PROVIDER_INSTANCE_TYPES = {
    "aws": {
        "T4": "g4dn.xlarge",
        "A10G": "g5.xlarge",
        "A100_40GB": "p4d.24xlarge",
        "A100_80GB": "p4de.24xlarge",
        "H100": "p5.48xlarge",
        "L4": "g6.xlarge",
    },
    "gcp": {
        "T4": "n1-standard-4",
        "A100_40GB": "a2-highgpu-1g",
        "A100_80GB": "a2-ultragpu-1g",
        "H100": "a3-highgpu-1g",
        "L4": "g2-standard-4",
    },
    "azure": {
        "T4": "Standard_NC4as_T4_v3",
        "A10G": "Standard_NV36ads_A10_v5",
        "A100_40GB": "Standard_ND96asr_v4",
        "A100_80GB": "Standard_ND96amsr_A100_v4",
        "H100": "Standard_ND96isr_H100_v5",
    },
}

_generator = DeploymentGenerator()


def _resolve_gpu_and_instance(
    parameters_billion: float,
    precision: str,
    context_length: int,
    cloud_provider: str,
    gpu_count: int,
) -> tuple[str, str, float]:
    """Use the cost engine to find the best GPU/instance and monthly cost."""
    est = estimate_cost(
        parameters_billion=parameters_billion,
        precision=precision,
        context_length=context_length,
        cloud_provider=cloud_provider,
        expected_qps=1.0,
        hours_per_day=24,
        days_per_month=30,
    )
    if est:
        return est.gpu_type, est.instance_type, est.total_cost_monthly

    # Fallback: pick a reasonable GPU based on model size
    if parameters_billion <= 7:
        gpu = "T4"
    elif parameters_billion <= 13:
        gpu = "A10G" if cloud_provider != "gcp" else "L4"
    elif parameters_billion <= 40:
        gpu = "A100_40GB"
    elif parameters_billion <= 72:
        gpu = "A100_80GB"
    else:
        gpu = "H100"

    instance = PROVIDER_INSTANCE_TYPES.get(cloud_provider, {}).get(gpu, "unknown")
    return gpu, instance, 0.0


def generate_pulumi_python(
    deployment_id: str,
    model_name: str,
    instance_type: str,
    gpu_type: str,
    gpu_count: int,
    cloud_provider: str,
    region: str,
    replicas: int = 1,
    enable_autoscaling: bool = True,
    enable_monitoring: bool = True,
) -> str:
    """Generate Pulumi Python program for LLM deployment."""
    dep_short = deployment_id[:8]

    if cloud_provider == "aws":
        return textwrap.dedent(f'''\
            """Pulumi program — Deploy {model_name} on AWS EKS"""
            import pulumi
            import pulumi_aws as aws
            import pulumi_eks as eks
            import pulumi_kubernetes as k8s

            config = pulumi.Config()
            deployment_id = config.get("deploymentId") or "{deployment_id}"
            region = config.get("region") or "{region}"

            # ── VPC ──
            vpc = aws.ec2.Vpc("llm-vpc",
                cidr_block="10.0.0.0/16",
                enable_dns_hostnames=True,
                tags={{"Name": f"llm-{{deployment_id[:8]}}-vpc"}},
            )

            public_subnet_a = aws.ec2.Subnet("public-a",
                vpc_id=vpc.id,
                cidr_block="10.0.1.0/24",
                availability_zone=f"{{region}}a",
                map_public_ip_on_launch=True,
            )

            public_subnet_b = aws.ec2.Subnet("public-b",
                vpc_id=vpc.id,
                cidr_block="10.0.2.0/24",
                availability_zone=f"{{region}}b",
                map_public_ip_on_launch=True,
            )

            # ── EKS Cluster ──
            cluster = eks.Cluster("llm-cluster",
                vpc_id=vpc.id,
                subnet_ids=[public_subnet_a.id, public_subnet_b.id],
                instance_type="{instance_type}",
                desired_capacity={replicas},
                min_size=1,
                max_size={"10" if enable_autoscaling else str(replicas)},
                gpu=True,
            )

            # ── ECR Repository ──
            repo = aws.ecr.Repository("llm-repo",
                name=f"llm-{dep_short}",
                image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                    scan_on_push=True,
                ),
            )

            # ── S3 for model weights ──
            bucket = aws.s3.BucketV2("model-weights",
                bucket=f"llm-models-{dep_short}",
            )

            aws.s3.BucketServerSideEncryptionConfigurationV2("model-weights-enc",
                bucket=bucket.id,
                rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                    apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                        sse_algorithm="AES256",
                    ),
                )],
            )

            # ── K8s Deployment ──
            provider = k8s.Provider("k8s-provider",
                kubeconfig=cluster.kubeconfig,
            )

            ns = k8s.core.v1.Namespace("llm-ns",
                metadata=k8s.meta.v1.ObjectMetaArgs(name="llm-deployments"),
                opts=pulumi.ResourceOptions(provider=provider),
            )

            app_labels = {{"app": "llm-inference", "deployment-id": deployment_id}}

            deployment = k8s.apps.v1.Deployment("llm-deploy",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"llm-{dep_short}",
                    namespace="llm-deployments",
                ),
                spec=k8s.apps.v1.DeploymentSpecArgs(
                    replicas={replicas},
                    selector=k8s.meta.v1.LabelSelectorArgs(match_labels=app_labels),
                    template=k8s.core.v1.PodTemplateSpecArgs(
                        metadata=k8s.meta.v1.ObjectMetaArgs(labels=app_labels),
                        spec=k8s.core.v1.PodSpecArgs(
                            containers=[k8s.core.v1.ContainerArgs(
                                name="vllm-server",
                                image=pulumi.Output.concat(repo.repository_url, ":latest"),
                                ports=[k8s.core.v1.ContainerPortArgs(container_port=8000)],
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    limits={{"nvidia.com/gpu": "{gpu_count}"}},
                                    requests={{"nvidia.com/gpu": "{gpu_count}"}},
                                ),
                            )],
                        ),
                    ),
                ),
                opts=pulumi.ResourceOptions(provider=provider),
            )

            svc = k8s.core.v1.Service("llm-svc",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"llm-{dep_short}-svc",
                    namespace="llm-deployments",
                ),
                spec=k8s.core.v1.ServiceSpecArgs(
                    type="LoadBalancer",
                    selector=app_labels,
                    ports=[k8s.core.v1.ServicePortArgs(port=80, target_port=8000)],
                ),
                opts=pulumi.ResourceOptions(provider=provider),
            )

            # ── Exports ──
            pulumi.export("cluster_endpoint", cluster.eks_cluster.endpoint)
            pulumi.export("ecr_url", repo.repository_url)
            pulumi.export("service_ip", svc.status.load_balancer.ingress[0].ip)
        ''')

    elif cloud_provider == "gcp":
        return textwrap.dedent(f'''\
            """Pulumi program — Deploy {model_name} on GCP GKE"""
            import pulumi
            import pulumi_gcp as gcp
            import pulumi_kubernetes as k8s

            config = pulumi.Config()
            project = config.require("gcpProject")
            deployment_id = config.get("deploymentId") or "{deployment_id}"

            # ── GKE Cluster ──
            cluster = gcp.container.Cluster("llm-cluster",
                name=f"llm-{dep_short}",
                location="{region}",
                initial_node_count=1,
                remove_default_node_pool=True,
            )

            gpu_pool = gcp.container.NodePool("gpu-pool",
                cluster=cluster.name,
                location="{region}",
                node_count={replicas},
                autoscaling=gcp.container.NodePoolAutoscalingArgs(
                    min_node_count=1,
                    max_node_count={"10" if enable_autoscaling else str(replicas)},
                ),
                node_config=gcp.container.NodePoolNodeConfigArgs(
                    machine_type="{instance_type}",
                    oauth_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                    guest_accelerators=[gcp.container.NodePoolNodeConfigGuestAcceleratorArgs(
                        type="{gpu_type.lower().replace('_', '-')}",
                        count={gpu_count},
                    )],
                ),
            )

            # ── Artifact Registry ──
            repo = gcp.artifactregistry.Repository("llm-repo",
                location="{region}",
                repository_id=f"llm-{dep_short}",
                format="DOCKER",
            )

            # ── GCS Bucket ──
            bucket = gcp.storage.Bucket("model-weights",
                name=f"llm-models-{dep_short}",
                location="{region}",
                uniform_bucket_level_access=True,
            )

            pulumi.export("cluster_endpoint", cluster.endpoint)
            pulumi.export("registry_url", pulumi.Output.concat(
                "{region}-docker.pkg.dev/", project, "/", repo.repository_id
            ))
        ''')

    else:  # azure
        return textwrap.dedent(f'''\
            """Pulumi program — Deploy {model_name} on Azure AKS"""
            import pulumi
            import pulumi_azure_native as azure
            import pulumi_kubernetes as k8s

            config = pulumi.Config()
            deployment_id = config.get("deploymentId") or "{deployment_id}"

            # ── Resource Group ──
            rg = azure.resources.ResourceGroup("llm-rg",
                resource_group_name=f"llm-{dep_short}-rg",
                location="{region}",
            )

            # ── AKS Cluster ──
            cluster = azure.containerservice.ManagedCluster("llm-cluster",
                resource_group_name=rg.name,
                resource_name_=f"llm-{dep_short}",
                location=rg.location,
                dns_prefix=f"llm-{dep_short}",
                agent_pool_profiles=[
                    azure.containerservice.ManagedClusterAgentPoolProfileArgs(
                        name="default",
                        count=1,
                        vm_size="Standard_DS2_v2",
                        mode="System",
                    ),
                    azure.containerservice.ManagedClusterAgentPoolProfileArgs(
                        name="gpupool",
                        count={replicas},
                        vm_size="{instance_type}",
                        mode="User",
                        min_count=1,
                        max_count={"10" if enable_autoscaling else str(replicas)},
                        enable_auto_scaling={enable_autoscaling},
                        node_taints=["nvidia.com/gpu=present:NoSchedule"],
                    ),
                ],
                identity=azure.containerservice.ManagedClusterIdentityArgs(
                    type=azure.containerservice.ResourceIdentityType.SYSTEM_ASSIGNED,
                ),
            )

            # ── Container Registry ──
            acr = azure.containerregistry.Registry("llm-acr",
                resource_group_name=rg.name,
                registry_name=f"llm{dep_short.replace('-', '')}",
                location=rg.location,
                sku=azure.containerregistry.SkuArgs(name="Standard"),
                admin_user_enabled=True,
            )

            pulumi.export("cluster_name", cluster.name)
            pulumi.export("acr_login_server", acr.login_server)
        ''')


def generate_pulumi_project_yaml(cloud_provider: str) -> str:
    """Generate Pulumi.yaml project definition."""
    runtime_config = {
        "aws": "name: llm-deploy-aws\nruntime: python\ndescription: LLM Deployment on AWS EKS",
        "gcp": "name: llm-deploy-gcp\nruntime: python\ndescription: LLM Deployment on GCP GKE",
        "azure": "name: llm-deploy-azure\nruntime: python\ndescription: LLM Deployment on Azure AKS",
    }
    return runtime_config.get(cloud_provider, runtime_config["aws"])


def generate_pulumi_requirements(cloud_provider: str) -> str:
    """Generate requirements.txt for Pulumi project."""
    base = "pulumi>=3.0.0\npulumi-kubernetes>=4.0.0\n"
    extra = {
        "aws": "pulumi-aws>=6.0.0\npulumi-eks>=2.0.0\n",
        "gcp": "pulumi-gcp>=7.0.0\n",
        "azure": "pulumi-azure-native>=2.0.0\n",
    }
    return base + extra.get(cloud_provider, "")


def generate_monitoring_yaml(
    deployment_id: str,
    namespace: str = "llm-deployments",
) -> str:
    """Generate Prometheus ServiceMonitor + Grafana dashboard ConfigMap."""
    dep_short = deployment_id[:8]
    return textwrap.dedent(f"""\
        # Prometheus ServiceMonitor
        apiVersion: monitoring.coreos.com/v1
        kind: ServiceMonitor
        metadata:
          name: llm-{dep_short}-monitor
          namespace: {namespace}
          labels:
            app: llm-inference
        spec:
          selector:
            matchLabels:
              app: llm-inference
              deployment-id: "{deployment_id}"
          endpoints:
          - port: http
            path: /metrics
            interval: 15s
        ---
        # Grafana Dashboard ConfigMap
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: llm-{dep_short}-dashboard
          namespace: {namespace}
          labels:
            grafana_dashboard: "1"
        data:
          llm-dashboard.json: |
            {{
              "dashboard": {{
                "title": "LLM Inference - {dep_short}",
                "panels": [
                  {{
                    "title": "GPU Utilization",
                    "targets": [{{"expr": "nvidia_gpu_utilization{{deployment_id=\\"{deployment_id}\\"}}"}}"}}]
                  }},
                  {{
                    "title": "Request Latency (p99)",
                    "targets": [{{"expr": "histogram_quantile(0.99, rate(vllm_request_duration_seconds_bucket{{deployment_id=\\"{deployment_id}\\"}}[5m]))"}}]
                  }},
                  {{
                    "title": "Tokens/Second",
                    "targets": [{{"expr": "rate(vllm_tokens_generated_total{{deployment_id=\\"{deployment_id}\\"}}[5m])"}}]
                  }}
                ]
              }}
            }}
    """)


def search_cloud_infra(req: InfraSearchRequest) -> InfraSearchResponse:
    """
    Search internal knowledge base for cloud GPU instances, pricing,
    and deployment best practices. Uses the cost engine's GPU catalog
    and instance type mappings.
    """
    query_lower = req.query.lower()
    results: list[InfraSearchResult] = []

    # Search GPU specs
    for gpu_name, spec in GPU_SPECS.items():
        name_lower = gpu_name.lower()
        if any(q in name_lower for q in query_lower.split()):
            results.append(InfraSearchResult(
                source="gpu_catalog",
                title=f"{spec.name} GPU",
                snippet=(
                    f"VRAM: {spec.vram_gb}GB | FP16 TFLOPS: {spec.fp16_tflops} | "
                    f"Memory Bandwidth: {spec.memory_bandwidth_gbps} GB/s"
                ),
                relevance=0.95,
            ))

    # Search instance types
    providers_to_search = [req.cloud_provider] if req.cloud_provider else ["aws", "gcp", "azure"]
    for provider in providers_to_search:
        mapping = PROVIDER_INSTANCE_TYPES.get(provider, {})
        for gpu_name, instance in mapping.items():
            if (
                any(q in gpu_name.lower() for q in query_lower.split())
                or any(q in instance.lower() for q in query_lower.split())
                or provider in query_lower
            ):
                spec = GPU_SPECS.get(gpu_name)
                vram = spec.vram_gb if spec else "?"
                results.append(InfraSearchResult(
                    source=f"{provider}_instances",
                    title=f"{provider.upper()} — {instance} ({gpu_name})",
                    snippet=f"Instance: {instance} | GPU: {gpu_name} ({vram}GB VRAM) | Provider: {provider.upper()}",
                    relevance=0.85,
                ))

    # Search for pricing keywords
    if any(w in query_lower for w in ["price", "pricing", "cost", "cheap", "budget", "expensive"]):
        for provider in providers_to_search:
            est_7b = estimate_cost(7.0, "fp16", 4096, provider)
            est_70b = estimate_cost(70.0, "fp16", 4096, provider)
            if est_7b:
                results.append(InfraSearchResult(
                    source=f"{provider}_pricing",
                    title=f"{provider.upper()} — 7B Model Pricing",
                    snippet=f"~${est_7b.total_cost_monthly:,.0f}/mo on {est_7b.instance_type} ({est_7b.gpu_type})",
                    relevance=0.80,
                ))
            if est_70b:
                results.append(InfraSearchResult(
                    source=f"{provider}_pricing",
                    title=f"{provider.upper()} — 70B Model Pricing",
                    snippet=f"~${est_70b.total_cost_monthly:,.0f}/mo on {est_70b.instance_type} ({est_70b.gpu_type})",
                    relevance=0.80,
                ))

    # Terraform / IaC best practices
    if any(w in query_lower for w in ["terraform", "iac", "infrastructure", "best practice", "pulumi", "cloudformation"]):
        results.append(InfraSearchResult(
            source="best_practices",
            title="IaC Best Practices for LLM Deployment",
            snippet=(
                "Use remote state (S3/GCS/Azure Blob). Enable state locking. "
                "Pin provider versions. Use modules for reusability. "
                "Separate environments with workspaces or directories. "
                "Always use GPU-specific node pools with taints/tolerations."
            ),
            relevance=0.75,
        ))

    if not results:
        results.append(InfraSearchResult(
            source="general",
            title="No exact match",
            snippet=(
                f"No results for '{req.query}'. Try searching for GPU types "
                "(A100, H100, T4), cloud providers (aws, gcp, azure), or "
                "keywords like 'pricing', 'terraform', 'instance types'."
            ),
            relevance=0.1,
        ))

    # Sort by relevance
    results.sort(key=lambda r: r.relevance, reverse=True)
    return InfraSearchResponse(query=req.query, results=results[:10])


def generate_infra(req: InfraGenerateRequest) -> InfraGenerateResponse:
    """
    Main entry point: generate all deployment files for the requested
    cloud provider and IaC language.
    """
    deployment_id = str(uuid.uuid4())
    dep_short = deployment_id[:8]
    region = req.region or DEFAULT_REGIONS.get(req.cloud_provider, "us-east-1")

    gpu_type, instance_type, monthly_cost = _resolve_gpu_and_instance(
        req.parameters_billion, req.precision, req.context_length,
        req.cloud_provider, req.gpu_count,
    )

    files: list[InfraFileEntry] = []

    # 1. Always generate Dockerfile
    dockerfile = _generator.generate_dockerfile(
        req.model_name, req.gpu_count, req.context_length, req.precision,
    )
    files.append(InfraFileEntry(filename="Dockerfile", content=dockerfile, language="dockerfile"))

    # 2. Always generate K8s YAML
    k8s_yaml = _generator.generate_kubernetes_yaml(
        deployment_id, req.model_name, instance_type, gpu_type, req.gpu_count,
        replicas=req.replicas,
    )
    files.append(InfraFileEntry(filename="kubernetes.yaml", content=k8s_yaml, language="yaml"))

    # 3. Generate IaC files based on language choice
    iac = req.iac_language.lower()

    if iac == "terraform":
        if req.cloud_provider == "aws":
            tf = _generator.generate_terraform_aws(deployment_id, instance_type, region, req.gpu_count)
        elif req.cloud_provider == "gcp":
            gpu_gcp = gpu_type.lower().replace("_", "-").replace("gb", "")
            tf = _generator.generate_terraform_gcp(deployment_id, instance_type, region, gpu_gcp, req.gpu_count)
        elif req.cloud_provider == "azure":
            tf = _generator.generate_terraform_azure(deployment_id, instance_type, region)
        else:
            tf = "# Unsupported provider for Terraform"
        files.append(InfraFileEntry(filename="main.tf", content=tf, language="terraform"))

    elif iac == "cloudformation":
        if req.cloud_provider == "aws":
            cfn = _generator.generate_cloudformation(
                deployment_id, instance_type, gpu_type, req.gpu_count, req.model_name, region,
            )
            files.append(InfraFileEntry(filename="cloudformation.yaml", content=cfn, language="yaml"))
        else:
            files.append(InfraFileEntry(
                filename="cloudformation.yaml",
                content=f"# CloudFormation is only available for AWS. Selected provider: {req.cloud_provider}\n# Falling back to Terraform.\n",
                language="yaml",
            ))
            # Fallback to terraform
            if req.cloud_provider == "gcp":
                gpu_gcp = gpu_type.lower().replace("_", "-").replace("gb", "")
                tf = _generator.generate_terraform_gcp(deployment_id, instance_type, region, gpu_gcp, req.gpu_count)
            else:
                tf = _generator.generate_terraform_azure(deployment_id, instance_type, region)
            files.append(InfraFileEntry(filename="main.tf", content=tf, language="terraform"))

    elif iac == "pulumi":
        pulumi_code = generate_pulumi_python(
            deployment_id, req.model_name, instance_type, gpu_type, req.gpu_count,
            req.cloud_provider, region, req.replicas, req.enable_autoscaling, req.enable_monitoring,
        )
        files.append(InfraFileEntry(filename="__main__.py", content=pulumi_code, language="python"))
        files.append(InfraFileEntry(
            filename="Pulumi.yaml",
            content=generate_pulumi_project_yaml(req.cloud_provider),
            language="yaml",
        ))
        files.append(InfraFileEntry(
            filename="requirements.txt",
            content=generate_pulumi_requirements(req.cloud_provider),
            language="text",
        ))

    elif iac == "kubernetes":
        # Already generated K8s YAML above — no additional IaC files needed
        pass

    else:
        files.append(InfraFileEntry(
            filename="README.md",
            content=f"# Unsupported IaC language: {req.iac_language}\nSupported: terraform, cloudformation, pulumi, kubernetes\n",
            language="text",
        ))

    # 4. CI/CD pipeline
    ci_cd = _generator.generate_ci_cd_pipeline(deployment_id, req.cloud_provider, req.model_name)
    files.append(InfraFileEntry(filename=".github/workflows/deploy.yaml", content=ci_cd, language="yaml"))

    # 5. Monitoring (optional)
    if req.enable_monitoring:
        monitoring = generate_monitoring_yaml(deployment_id)
        files.append(InfraFileEntry(filename="monitoring.yaml", content=monitoring, language="yaml"))

    # 6. Quickstart instructions
    quickstart = _generator.generate_quickstart_instructions(
        req.cloud_provider, deployment_id, req.model_name, instance_type, gpu_type, region,
    )
    files.append(InfraFileEntry(filename="QUICKSTART.sh", content=quickstart, language="bash"))

    summary = (
        f"Generated {len(files)} deployment files for {req.model_name} "
        f"({req.parameters_billion}B, {req.precision}) on {req.cloud_provider.upper()} "
        f"using {req.iac_language}. "
        f"Instance: {instance_type} with {gpu_type} x{req.gpu_count}. "
        f"Region: {region}."
    )
    if monthly_cost > 0:
        summary += f" Estimated cost: ${monthly_cost:,.0f}/mo."

    return InfraGenerateResponse(
        deployment_id=deployment_id,
        cloud_provider=req.cloud_provider,
        iac_language=req.iac_language,
        region=region,
        instance_type=instance_type,
        gpu_type=gpu_type,
        gpu_count=req.gpu_count,
        estimated_monthly_cost=monthly_cost,
        files=files,
        quickstart=quickstart,
        summary=summary,
    )
