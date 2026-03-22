"use client";

import { useState } from "react";
import type { CostEstimate, OptimizationReport } from "@/types";
import * as api from "@/lib/api";

interface Props {
  estimate: CostEstimate;
  parameters_billion: number;
  precision: string;
  context_length: number;
  cloud_provider: string;
  expected_qps?: number;
  hours_per_day?: number;
  days_per_month?: number;
}

export function OptimizationPanel({
  estimate,
  parameters_billion,
  precision,
  context_length,
  cloud_provider,
  expected_qps = 1,
  hours_per_day = 24,
  days_per_month = 30,
}: Props) {
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchOptimizations() {
    setLoading(true);
    setError("");
    try {
      const r = await api.optimizeEstimate({
        model_name: estimate.model_name,
        parameters_billion,
        precision,
        context_length,
        cloud_provider,
        expected_qps,
        hours_per_day,
        days_per_month,
      });
      setReport(r);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  if (!report) {
    return (
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">Cost Optimization</h3>
            <p className="text-sm text-gray-400">
              Get AI-powered suggestions to reduce your deployment costs.
            </p>
          </div>
          <button
            onClick={fetchOptimizations}
            disabled={loading}
            className="btn-primary text-sm"
          >
            {loading ? "Analyzing..." : "Optimize"}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-sm text-red-400">{error}</p>
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white">Optimization Report</h3>
        <div className="text-right">
          <div className="text-sm text-gray-400">Potential Savings</div>
          <div className="text-xl font-bold text-green-400">
            ${report.total_potential_savings.toLocaleString()}/mo
          </div>
        </div>
      </div>

      <div className="mt-3 flex gap-4 text-sm">
        <div className="rounded-lg bg-gray-800 px-3 py-2">
          <span className="text-gray-500">Current: </span>
          <span className="font-bold text-white">
            ${report.current_monthly_cost.toLocaleString()}/mo
          </span>
        </div>
        <div className="rounded-lg bg-green-900/30 px-3 py-2">
          <span className="text-gray-500">Optimized: </span>
          <span className="font-bold text-green-400">
            ${report.best_optimized_cost.toLocaleString()}/mo
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {report.optimizations.map((opt, i) => (
          <div
            key={i}
            className="rounded-lg border border-gray-700 bg-gray-800/50 p-3"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">
                    {opt.title}
                  </span>
                  <span className="rounded-full bg-gray-700 px-2 py-0.5 text-[10px] text-gray-400 uppercase">
                    {opt.type}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-400">{opt.description}</p>
              </div>
              <div className="text-right shrink-0 ml-4">
                <div className="text-sm font-bold text-green-400">
                  -${opt.savings_monthly.toLocaleString()}/mo
                </div>
                <div className="text-xs text-gray-500">
                  {opt.savings_pct.toFixed(0)}% savings
                </div>
              </div>
            </div>
            <div className="mt-2 flex gap-3 text-xs">
              <span className="text-gray-500">
                ${opt.current_cost.toLocaleString()} → ${opt.optimized_cost.toLocaleString()}
              </span>
              {opt.tradeoff && (
                <span className="text-yellow-500/80">
                  Tradeoff: {opt.tradeoff}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {report.optimizations.length === 0 && (
        <p className="mt-4 text-sm text-gray-500 text-center py-4">
          Your current configuration is already well-optimized.
        </p>
      )}
    </div>
  );
}
