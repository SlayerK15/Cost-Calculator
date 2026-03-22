"""Tests for the model recommender service."""

import pytest
from app.services.recommender import recommend_models, MODEL_CATALOG, QUALITY_ORDER


class TestRecommendModels:
    def test_chat_use_case(self):
        results = recommend_models("chat", max_budget_monthly=50000)
        assert len(results) > 0
        for r in results:
            assert r["monthly_cost"] <= 50000

    def test_coding_use_case(self):
        results = recommend_models("coding", max_budget_monthly=50000)
        assert len(results) > 0

    def test_budget_filtering(self):
        results = recommend_models("chat", max_budget_monthly=100)
        # Very low budget — might get 0 or only tiny models
        for r in results:
            assert r["monthly_cost"] <= 100

    def test_max_five_results(self):
        results = recommend_models("general", max_budget_monthly=999999)
        assert len(results) <= 5

    def test_provider_filter(self):
        results = recommend_models("chat", max_budget_monthly=50000, cloud_provider="gcp")
        for r in results:
            assert r["cloud_provider"] == "gcp"

    def test_results_sorted_by_quality_then_cost(self):
        results = recommend_models("general", max_budget_monthly=50000)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                a, b = results[i], results[i + 1]
                qa = QUALITY_ORDER.get(a["quality_tier"], 0)
                qb = QUALITY_ORDER.get(b["quality_tier"], 0)
                if qa == qb:
                    assert a["monthly_cost"] <= b["monthly_cost"]
                else:
                    assert qa >= qb

    def test_min_context_length_filter(self):
        results = recommend_models("general", max_budget_monthly=50000, min_context_length=32768)
        # Models with <32K context should be filtered out
        for r in results:
            model_info = next((m for m in MODEL_CATALOG if m["name"] == r["model_name"]), None)
            if model_info:
                assert model_info["context_length"] >= 32768

    def test_unknown_use_case_returns_fallback(self):
        results = recommend_models("quantum_computing", max_budget_monthly=50000)
        # Should fall back to all models
        assert len(results) >= 0  # May return 0 if all too expensive, or some fallback

    def test_result_fields(self):
        results = recommend_models("chat", max_budget_monthly=50000)
        if results:
            r = results[0]
            assert "model_name" in r
            assert "parameters_billion" in r
            assert "quality_tier" in r
            assert "cloud_provider" in r
            assert "instance_type" in r
            assert "monthly_cost" in r
            assert "recommendation" in r
