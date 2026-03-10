"use client";

import type { CostEstimate } from "@/types";

export function CostBreakdownCard({
  estimate,
  compact = false,
}: {
  estimate: CostEstimate;
  compact?: boolean;
}) {
  const { cost_breakdown, recommended_gpu, scaling_scenarios, recommendation } =
    estimate;

  const providerColors: Record<string, string> = {
    aws: "text-yellow-400 border-yellow-600",
    gcp: "text-blue-400 border-blue-600",
    azure: "text-cyan-400 border-cyan-600",
  };

  const colorClass = providerColors[estimate.cloud_provider] || "text-gray-400 border-gray-600";

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span
            className={`rounded-full border px-3 py-0.5 text-xs font-bold uppercase ${colorClass}`}
          >
            {estimate.cloud_provider}
          </span>
          {!compact && (
            <span className="ml-2 text-gray-500 text-sm">{estimate.model_name}</span>
          )}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-white">
            ${cost_breakdown.total_cost_monthly.toLocaleString()}<span className="text-sm text-gray-500">/mo</span>
          </div>
        </div>
      </div>

      {/* GPU recommendation */}
      <div className="mt-4 rounded-lg bg-gray-800/50 p-3">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Recommended Instance</div>
        <div className="mt-1 text-sm text-white">
          {recommended_gpu.instance_type} — {recommended_gpu.gpu_count}x{" "}
          {recommended_gpu.gpu_type.replace(/_/g, " ")}
        </div>
        <div className="mt-1 text-xs text-gray-400">
          {recommended_gpu.total_vram_gb}GB VRAM · ${recommended_gpu.cost_per_hour.toFixed(2)}/hr
          · VRAM needed: {estimate.vram_required_gb.toFixed(1)}GB
        </div>
      </div>

      {/* Cost breakdown */}
      <div className="mt-4 space-y-2">
        <CostLine label="Compute" value={cost_breakdown.compute_cost_monthly} />
        <CostLine label="Storage" value={cost_breakdown.storage_cost_monthly} />
        <CostLine label="Bandwidth" value={cost_breakdown.bandwidth_cost_monthly} />
        <CostLine label="KV Cache Overhead" value={cost_breakdown.kv_cache_overhead_cost} />
        {!compact && (
          <CostLine label="Idle Cost" value={cost_breakdown.idle_cost_monthly} muted />
        )}
        <div className="border-t border-gray-700 pt-2">
          <CostLine
            label="Total Monthly"
            value={cost_breakdown.total_cost_monthly}
            bold
          />
        </div>
      </div>

      {/* Scaling scenarios */}
      {!compact && scaling_scenarios.length > 0 && (
        <div className="mt-6">
          <h4 className="text-sm font-medium text-gray-400">Scaling Scenarios</h4>
          <div className="mt-2 space-y-2">
            {scaling_scenarios.map((s) => (
              <div
                key={s.name}
                className="flex items-center justify-between rounded-lg bg-gray-800/30 px-3 py-2 text-sm"
              >
                <div>
                  <span className="font-medium text-white">{s.name}</span>
                  <span className="ml-2 text-xs text-gray-500">{s.description}</span>
                </div>
                <div className="text-right">
                  <span className="text-white font-medium">
                    ${s.total_monthly_cost.toLocaleString()}/mo
                  </span>
                  <span className="ml-2 text-xs text-gray-500">
                    ${s.cost_per_request.toFixed(6)}/req
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendation */}
      {!compact && recommendation && (
        <div className="mt-6 rounded-lg border border-brand-800 bg-brand-900/20 p-3">
          <div className="text-xs font-medium text-brand-400 uppercase">Recommendation</div>
          <p className="mt-1 text-sm text-gray-300">{recommendation}</p>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-4 flex gap-2">
        <a
          href={`/deploy?model=${estimate.id}&provider=${estimate.cloud_provider}`}
          className="btn-primary text-sm flex-1 text-center"
        >
          Deploy on {estimate.cloud_provider.toUpperCase()}
        </a>
      </div>
    </div>
  );
}

function CostLine({
  label,
  value,
  bold = false,
  muted = false,
}: {
  label: string;
  value: number;
  bold?: boolean;
  muted?: boolean;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className={muted ? "text-gray-600" : "text-gray-400"}>{label}</span>
      <span className={bold ? "font-bold text-white" : muted ? "text-gray-600" : "text-gray-300"}>
        ${value.toFixed(2)}
      </span>
    </div>
  );
}
