"""
Deployment Config Generator.

Generates:
- Dockerfiles for vLLM inference (LoRA/merge/quantization-aware)
- Kubernetes deployment YAML
- Terraform configurations for AWS/GCP/Azure
- CI/CD pipeline configs
"""

import textwrap
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelPipeline:
    """Describes how a composed model should be built before serving."""
    base_model_hf_id: str
    adapter_hf_id: Optional[str] = None
    is_merge: bool = False
    merge_method: Optional[str] = None  # linear, slerp, ties, dare
    merge_models: list[dict] = field(default_factory=list)  # [{model_hf_id, weight}]
    quantization_method: str = "none"  # none, gptq, awq, bnb_int8, bnb_int4
    system_prompt: Optional[str] = None
    default_temperature: float = 0.7
    default_max_tokens: int = 512


QUANT_TO_VLLM_FLAG = {
    "gptq": "--quantization gptq",
    "awq": "--quantization awq",
    "bnb_int8": "--quantization bitsandbytes",
    "bnb_int4": "--quantization bitsandbytes",
}

QUANT_TO_DTYPE = {
    "none": "auto",
    "gptq": "float16",
    "awq": "float16",
    "bnb_int8": "float16",
    "bnb_int4": "float16",
}


class DeploymentGenerator:

    def generate_dockerfile(
        self,
        model_id: str,
        gpu_count: int = 1,
        context_length: int = 4096,
        precision: str = "fp16",
        is_custom_upload: bool = False,
        pipeline: Optional[ModelPipeline] = None,
    ) -> str:
        # If we have a pipeline from model builder, use its settings
        if pipeline:
            return self._generate_pipeline_dockerfile(
                pipeline, gpu_count, context_length
            )

        dtype_flag = "float16" if precision in ("fp16",) else "bfloat16" if precision == "bf16" else "auto"
        quantization_flag = ""
        if precision == "int8":
            quantization_flag = "--quantization squeezellm"
        elif precision == "int4":
            quantization_flag = "--quantization awq"

        model_source = "/models/custom" if is_custom_upload else model_id
        tp_flag = f"--tensor-parallel-size {gpu_count}" if gpu_count > 1 else ""

        copy_line = "COPY ./model_weights /models/custom" if is_custom_upload else "# Using HuggingFace model directly"

        # Build entrypoint args
        entrypoint_args = [
            '"python", "-m", "vllm.entrypoints.openai.api_server"',
            f'"--model", "$MODEL_ID"',
            f'"--max-model-len", "{context_length}"',
            '"--dtype", "$DTYPE"',
        ]
        if quantization_flag:
            entrypoint_args.append(f'"{quantization_flag}"')
        if tp_flag:
            entrypoint_args.append(f'"{tp_flag}"')
        entrypoint_args.extend(['"--host", "0.0.0.0"', '"--port", "8000"'])

        formatted_args = ", \\\n                ".join(entrypoint_args)

        lines = [
            "FROM vllm/vllm-openai:latest",
            "",
            f'ENV MODEL_ID="{model_source}"',
            f"ENV MAX_MODEL_LEN={context_length}",
            f"ENV DTYPE={dtype_flag}",
            "",
            f"# Model weights",
            copy_line,
            "",
            "EXPOSE 8000",
            "",
            f"ENTRYPOINT [{formatted_args}]",
        ]
        return "\n".join(lines) + "\n"

    def _generate_pipeline_dockerfile(
        self,
        pipeline: ModelPipeline,
        gpu_count: int,
        context_length: int,
    ) -> str:
        """Generate Dockerfile for a composed model (with merge/LoRA/quantization)."""
        qmethod = pipeline.quantization_method or "none"
        dtype = QUANT_TO_DTYPE.get(qmethod, "auto")
        quant_flag = QUANT_TO_VLLM_FLAG.get(qmethod, "")
        tp_flag = f"--tensor-parallel-size {gpu_count}" if gpu_count > 1 else ""
        lora_flag = ""

        sections = []
        sections.append("FROM vllm/vllm-openai:latest")
        sections.append("")

        if pipeline.is_merge and pipeline.merge_models:
            # Merge pipeline: uses mergekit at build time
            sections.append("# ── Build stage: merge models with mergekit ──")
            sections.append("RUN pip install mergekit")
            sections.append("")
            sections.append("# Copy merge config (generated in bundle)")
            sections.append("COPY merge_config.yaml /tmp/merge_config.yaml")
            sections.append("")
            sections.append("# Run merge at build time")
            sections.append(
                "RUN mergekit-yaml /tmp/merge_config.yaml /models/merged "
                "--clone-tensors --lazy-unpickle"
            )
            sections.append("")
            model_source = "/models/merged"
        else:
            model_source = pipeline.base_model_hf_id

        if pipeline.adapter_hf_id and not pipeline.is_merge:
            # LoRA: vLLM supports --enable-lora at runtime
            lora_flag = (
                f'--enable-lora --lora-modules adapter={pipeline.adapter_hf_id}'
            )

        sections.append(f'ENV MODEL_ID="{model_source}"')
        sections.append(f"ENV MAX_MODEL_LEN={context_length}")
        sections.append(f"ENV DTYPE={dtype}")
        sections.append("")
        sections.append("EXPOSE 8000")
        sections.append("")

        # Build entrypoint
        args = [
            '"python", "-m", "vllm.entrypoints.openai.api_server"',
            '"--model", "$MODEL_ID"',
            '"--max-model-len", "$MAX_MODEL_LEN"',
            '"--dtype", "$DTYPE"',
        ]
        if quant_flag:
            args.append(f'"{quant_flag}"')
        if tp_flag:
            args.append(f'"{tp_flag}"')
        if lora_flag:
            for part in lora_flag.split(" "):
                pass
            args.append(f'"--enable-lora"')
            args.append(f'"--lora-modules", "adapter={pipeline.adapter_hf_id}"')
        args.extend(['"--host", "0.0.0.0"', '"--port", "8000"'])

        formatted_args = ", \\\n                ".join(args)
        sections.append(f"ENTRYPOINT [{formatted_args}]")

        return "\n".join(sections) + "\n"

    def generate_merge_config(self, pipeline: ModelPipeline) -> str:
        """Generate a mergekit YAML config for model merging."""
        if not pipeline.is_merge or not pipeline.merge_models:
            return ""

        method = (pipeline.merge_method or "slerp").lower()
        lines = [
            f"merge_method: {method}",
            "slices:",
            "  - sources:",
        ]

        for entry in pipeline.merge_models:
            lines.append(f"      - model: {entry.get('model_hf_id', 'unknown')}")
            lines.append(f"        layer_range: [0, 32]")

        if method == "slerp":
            lines.append("parameters:")
            lines.append("  t:")
            lines.append("    - filter: self_attn")
            w = pipeline.merge_models[0].get("weight", 0.5) if pipeline.merge_models else 0.5
            lines.append(f"      value: {w}")
            lines.append("    - filter: mlp")
            lines.append(f"      value: {1 - w}")
            lines.append(f"    - value: 0.5")
        elif method in ("ties", "dare"):
            lines.append("parameters:")
            lines.append("  density: 0.5")
            lines.append(f"  weight:")
            for entry in pipeline.merge_models:
                lines.append(f"    - value: {entry.get('weight', 0.5)}")

        lines.append(f"base_model: {pipeline.base_model_hf_id}")
        lines.append(f"dtype: float16")

        return "\n".join(lines) + "\n"

    def generate_kubernetes_yaml(
        self,
        deployment_id: str,
        model_name: str,
        instance_type: str,
        gpu_type: str,
        gpu_count: int,
        replicas: int = 1,
        namespace: str = "llm-deployments",
    ) -> str:
        gpu_resource_key = "nvidia.com/gpu"
        return textwrap.dedent(f"""\
            apiVersion: v1
            kind: Namespace
            metadata:
              name: {namespace}
            ---
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: llm-{deployment_id[:8]}
              namespace: {namespace}
              labels:
                app: llm-inference
                deployment-id: "{deployment_id}"
            spec:
              replicas: {replicas}
              selector:
                matchLabels:
                  app: llm-inference
                  deployment-id: "{deployment_id}"
              template:
                metadata:
                  labels:
                    app: llm-inference
                    deployment-id: "{deployment_id}"
                spec:
                  containers:
                  - name: vllm-server
                    image: llm-platform/{model_name}:latest
                    ports:
                    - containerPort: 8000
                    resources:
                      limits:
                        {gpu_resource_key}: "{gpu_count}"
                        memory: "64Gi"
                      requests:
                        {gpu_resource_key}: "{gpu_count}"
                        memory: "32Gi"
                    readinessProbe:
                      httpGet:
                        path: /health
                        port: 8000
                      initialDelaySeconds: 120
                      periodSeconds: 10
                    livenessProbe:
                      httpGet:
                        path: /health
                        port: 8000
                      initialDelaySeconds: 180
                      periodSeconds: 30
                    env:
                    - name: HUGGING_FACE_HUB_TOKEN
                      valueFrom:
                        secretKeyRef:
                          name: hf-token
                          key: token
                          optional: true
                  nodeSelector:
                    cloud.google.com/gke-accelerator: "{gpu_type.lower().replace('_', '-')}"
                  tolerations:
                  - key: nvidia.com/gpu
                    operator: Exists
                    effect: NoSchedule
            ---
            apiVersion: v1
            kind: Service
            metadata:
              name: llm-{deployment_id[:8]}-svc
              namespace: {namespace}
            spec:
              type: ClusterIP
              selector:
                app: llm-inference
                deployment-id: "{deployment_id}"
              ports:
              - port: 80
                targetPort: 8000
                protocol: TCP
            ---
            apiVersion: autoscaling/v2
            kind: HorizontalPodAutoscaler
            metadata:
              name: llm-{deployment_id[:8]}-hpa
              namespace: {namespace}
            spec:
              scaleTargetRef:
                apiVersion: apps/v1
                kind: Deployment
                name: llm-{deployment_id[:8]}
              minReplicas: 1
              maxReplicas: 10
              metrics:
              - type: Resource
                resource:
                  name: cpu
                  target:
                    type: Utilization
                    averageUtilization: 70
              - type: Pods
                pods:
                  metric:
                    name: gpu_utilization
                  target:
                    type: AverageValue
                    averageValue: "80"
        """)

    def generate_terraform_aws(
        self,
        deployment_id: str,
        instance_type: str,
        region: str = "us-east-1",
        gpu_count: int = 1,
    ) -> str:
        return textwrap.dedent(f"""\
            terraform {{
              required_providers {{
                aws = {{
                  source  = "hashicorp/aws"
                  version = "~> 5.0"
                }}
              }}
            }}

            provider "aws" {{
              region = "{region}"
            }}

            variable "deployment_id" {{
              default = "{deployment_id}"
            }}

            # ── VPC ──
            module "vpc" {{
              source  = "terraform-aws-modules/vpc/aws"
              version = "~> 5.0"

              name = "llm-${{var.deployment_id}}-vpc"
              cidr = "10.0.0.0/16"

              azs             = ["{region}a", "{region}b"]
              private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
              public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

              enable_nat_gateway = true
              single_nat_gateway = true
            }}

            # ── EKS Cluster ──
            module "eks" {{
              source  = "terraform-aws-modules/eks/aws"
              version = "~> 20.0"

              cluster_name    = "llm-${{var.deployment_id}}"
              cluster_version = "1.29"

              vpc_id     = module.vpc.vpc_id
              subnet_ids = module.vpc.private_subnets

              eks_managed_node_groups = {{
                gpu_nodes = {{
                  instance_types = ["{instance_type}"]
                  min_size       = 1
                  max_size       = 5
                  desired_size   = 1

                  ami_type = "AL2_x86_64_GPU"

                  labels = {{
                    "workload" = "llm-inference"
                  }}

                  taints = [{{
                    key    = "nvidia.com/gpu"
                    value  = "true"
                    effect = "NO_SCHEDULE"
                  }}]
                }}
              }}
            }}

            # ── ECR Repository ──
            resource "aws_ecr_repository" "llm_repo" {{
              name                 = "llm-${{var.deployment_id}}"
              image_tag_mutability = "MUTABLE"
              force_delete         = true

              image_scanning_configuration {{
                scan_on_push = true
              }}
            }}

            # ── S3 Bucket for Model Weights ──
            resource "aws_s3_bucket" "model_weights" {{
              bucket        = "llm-models-${{var.deployment_id}}"
              force_destroy = true
            }}

            resource "aws_s3_bucket_server_side_encryption_configuration" "model_weights" {{
              bucket = aws_s3_bucket.model_weights.id
              rule {{
                apply_server_side_encryption_by_default {{
                  sse_algorithm = "AES256"
                }}
              }}
            }}

            # ── IAM Role for GPU Nodes ──
            resource "aws_iam_role" "gpu_node_role" {{
              name = "llm-gpu-node-${{var.deployment_id}}"

              assume_role_policy = jsonencode({{
                Version = "2012-10-17"
                Statement = [{{
                  Action = "sts:AssumeRole"
                  Effect = "Allow"
                  Principal = {{
                    Service = "ec2.amazonaws.com"
                  }}
                }}]
              }})
            }}

            output "cluster_endpoint" {{
              value = module.eks.cluster_endpoint
            }}

            output "ecr_repository_url" {{
              value = aws_ecr_repository.llm_repo.repository_url
            }}

            output "model_bucket" {{
              value = aws_s3_bucket.model_weights.bucket
            }}
        """)

    def generate_terraform_gcp(
        self,
        deployment_id: str,
        machine_type: str,
        region: str = "us-central1",
        gpu_type: str = "nvidia-l4",
        gpu_count: int = 1,
    ) -> str:
        return textwrap.dedent(f"""\
            terraform {{
              required_providers {{
                google = {{
                  source  = "hashicorp/google"
                  version = "~> 5.0"
                }}
              }}
            }}

            variable "project_id" {{
              description = "GCP project ID"
              type        = string
            }}

            variable "deployment_id" {{
              default = "{deployment_id}"
            }}

            provider "google" {{
              project = var.project_id
              region  = "{region}"
            }}

            # ── GKE Cluster ──
            resource "google_container_cluster" "llm_cluster" {{
              name     = "llm-${{var.deployment_id}}"
              location = "{region}"

              initial_node_count       = 1
              remove_default_node_pool = true

              networking_mode = "VPC_NATIVE"
              ip_allocation_policy {{}}
            }}

            resource "google_container_node_pool" "gpu_pool" {{
              name       = "gpu-pool"
              cluster    = google_container_cluster.llm_cluster.name
              location   = "{region}"
              node_count = 1

              autoscaling {{
                min_node_count = 1
                max_node_count = 5
              }}

              node_config {{
                machine_type = "{machine_type}"
                oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

                guest_accelerator {{
                  type  = "{gpu_type}"
                  count = {gpu_count}
                  gpu_sharing_config {{
                    gpu_sharing_strategy = "TIME_SHARING"
                    max_shared_clients_per_gpu = 2
                  }}
                }}

                taint {{
                  key    = "nvidia.com/gpu"
                  value  = "present"
                  effect = "NO_SCHEDULE"
                }}
              }}
            }}

            # ── Artifact Registry ──
            resource "google_artifact_registry_repository" "llm_repo" {{
              location      = "{region}"
              repository_id = "llm-${{var.deployment_id}}"
              format        = "DOCKER"
            }}

            # ── GCS Bucket ──
            resource "google_storage_bucket" "model_weights" {{
              name          = "llm-models-${{var.deployment_id}}"
              location      = "{region}"
              force_destroy = true
              uniform_bucket_level_access = true
            }}

            output "cluster_endpoint" {{
              value = google_container_cluster.llm_cluster.endpoint
            }}

            output "registry_url" {{
              value = "${{google_artifact_registry_repository.llm_repo.location}}-docker.pkg.dev/${{var.project_id}}/${{google_artifact_registry_repository.llm_repo.repository_id}}"
            }}
        """)

    def generate_terraform_azure(
        self,
        deployment_id: str,
        vm_size: str,
        region: str = "eastus",
    ) -> str:
        return textwrap.dedent(f"""\
            terraform {{
              required_providers {{
                azurerm = {{
                  source  = "hashicorp/azurerm"
                  version = "~> 3.0"
                }}
              }}
            }}

            provider "azurerm" {{
              features {{}}
            }}

            variable "deployment_id" {{
              default = "{deployment_id}"
            }}

            # ── Resource Group ──
            resource "azurerm_resource_group" "llm_rg" {{
              name     = "llm-${{var.deployment_id}}-rg"
              location = "{region}"
            }}

            # ── AKS Cluster ──
            resource "azurerm_kubernetes_cluster" "llm_cluster" {{
              name                = "llm-${{var.deployment_id}}"
              location            = azurerm_resource_group.llm_rg.location
              resource_group_name = azurerm_resource_group.llm_rg.name
              dns_prefix          = "llm-${{var.deployment_id}}"

              default_node_pool {{
                name       = "default"
                node_count = 1
                vm_size    = "Standard_DS2_v2"
              }}

              identity {{
                type = "SystemAssigned"
              }}
            }}

            resource "azurerm_kubernetes_cluster_node_pool" "gpu_pool" {{
              name                  = "gpupool"
              kubernetes_cluster_id = azurerm_kubernetes_cluster.llm_cluster.id
              vm_size               = "{vm_size}"
              node_count            = 1
              min_count             = 1
              max_count             = 5
              enable_auto_scaling   = true

              node_taints = ["nvidia.com/gpu=present:NoSchedule"]

              node_labels = {{
                "workload" = "llm-inference"
              }}
            }}

            # ── Container Registry ──
            resource "azurerm_container_registry" "llm_acr" {{
              name                = "llm${{replace(var.deployment_id, "-", "")}}"
              resource_group_name = azurerm_resource_group.llm_rg.name
              location            = azurerm_resource_group.llm_rg.location
              sku                 = "Standard"
              admin_enabled       = true
            }}

            # ── Storage Account ──
            resource "azurerm_storage_account" "model_storage" {{
              name                     = "llmmodels${{substr(replace(var.deployment_id, "-", ""), 0, 12)}}"
              resource_group_name      = azurerm_resource_group.llm_rg.name
              location                 = azurerm_resource_group.llm_rg.location
              account_tier             = "Standard"
              account_replication_type = "LRS"
            }}

            output "cluster_name" {{
              value = azurerm_kubernetes_cluster.llm_cluster.name
            }}

            output "acr_login_server" {{
              value = azurerm_container_registry.llm_acr.login_server
            }}
        """)

    def generate_ci_cd_pipeline(
        self,
        deployment_id: str,
        cloud_provider: str,
        model_name: str,
    ) -> str:
        return textwrap.dedent(f"""\
            name: Deploy LLM - {model_name}

            on:
              push:
                branches: [main]
              workflow_dispatch:

            env:
              DEPLOYMENT_ID: "{deployment_id}"
              CLOUD_PROVIDER: "{cloud_provider}"

            jobs:
              build-and-push:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4

                  - name: Set up Docker Buildx
                    uses: docker/setup-buildx-action@v3

                  - name: Build Docker image
                    run: |
                      docker build -t llm-{model_name}:${{{{ github.sha }}}} .
                      docker tag llm-{model_name}:${{{{ github.sha }}}} llm-{model_name}:latest

                  - name: Push to registry
                    run: |
                      # Push to cloud-specific registry
                      echo "Pushing to {cloud_provider} container registry..."
                      docker push llm-{model_name}:latest

              deploy:
                needs: build-and-push
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4

                  - name: Setup Terraform
                    uses: hashicorp/setup-terraform@v3

                  - name: Terraform Init
                    working-directory: ./infra/{cloud_provider}
                    run: terraform init

                  - name: Terraform Apply
                    working-directory: ./infra/{cloud_provider}
                    run: terraform apply -auto-approve

                  - name: Deploy to Kubernetes
                    run: |
                      kubectl apply -f k8s/deployment.yaml
                      kubectl rollout status deployment/llm-{deployment_id[:8]} -n llm-deployments --timeout=600s

              health-check:
                needs: deploy
                runs-on: ubuntu-latest
                steps:
                  - name: Wait for service
                    run: sleep 60

                  - name: Health check
                    run: |
                      ENDPOINT=$(kubectl get svc llm-{deployment_id[:8]}-svc -n llm-deployments -o jsonpath='{{.status.loadBalancer.ingress[0].ip}}')
                      curl -sf http://$ENDPOINT/health || exit 1
                      echo "Deployment healthy!"
        """)

    def generate_cloudformation(
        self,
        deployment_id: str,
        instance_type: str,
        gpu_type: str,
        gpu_count: int,
        model_name: str,
        region: str = "us-east-1",
    ) -> str:
        return textwrap.dedent(f"""\
            AWSTemplateFormatVersion: "2010-09-09"
            Description: "LLM Deployment Stack - {model_name}"

            Parameters:
              DeploymentId:
                Type: String
                Default: "{deployment_id}"
              ClusterName:
                Type: String
                Default: "llm-{deployment_id[:8]}"
              InstanceType:
                Type: String
                Default: "{instance_type}"
                Description: "EC2 instance type for GPU nodes"
              DesiredCapacity:
                Type: Number
                Default: 1
              MaxSize:
                Type: Number
                Default: 5

            Resources:
              # ── VPC ──
              VPC:
                Type: AWS::EC2::VPC
                Properties:
                  CidrBlock: "10.0.0.0/16"
                  EnableDnsSupport: true
                  EnableDnsHostnames: true
                  Tags:
                    - Key: Name
                      Value: !Sub "llm-${{DeploymentId}}-vpc"

              PublicSubnetA:
                Type: AWS::EC2::Subnet
                Properties:
                  VpcId: !Ref VPC
                  CidrBlock: "10.0.1.0/24"
                  AvailabilityZone: !Sub "${{AWS::Region}}a"
                  MapPublicIpOnLaunch: true

              PublicSubnetB:
                Type: AWS::EC2::Subnet
                Properties:
                  VpcId: !Ref VPC
                  CidrBlock: "10.0.2.0/24"
                  AvailabilityZone: !Sub "${{AWS::Region}}b"
                  MapPublicIpOnLaunch: true

              InternetGateway:
                Type: AWS::EC2::InternetGateway

              VPCGatewayAttachment:
                Type: AWS::EC2::VPCGatewayAttachment
                Properties:
                  VpcId: !Ref VPC
                  InternetGatewayId: !Ref InternetGateway

              # ── EKS Cluster ──
              EKSClusterRole:
                Type: AWS::IAM::Role
                Properties:
                  AssumeRolePolicyDocument:
                    Version: "2012-10-17"
                    Statement:
                      - Effect: Allow
                        Principal:
                          Service: eks.amazonaws.com
                        Action: sts:AssumeRole
                  ManagedPolicyArns:
                    - arn:aws:iam::aws:policy/AmazonEKSClusterPolicy

              EKSCluster:
                Type: AWS::EKS::Cluster
                Properties:
                  Name: !Ref ClusterName
                  Version: "1.29"
                  RoleArn: !GetAtt EKSClusterRole.Arn
                  ResourcesVpcConfig:
                    SubnetIds:
                      - !Ref PublicSubnetA
                      - !Ref PublicSubnetB

              NodeRole:
                Type: AWS::IAM::Role
                Properties:
                  AssumeRolePolicyDocument:
                    Version: "2012-10-17"
                    Statement:
                      - Effect: Allow
                        Principal:
                          Service: ec2.amazonaws.com
                        Action: sts:AssumeRole
                  ManagedPolicyArns:
                    - arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
                    - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
                    - arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

              GPUNodeGroup:
                Type: AWS::EKS::Nodegroup
                DependsOn: EKSCluster
                Properties:
                  ClusterName: !Ref ClusterName
                  NodegroupName: "gpu-nodes"
                  NodeRole: !GetAtt NodeRole.Arn
                  InstanceTypes:
                    - !Ref InstanceType
                  AmiType: AL2_x86_64_GPU
                  ScalingConfig:
                    DesiredSize: !Ref DesiredCapacity
                    MinSize: 1
                    MaxSize: !Ref MaxSize
                  Subnets:
                    - !Ref PublicSubnetA
                    - !Ref PublicSubnetB

              # ── ECR Repository ──
              ECRRepository:
                Type: AWS::ECR::Repository
                Properties:
                  RepositoryName: !Sub "llm-${{DeploymentId}}"
                  ImageScanningConfiguration:
                    ScanOnPush: true

              # ── S3 Bucket for Model Weights ──
              ModelBucket:
                Type: AWS::S3::Bucket
                Properties:
                  BucketName: !Sub "llm-models-${{DeploymentId}}"
                  BucketEncryption:
                    ServerSideEncryptionConfiguration:
                      - ServerSideEncryptionByDefault:
                          SSEAlgorithm: AES256

            Outputs:
              ClusterEndpoint:
                Value: !GetAtt EKSCluster.Endpoint
              ECRRepositoryUri:
                Value: !GetAtt ECRRepository.RepositoryUri
              ModelBucketName:
                Value: !Ref ModelBucket
              LaunchStackURL:
                Description: "One-click deploy URL (share this)"
                Value: !Sub "https://${{AWS::Region}}.console.aws.amazon.com/cloudformation/home?region=${{AWS::Region}}#/stacks/quickcreate?stackName=llm-${{DeploymentId}}"
        """)

    def generate_quickstart_instructions(
        self,
        cloud_provider: str,
        deployment_id: str,
        model_name: str,
        instance_type: str,
        gpu_type: str,
        region: str,
    ) -> str:
        dep_short = deployment_id[:8]
        if cloud_provider == "aws":
            return textwrap.dedent(f"""\
                # Deploy {model_name} on AWS
                # Prerequisites: AWS CLI configured, kubectl, Docker

                # 1. Provision infrastructure
                # Option A: CloudFormation (one-click)
                aws cloudformation deploy \\
                  --template-file cloudformation.yaml \\
                  --stack-name llm-{dep_short} \\
                  --capabilities CAPABILITY_IAM \\
                  --region {region}

                # Option B: Terraform
                cd terraform/ && terraform init && terraform apply

                # 2. Build and push container
                aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.{region}.amazonaws.com
                docker build -t llm-{dep_short} -f Dockerfile .
                docker tag llm-{dep_short}:latest <ACCOUNT_ID>.dkr.ecr.{region}.amazonaws.com/llm-{deployment_id}:latest
                docker push <ACCOUNT_ID>.dkr.ecr.{region}.amazonaws.com/llm-{deployment_id}:latest

                # 3. Deploy to EKS
                aws eks update-kubeconfig --name llm-{dep_short} --region {region}
                kubectl apply -f kubernetes.yaml

                # 4. Verify
                kubectl get pods -n llm-deployments
                kubectl logs -f deployment/llm-{dep_short} -n llm-deployments
            """)
        elif cloud_provider == "gcp":
            return textwrap.dedent(f"""\
                # Deploy {model_name} on GCP
                # Prerequisites: gcloud CLI configured, kubectl, Docker

                # 1. Provision infrastructure
                cd terraform/ && terraform init
                terraform apply -var="project_id=YOUR_PROJECT_ID"

                # 2. Build and push container
                gcloud auth configure-docker {region}-docker.pkg.dev
                docker build -t llm-{dep_short} -f Dockerfile .
                docker tag llm-{dep_short}:latest {region}-docker.pkg.dev/YOUR_PROJECT_ID/llm-{deployment_id}/vllm:latest
                docker push {region}-docker.pkg.dev/YOUR_PROJECT_ID/llm-{deployment_id}/vllm:latest

                # 3. Deploy to GKE
                gcloud container clusters get-credentials llm-{dep_short} --region {region}
                kubectl apply -f kubernetes.yaml

                # 4. Verify
                kubectl get pods -n llm-deployments
                kubectl logs -f deployment/llm-{dep_short} -n llm-deployments
            """)
        else:  # azure
            return textwrap.dedent(f"""\
                # Deploy {model_name} on Azure
                # Prerequisites: Azure CLI configured, kubectl, Docker

                # 1. Provision infrastructure
                cd terraform/ && terraform init && terraform apply

                # 2. Build and push container
                az acr login --name llm{dep_short.replace('-', '')}
                docker build -t llm-{dep_short} -f Dockerfile .
                docker tag llm-{dep_short}:latest llm{dep_short.replace('-', '')}.azurecr.io/vllm:latest
                docker push llm{dep_short.replace('-', '')}.azurecr.io/vllm:latest

                # 3. Deploy to AKS
                az aks get-credentials --resource-group llm-{dep_short}-rg --name llm-{dep_short}
                kubectl apply -f kubernetes.yaml

                # 4. Verify
                kubectl get pods -n llm-deployments
                kubectl logs -f deployment/llm-{dep_short} -n llm-deployments
            """)

    def generate_all_configs(
        self,
        deployment_id: str,
        model_id: str,
        model_name: str,
        cloud_provider: str,
        instance_type: str,
        gpu_type: str,
        gpu_count: int,
        context_length: int,
        precision: str,
        region: str,
        is_custom_upload: bool = False,
        pipeline: Optional[ModelPipeline] = None,
    ) -> dict:
        """Generate all deployment configurations."""
        dockerfile = self.generate_dockerfile(
            model_id, gpu_count, context_length, precision, is_custom_upload,
            pipeline=pipeline,
        )

        k8s_yaml = self.generate_kubernetes_yaml(
            deployment_id, model_name, instance_type, gpu_type, gpu_count
        )

        if cloud_provider == "aws":
            terraform = self.generate_terraform_aws(deployment_id, instance_type, region, gpu_count)
        elif cloud_provider == "gcp":
            gpu_type_gcp = gpu_type.lower().replace("_", "-").replace("gb", "")
            terraform = self.generate_terraform_gcp(
                deployment_id, instance_type, region, gpu_type_gcp, gpu_count
            )
        elif cloud_provider == "azure":
            terraform = self.generate_terraform_azure(deployment_id, instance_type, region)
        else:
            terraform = "# Unsupported cloud provider"

        ci_cd = self.generate_ci_cd_pipeline(deployment_id, cloud_provider, model_name)

        cloudformation = ""
        if cloud_provider == "aws":
            cloudformation = self.generate_cloudformation(
                deployment_id, instance_type, gpu_type, gpu_count, model_name, region
            )

        quickstart = self.generate_quickstart_instructions(
            cloud_provider, deployment_id, model_name, instance_type, gpu_type, region
        )

        merge_config = ""
        if pipeline:
            merge_config = self.generate_merge_config(pipeline)

        return {
            "dockerfile": dockerfile,
            "kubernetes_yaml": k8s_yaml,
            "terraform_config": terraform,
            "ci_cd_pipeline": ci_cd,
            "cloudformation": cloudformation,
            "quickstart": quickstart,
            "merge_config": merge_config,
        }
