"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { SharedEstimateData } from "@/types";
import * as api from "@/lib/api";

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;
  const [data, setData] = useState<SharedEstimateData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (token) {
      api.getSharedEstimate(token).then(setData).catch((e) => setError(e.message));
    }
  }, [token]);

  if (error) {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold text-red-400">Estimate Not Found</h1>
        <p className="mt-2 text-gray-400">This shared estimate may have expired or been removed.</p>
        <Link href="/estimate" className="mt-6 inline-block btn-primary">
          Create Your Own Estimate
        </Link>
      </div>
    );
  }

  if (!data) {
    return <div className="text-center py-20 text-gray-400">Loading shared estimate...</div>;
  }

  const est = data.estimate as Record<string, any>;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Shared Cost Estimate</h1>
          <p className="mt-1 text-sm text-gray-400">
            {data.model_name} on {data.cloud_provider.toUpperCase()} — shared{" "}
            {new Date(data.created_at).toLocaleDateString()} — {data.views_count} views
          </p>
        </div>
        <Link href="/estimate" className="btn-primary text-sm">
          Create Your Own
        </Link>
      </div>

      <div className="mt-6 card">
        <h3 className="text-lg font-bold text-white">{data.model_name}</h3>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-gray-800 p-3 text-center">
            <div className="text-2xl font-bold text-white">
              ${data.total_cost_monthly.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500">Monthly Cost</div>
          </div>
          {est.cloud_provider && (
            <div className="rounded-lg bg-gray-800 p-3 text-center">
              <div className="text-lg font-bold text-brand-400">
                {(est.cloud_provider || data.cloud_provider).toUpperCase()}
              </div>
              <div className="text-xs text-gray-500">Cloud Provider</div>
            </div>
          )}
          {est.vram_required_gb && (
            <div className="rounded-lg bg-gray-800 p-3 text-center">
              <div className="text-lg font-bold text-white">
                {est.vram_required_gb.toFixed(1)} GB
              </div>
              <div className="text-xs text-gray-500">VRAM Required</div>
            </div>
          )}
          {est.recommended_gpu && (
            <div className="rounded-lg bg-gray-800 p-3 text-center">
              <div className="text-lg font-bold text-white">
                {est.recommended_gpu.gpu_type}
              </div>
              <div className="text-xs text-gray-500">
                x{est.recommended_gpu.gpu_count} GPU{est.recommended_gpu.gpu_count > 1 ? "s" : ""}
              </div>
            </div>
          )}
        </div>

        {est.cost_breakdown && (
          <div className="mt-4 rounded-lg border border-gray-700 p-3">
            <h4 className="text-sm font-bold text-gray-300 mb-2">Cost Breakdown</h4>
            <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Compute</span>
                <span className="text-white">${est.cost_breakdown.compute_cost_monthly?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Storage</span>
                <span className="text-white">${est.cost_breakdown.storage_cost_monthly?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Bandwidth</span>
                <span className="text-white">${est.cost_breakdown.bandwidth_cost_monthly?.toLocaleString()}</span>
              </div>
            </div>
          </div>
        )}

        {est.recommendation && (
          <div className="mt-4 rounded-lg border border-brand-800 bg-brand-900/20 p-3 text-sm text-brand-300">
            {est.recommendation}
          </div>
        )}
      </div>
    </div>
  );
}
