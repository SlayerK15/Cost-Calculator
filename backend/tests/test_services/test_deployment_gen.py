"""Tests for deployment configuration generator."""

import pytest
from app.services.deployment_generator import DeploymentGenerator, ModelPipeline


@pytest.fixture
def gen():
    return DeploymentGenerator()


class TestDockerfile:
    def test_basic_dockerfile(self, gen):
        df = gen.generate_dockerfile(
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            gpu_count=1,
            context_length=4096,
            precision="fp16",
        )
        assert "FROM" in df
        assert "Llama" in df or "llama" in df or "meta" in df

    def test_multi_gpu_dockerfile(self, gen):
        df = gen.generate_dockerfile(
            model_id="meta-llama/Llama-3.1-70B-Instruct",
            gpu_count=8,
            precision="fp16",
        )
        assert "tensor" in df.lower() or "parallel" in df.lower() or "8" in df

    def test_pipeline_dockerfile(self, gen):
        pipeline = ModelPipeline(
            base_model_hf_id="meta-llama/Llama-3.1-8B-Instruct",
        )
        df = gen.generate_dockerfile(
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            pipeline=pipeline,
            gpu_count=1,
        )
        assert "FROM" in df


class TestKubernetesYAML:
    def test_basic_k8s(self, gen):
        yaml_str = gen.generate_kubernetes_yaml(
            deployment_id="test-deploy-1",
            model_name="Llama-3.1-8B",
            instance_type="g5.xlarge",
            gpu_type="A10G_24GB",
            gpu_count=1,
        )
        assert "apiVersion" in yaml_str or "kind" in yaml_str or "Deployment" in yaml_str


class TestTerraform:
    def test_aws_terraform(self, gen):
        tf = gen.generate_terraform_aws(
            deployment_id="test-deploy-1",
            instance_type="g5.xlarge",
            region="us-east-1",
            gpu_count=1,
        )
        assert "aws" in tf.lower()
        assert "g5.xlarge" in tf

    def test_gcp_terraform(self, gen):
        tf = gen.generate_terraform_gcp(
            deployment_id="test-deploy-1",
            machine_type="g2-standard-4",
            region="us-central1",
            gpu_count=1,
        )
        assert "google" in tf.lower() or "gcp" in tf.lower()

    def test_azure_terraform(self, gen):
        tf = gen.generate_terraform_azure(
            deployment_id="test-deploy-1",
            vm_size="Standard_NC4as_T4_v3",
            region="eastus",
        )
        assert "azurerm" in tf.lower() or "azure" in tf.lower()
