"""Tests for the core cost estimation engine."""

import pytest
from app.services.cost_engine.calculator import (
    calculate_vram,
    select_gpu_instance,
    estimate_cost,
    estimate_parameters_from_file_size,
    calculate_storage_cost,
    calculate_bandwidth_cost,
    calculate_idle_cost,
    generate_scaling_scenarios,
    BYTES_PER_PARAM,
    _estimate_architecture,
)
from app.services.cost_engine.gpu_catalog import CloudInstance


# ---------------------------------------------------------------------------
# Architecture estimation
# ---------------------------------------------------------------------------

class TestArchitectureEstimation:
    def test_small_model_1b(self):
        h, l = _estimate_architecture(0.5)
        assert h == 1024 and l == 16

    def test_8b_model(self):
        h, l = _estimate_architecture(8.0)
        assert h == 4096 and l == 32

    def test_13b_model(self):
        h, l = _estimate_architecture(13.0)
        assert h == 5120 and l == 40

    def test_70b_model(self):
        h, l = _estimate_architecture(70.0)
        assert h == 8192 and l == 80

    def test_405b_model(self):
        h, l = _estimate_architecture(405.0)
        assert h == 12288 and l == 96

    def test_fallback_for_huge_model(self):
        h, l = _estimate_architecture(2000.0)
        assert h == 12288 and l == 96


# ---------------------------------------------------------------------------
# VRAM calculation
# ---------------------------------------------------------------------------

class TestCalculateVRAM:
    def test_8b_fp16(self):
        vram = calculate_vram(8.0, "fp16", 4096)
        # Model weights: 8*1e9*2 / 1024^3 ≈ 14.9 GB
        assert 14 < vram.model_weights_gb < 16
        assert vram.kv_cache_gb > 0
        assert vram.activation_overhead_gb > 0
        assert vram.framework_overhead_gb >= 1.0
        assert vram.total_gb == pytest.approx(
            vram.model_weights_gb + vram.kv_cache_gb +
            vram.activation_overhead_gb + vram.framework_overhead_gb,
            abs=0.1,
        )

    def test_8b_int4_uses_less_vram(self):
        fp16 = calculate_vram(8.0, "fp16", 4096)
        int4 = calculate_vram(8.0, "int4", 4096)
        assert int4.total_gb < fp16.total_gb

    def test_larger_context_more_vram(self):
        short = calculate_vram(8.0, "fp16", 2048)
        long = calculate_vram(8.0, "fp16", 8192)
        assert long.total_gb > short.total_gb

    def test_larger_model_more_vram(self):
        small = calculate_vram(1.0, "fp16", 4096)
        large = calculate_vram(70.0, "fp16", 4096)
        assert large.total_gb > small.total_gb

    def test_explicit_architecture(self):
        vram = calculate_vram(8.0, "fp16", 4096, num_layers=32, hidden_dim=4096)
        assert vram.kv_cache_gb > 0

    def test_fp32_doubles_weights(self):
        fp16 = calculate_vram(8.0, "fp16", 4096)
        fp32 = calculate_vram(8.0, "fp32", 4096)
        assert fp32.model_weights_gb == pytest.approx(fp16.model_weights_gb * 2, rel=0.01)

    def test_all_precisions(self):
        for prec in BYTES_PER_PARAM:
            vram = calculate_vram(8.0, prec, 4096)
            assert vram.total_gb > 0


# ---------------------------------------------------------------------------
# GPU instance selection
# ---------------------------------------------------------------------------

class TestSelectGPUInstance:
    def test_aws_small_model(self):
        inst = select_gpu_instance(15.0, "aws")
        assert inst is not None
        assert inst.total_vram_gb >= 15.0
        assert inst.provider == "aws"

    def test_gcp_small_model(self):
        inst = select_gpu_instance(15.0, "gcp")
        assert inst is not None
        assert inst.provider == "gcp"

    def test_azure_small_model(self):
        inst = select_gpu_instance(15.0, "azure")
        assert inst is not None
        assert inst.provider == "azure"

    def test_no_instance_for_absurd_vram(self):
        inst = select_gpu_instance(99999.0, "aws")
        assert inst is None

    def test_cheapest_first(self):
        inst = select_gpu_instance(20.0, "aws", prefer_cost_efficiency=True)
        all_valid = [
            i for i in __import__("app.services.cost_engine.gpu_catalog", fromlist=["AWS_INSTANCES"]).AWS_INSTANCES
            if i.total_vram_gb >= 20.0
        ]
        cheapest = min(all_valid, key=lambda i: i.cost_per_hour)
        assert inst.cost_per_hour == cheapest.cost_per_hour

    def test_unknown_provider_returns_empty(self):
        inst = select_gpu_instance(20.0, "oracle")
        assert inst is None


# ---------------------------------------------------------------------------
# Parameter estimation from file size
# ---------------------------------------------------------------------------

class TestParameterEstimation:
    def test_fp16_estimation(self):
        # 16 GB file in FP16: 16*1024^3 / 2 / 1e9 ≈ 8.59B
        file_bytes = 16 * (1024 ** 3)
        params = estimate_parameters_from_file_size(file_bytes, "fp16")
        assert 8.0 < params < 9.0

    def test_int4_estimation(self):
        file_bytes = 4 * (1024 ** 3)
        params = estimate_parameters_from_file_size(file_bytes, "int4")
        assert params > 8.0  # int4 = 0.5 bytes/param → more params per byte


# ---------------------------------------------------------------------------
# Storage, bandwidth, idle cost helpers
# ---------------------------------------------------------------------------

class TestCostHelpers:
    def test_storage_cost(self):
        cost = calculate_storage_cost(10.0, 0.08)
        assert cost == pytest.approx(10.0 * 1.5 * 0.08, abs=0.01)

    def test_bandwidth_cost(self):
        cost = calculate_bandwidth_cost(512, 1.0, 0.09, 24, 30)
        assert cost >= 0

    def test_idle_cost_24x7_is_zero(self):
        cost = calculate_idle_cost(1.0, 24, 30)
        assert cost == 0.0

    def test_idle_cost_partial_day(self):
        cost = calculate_idle_cost(1.0, 12, 30)
        assert cost > 0


# ---------------------------------------------------------------------------
# Scaling scenarios
# ---------------------------------------------------------------------------

class TestScalingScenarios:
    def test_produces_three_scenarios(self):
        dummy = CloudInstance("aws", "g5.xlarge", "A10G", 1, 24, 24, 4, 16, 1.0, "us-east-1", 0.08, 0.09)
        scenarios = generate_scaling_scenarios(700, dummy, 1.0, False, 1, 3)
        assert len(scenarios) == 3
        assert scenarios[0]["name"] == "Baseline"
        assert scenarios[1]["name"] == "High Concurrency"
        assert scenarios[2]["name"] == "Enterprise"

    def test_baseline_cost_matches_input(self):
        dummy = CloudInstance("aws", "g5.xlarge", "A10G", 1, 24, 24, 4, 16, 1.0, "us-east-1", 0.08, 0.09)
        scenarios = generate_scaling_scenarios(700, dummy, 1.0, False, 1, 3)
        assert scenarios[0]["total_monthly_cost"] == 700.0


# ---------------------------------------------------------------------------
# Full estimate_cost integration
# ---------------------------------------------------------------------------

class TestEstimateCost:
    def test_8b_fp16_aws(self):
        result = estimate_cost(8.0, "fp16", 4096, "aws")
        assert result is not None
        assert result.total_cost_monthly > 0
        assert result.vram_required_gb > 0
        assert result.instance_type != ""
        assert len(result.scaling_scenarios) == 3

    def test_70b_fp16_aws(self):
        result = estimate_cost(70.0, "fp16", 4096, "aws")
        assert result is not None
        assert result.gpu_count >= 1
        assert result.total_cost_monthly > 1000  # large model, not cheap

    def test_returns_none_for_impossible_model(self):
        # 10000B model with fp32 — needs absurd VRAM
        result = estimate_cost(10000.0, "fp32", 4096, "aws")
        assert result is None

    def test_partial_hours(self):
        full = estimate_cost(8.0, "fp16", 4096, "aws", hours_per_day=24, days_per_month=30)
        partial = estimate_cost(8.0, "fp16", 4096, "aws", hours_per_day=8, days_per_month=20)
        assert partial.total_cost_monthly < full.total_cost_monthly

    def test_all_providers(self):
        for prov in ["aws", "gcp", "azure"]:
            result = estimate_cost(8.0, "fp16", 4096, prov)
            assert result is not None, f"Failed for {prov}"

    def test_optimized_config_present(self):
        result = estimate_cost(8.0, "fp16", 4096, "aws")
        assert "spot_instances" in result.optimized_config

    def test_recommendation_not_empty(self):
        result = estimate_cost(8.0, "fp16", 4096, "aws")
        assert len(result.recommendation) > 10

    def test_kv_overhead_cost_nonnegative(self):
        result = estimate_cost(8.0, "fp16", 4096, "aws")
        assert result.kv_cache_overhead_cost >= 0
