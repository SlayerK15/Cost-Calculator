"""Tests for the cost optimizer service."""

import pytest
from app.services.optimizer import optimize_estimate


class TestOptimizeEstimate:
    def test_basic_optimization(self):
        report = optimize_estimate(
            parameters_billion=8.0,
            precision="fp16",
            context_length=4096,
            cloud_provider="aws",
        )
        assert report["current_monthly_cost"] > 0
        assert len(report["optimizations"]) > 0
        assert report["best_optimized_cost"] <= report["current_monthly_cost"]

    def test_spot_instance_suggestion(self):
        report = optimize_estimate(8.0, "fp16", 4096, "aws")
        types = [s["type"] for s in report["optimizations"]]
        assert "spot" in types

    def test_reserved_instance_suggestion(self):
        report = optimize_estimate(8.0, "fp16", 4096, "aws")
        types = [s["type"] for s in report["optimizations"]]
        assert "reserved" in types

    def test_autoscaling_suggested_for_24x7(self):
        report = optimize_estimate(
            8.0, "fp16", 4096, "aws",
            hours_per_day=24, days_per_month=30,
        )
        types = [s["type"] for s in report["optimizations"]]
        assert "autoscaling" in types

    def test_no_autoscaling_for_partial_hours(self):
        report = optimize_estimate(
            8.0, "fp16", 4096, "aws",
            hours_per_day=8, days_per_month=20,
        )
        types = [s["type"] for s in report["optimizations"]]
        assert "autoscaling" not in types

    def test_precision_reduction_for_fp16(self):
        report = optimize_estimate(8.0, "fp16", 4096, "aws")
        precision_opts = [s for s in report["optimizations"] if s["type"] == "precision"]
        # May or may not suggest depending on whether int8/int4 actually saves money
        for opt in precision_opts:
            assert opt["savings_monthly"] > 0

    def test_no_precision_reduction_for_int4(self):
        report = optimize_estimate(8.0, "int4", 4096, "aws")
        precision_opts = [s for s in report["optimizations"] if s["type"] == "precision"]
        assert len(precision_opts) == 0

    def test_sorted_by_savings(self):
        report = optimize_estimate(8.0, "fp16", 4096, "aws")
        savings = [s["savings_monthly"] for s in report["optimizations"]]
        assert savings == sorted(savings, reverse=True)

    def test_impossible_model_returns_empty(self):
        report = optimize_estimate(10000.0, "fp32", 4096, "aws")
        assert report["current_monthly_cost"] == 0
        assert report["optimizations"] == []

    def test_provider_switch_suggestion(self):
        # Check if any provider switch is suggested
        report = optimize_estimate(8.0, "fp16", 4096, "aws")
        # May or may not appear depending on price differences
        for opt in report["optimizations"]:
            if opt["type"] == "provider_switch":
                assert opt["savings_pct"] > 10
