"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import type { PopularModel, CostEstimate, APIProviderComparison, PricingStatus } from "@/types";
import * as api from "@/lib/api";
import { CostBreakdownCard } from "@/components/CostBreakdown";
import { APIProviderComparisonCard } from "@/components/APIProviderComparison";

const PRECISIONS = [
  { value: "fp16", label: "FP16" },
  { value: "bf16", label: "BF16" },
  { value: "int8", label: "INT8" },
  { value: "int4", label: "INT4" },
  { value: "fp32", label: "FP32" },
];

export default function EstimatePage() {
  const searchParams = useSearchParams();
  const [popularModels, setPopularModels] = useState<PopularModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [customParams, setCustomParams] = useState("");
  const [precision, setPrecision] = useState("fp16");
  const [contextLength, setContextLength] = useState(4096);
  const [provider, setProvider] = useState("aws");
  const [qps, setQps] = useState(1);
  const [tokensPerReq, setTokensPerReq] = useState(512);
  const [hoursPerDay, setHoursPerDay] = useState(24);
  const [daysPerMonth, setDaysPerMonth] = useState(30);
  const [autoscaling, setAutoscaling] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [allEstimates, setAllEstimates] = useState<CostEstimate[]>([]);
  const [apiComparison, setApiComparison] = useState<APIProviderComparison | null>(null);
  const [pricingStatus, setPricingStatus] = useState<PricingStatus | null>(null);

  useEffect(() => {
    loadPopularModels();
    loadPricingStatus();
  }, []);

  // Pre-fill from query params (e.g. from models page)
  useEffect(() => {
    const paramsBillion = searchParams.get("params");
    const ctx = searchParams.get("ctx");
    const modelName = searchParams.get("model");

    if (paramsBillion && popularModels.length > 0) {
      // Try to match a popular model by name
      const match = modelName
        ? popularModels.find((m) => m.name === modelName)
        : null;
      if (match) {
        setSelectedModelId(match.id);
        setContextLength(match.context_length);
      } else {
        // Fall back to custom model with the given params
        setSelectedModelId("__custom");
        setCustomParams(paramsBillion);
        if (ctx) setContextLength(Number(ctx));
      }
    }
  }, [searchParams, popularModels]);

  async function loadPopularModels() {
    try {
      const models = await api.getPopularModels();
      setPopularModels(models);
    } catch {}
  }

  async function loadPricingStatus() {
    try {
      const status = await api.getPricingStatus();
      setPricingStatus(status);
    } catch {}
  }

  function getModelInfo(): {
    name: string;
    parameters_billion: number;
    precision: string;
    context_length: number;
  } | null {
    if (selectedModelId === "__custom") {
      const params = parseFloat(customParams);
      if (!params || params <= 0) return null;
      return {
        name: `Custom ${params}B Model`,
        parameters_billion: params,
        precision,
        context_length: contextLength,
      };
    }
    const model = popularModels.find((m) => m.id === selectedModelId);
    if (!model) return null;
    return {
      name: model.name,
      parameters_billion: model.parameters_billion,
      precision,
      context_length: model.context_length,
    };
  }

  async function runEstimate() {
    const info = getModelInfo();
    if (!info) return;
    setLoading(true);
    setError("");
    setEstimate(null);
    setAllEstimates([]);
    setApiComparison(null);

    const requestData = {
      model_name: info.name,
      parameters_billion: info.parameters_billion,
      precision: info.precision,
      context_length: info.context_length,
      cloud_provider: provider,
      expected_qps: qps,
      avg_tokens_per_request: tokensPerReq,
      hours_per_day: hoursPerDay,
      days_per_month: daysPerMonth,
      autoscaling_enabled: autoscaling,
    };

    try {
      if (compareMode) {
        const comparison = await api.publicCompareProviders({
          parameters_billion: info.parameters_billion,
          model_name: info.name,
          precision: info.precision,
          context_length: info.context_length,
          expected_qps: qps,
          hours_per_day: hoursPerDay,
          days_per_month: daysPerMonth,
        });
        setAllEstimates(comparison.estimates);
      } else {
        const est = await api.publicEstimateCost(requestData);
        setEstimate(est);
      }

      // Always fetch API provider comparison
      const apiComp = await api.compareWithAPIProviders(requestData);
      setApiComparison(apiComp);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  const canEstimate =
    selectedModelId === "__custom"
      ? parseFloat(customParams) > 0
      : !!selectedModelId;

  return (
    <div>
      <h1 className="text-3xl font-bold">Cost Calculator</h1>
      <p className="mt-2 text-gray-400">
        Free tool — estimate the cost to deploy any LLM on AWS, GCP, or Azure.
        No account required.
      </p>

      {pricingStatus && (
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              pricingStatus.using_live_prices ? "bg-green-500" : "bg-yellow-500"
            }`}
          />
          {pricingStatus.using_live_prices ? (
            <span>
              Live pricing ({pricingStatus.gpu_prices_count} GPU instances
              {pricingStatus.api_prices_count > 0
                ? `, ${pricingStatus.api_prices_count} API models`
                : ""}
              ) — updated{" "}
              {pricingStatus.gpu_last_updated
                ? new Date(pricingStatus.gpu_last_updated).toLocaleDateString()
                : "recently"}
            </span>
          ) : (
            <span>Using static pricing (early 2025 rates)</span>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-800 bg-red-900/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-6 card max-w-2xl space-y-4">
        <div>
          <label className="label">Select Model</label>
          <select
            className="input"
            value={selectedModelId}
            onChange={(e) => {
              setSelectedModelId(e.target.value);
              const m = popularModels.find((m) => m.id === e.target.value);
              if (m) setContextLength(m.context_length);
            }}
          >
            <option value="">-- Choose a model --</option>
            {popularModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.parameters_billion}B) — {m.organization}
              </option>
            ))}
            <option value="__custom">Custom Model (enter parameters)</option>
          </select>
        </div>

        {selectedModelId === "__custom" && (
          <div>
            <label className="label">Parameters (Billion)</label>
            <input
              className="input"
              type="number"
              step="0.1"
              placeholder="e.g. 7, 13, 70"
              value={customParams}
              onChange={(e) => setCustomParams(e.target.value)}
            />
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Precision</label>
            <select
              className="input"
              value={precision}
              onChange={(e) => setPrecision(e.target.value)}
            >
              {PRECISIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Context Length</label>
            <input
              className="input"
              type="number"
              value={contextLength}
              onChange={(e) => setContextLength(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input
              type="checkbox"
              checked={compareMode}
              onChange={(e) => setCompareMode(e.target.checked)}
              className="rounded border-gray-600"
            />
            Compare all providers
          </label>
        </div>

        {!compareMode && (
          <div>
            <label className="label">Cloud Provider</label>
            <div className="flex gap-2">
              {(["aws", "gcp", "azure"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    provider === p
                      ? "bg-brand-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Expected QPS</label>
            <input className="input" type="number" step="0.1" value={qps} onChange={(e) => setQps(Number(e.target.value))} />
          </div>
          <div>
            <label className="label">Avg Tokens/Request</label>
            <input className="input" type="number" value={tokensPerReq} onChange={(e) => setTokensPerReq(Number(e.target.value))} />
          </div>
          <div>
            <label className="label">Hours/Day Active</label>
            <input className="input" type="number" min={1} max={24} value={hoursPerDay} onChange={(e) => setHoursPerDay(Number(e.target.value))} />
          </div>
          <div>
            <label className="label">Days/Month Active</label>
            <input className="input" type="number" min={1} max={31} value={daysPerMonth} onChange={(e) => setDaysPerMonth(Number(e.target.value))} />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input type="checkbox" checked={autoscaling} onChange={(e) => setAutoscaling(e.target.checked)} className="rounded border-gray-600" />
            Enable Autoscaling
          </label>
          <span className="text-xs text-gray-500">
            Billable: {hoursPerDay * daysPerMonth}h/mo
            {hoursPerDay * daysPerMonth < 720 && ` (saves ${Math.round((1 - (hoursPerDay * daysPerMonth) / 720) * 100)}% vs 24/7)`}
          </span>
        </div>

        <button onClick={runEstimate} disabled={loading || !canEstimate} className="btn-primary w-full">
          {loading ? "Calculating..." : compareMode ? "Compare All Providers" : "Estimate Cost"}
        </button>
      </div>

      {estimate && (
        <div className="mt-8">
          <CostBreakdownCard estimate={estimate} />
        </div>
      )}

      {allEstimates.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4">Multi-Cloud Comparison</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {allEstimates.map((est) => (
              <CostBreakdownCard key={est.cloud_provider} estimate={est} compact />
            ))}
          </div>
        </div>
      )}

      {apiComparison && (
        <div className="mt-8">
          <APIProviderComparisonCard data={apiComparison} />
        </div>
      )}
    </div>
  );
}
