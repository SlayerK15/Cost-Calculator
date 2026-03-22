"use client";

import { useState, useEffect } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from "recharts";
import type { PopularModel, CompareModelEntry, ModelComparisonEntry } from "@/types";
import * as api from "@/lib/api";

const COLORS = ["#5c7cfa", "#22c55e", "#f97316", "#a855f7"];
const PRECISIONS = ["fp16", "bf16", "int8", "int4"];

export default function ComparePage() {
  const [popularModels, setPopularModels] = useState<PopularModel[]>([]);
  const [slots, setSlots] = useState<CompareModelEntry[]>([
    { name: "", parameters_billion: 0, precision: "fp16", context_length: 4096 },
    { name: "", parameters_billion: 0, precision: "fp16", context_length: 4096 },
  ]);
  const [provider, setProvider] = useState("aws");
  const [results, setResults] = useState<ModelComparisonEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getPopularModels().then(setPopularModels).catch(() => {});
  }, []);

  function updateSlot(index: number, modelId: string) {
    const m = popularModels.find((p) => p.id === modelId);
    if (!m) return;
    const next = [...slots];
    next[index] = {
      name: m.name,
      parameters_billion: m.parameters_billion,
      precision: "fp16",
      context_length: Math.min(m.context_length, 4096),
    };
    setSlots(next);
  }

  function addSlot() {
    if (slots.length >= 4) return;
    setSlots([...slots, { name: "", parameters_billion: 0, precision: "fp16", context_length: 4096 }]);
  }

  function removeSlot(i: number) {
    if (slots.length <= 2) return;
    setSlots(slots.filter((_, idx) => idx !== i));
  }

  async function runComparison() {
    const valid = slots.filter((s) => s.parameters_billion > 0);
    if (valid.length < 2) {
      setError("Select at least 2 models to compare.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await api.compareModels({ models: valid, cloud_provider: provider });
      setResults(res.comparisons);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  // Build radar data (normalize to 0-100)
  const radarData = results.length > 0
    ? (() => {
        const maxCost = Math.max(...results.map((r) => r.total_cost_monthly)) || 1;
        const maxVram = Math.max(...results.map((r) => r.vram_required_gb)) || 1;
        const maxParams = Math.max(...results.map((r) => r.parameters_billion)) || 1;
        const metrics = [
          { metric: "Cost Efficiency", key: "cost" },
          { metric: "VRAM Efficiency", key: "vram" },
          { metric: "Model Size", key: "size" },
          { metric: "GPU Count", key: "gpus" },
        ];
        return metrics.map((m) => {
          const row: Record<string, any> = { metric: m.metric };
          results.forEach((r, i) => {
            if (m.key === "cost") row[r.model_name] = Math.round((1 - r.total_cost_monthly / maxCost) * 100);
            else if (m.key === "vram") row[r.model_name] = Math.round((1 - r.vram_required_gb / maxVram) * 100);
            else if (m.key === "size") row[r.model_name] = Math.round((r.parameters_billion / maxParams) * 100);
            else if (m.key === "gpus") row[r.model_name] = Math.round((1 / Math.max(r.gpu_count, 1)) * 100);
          });
          return row;
        });
      })()
    : [];

  const barData = results.map((r) => ({
    name: r.model_name,
    cost: r.total_cost_monthly,
    vram: r.vram_required_gb,
  }));

  return (
    <div>
      <h1 className="text-3xl font-bold">Model Comparison</h1>
      <p className="mt-2 text-gray-400">
        Compare 2-4 models side by side on cost, VRAM, and GPU requirements.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-800 bg-red-900/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-6 card max-w-3xl space-y-4">
        {slots.map((slot, i) => (
          <div key={i} className="flex items-center gap-3">
            <span
              className="inline-block h-3 w-3 rounded-full flex-shrink-0"
              style={{ background: COLORS[i] }}
            />
            <select
              className="input flex-1"
              value={popularModels.find((m) => m.name === slot.name)?.id || ""}
              onChange={(e) => updateSlot(i, e.target.value)}
            >
              <option value="">-- Model {i + 1} --</option>
              {popularModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.parameters_billion}B)
                </option>
              ))}
            </select>
            <select
              className="input w-24"
              value={slot.precision}
              onChange={(e) => {
                const next = [...slots];
                next[i] = { ...next[i], precision: e.target.value };
                setSlots(next);
              }}
            >
              {PRECISIONS.map((p) => (
                <option key={p} value={p}>{p.toUpperCase()}</option>
              ))}
            </select>
            {slots.length > 2 && (
              <button onClick={() => removeSlot(i)} className="text-gray-500 hover:text-red-400 text-sm">
                Remove
              </button>
            )}
          </div>
        ))}

        {slots.length < 4 && (
          <button onClick={addSlot} className="text-sm text-brand-400 hover:text-brand-300">
            + Add model
          </button>
        )}

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

        <button onClick={runComparison} disabled={loading} className="btn-primary w-full">
          {loading ? "Comparing..." : "Compare Models"}
        </button>
      </div>

      {results.length > 0 && (
        <div className="mt-8 space-y-8">
          {/* Charts side by side */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Radar Chart */}
            <div className="card">
              <h3 className="text-sm font-bold text-gray-300 mb-4">Performance Radar</h3>
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <PolarRadiusAxis tick={false} axisLine={false} domain={[0, 100]} />
                  {results.map((r, i) => (
                    <Radar
                      key={r.model_name}
                      name={r.model_name}
                      dataKey={r.model_name}
                      stroke={COLORS[i]}
                      fill={COLORS[i]}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                  <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Cost Bar Chart */}
            <div className="card">
              <h3 className="text-sm font-bold text-gray-300 mb-4">Monthly Cost Comparison</h3>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10 }} />
                  <YAxis tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`} tick={{ fill: "#64748b", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [`$${v.toLocaleString()}`, "Monthly Cost"]}
                  />
                  <Bar dataKey="cost" radius={[6, 6, 0, 0]}>
                    {barData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Comparison Table */}
          <div className="card overflow-x-auto">
            <h3 className="text-sm font-bold text-gray-300 mb-4">Detailed Comparison</h3>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-700 text-gray-500">
                <tr>
                  <th className="pb-2 pr-4">Metric</th>
                  {results.map((r, i) => (
                    <th key={r.model_name} className="pb-2 pr-4 text-right">
                      <span className="inline-block h-2 w-2 rounded-full mr-1" style={{ background: COLORS[i] }} />
                      {r.model_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {[
                  { label: "Parameters", fmt: (r: ModelComparisonEntry) => `${r.parameters_billion}B` },
                  { label: "Precision", fmt: (r: ModelComparisonEntry) => r.precision.toUpperCase() },
                  { label: "VRAM Required", fmt: (r: ModelComparisonEntry) => `${r.vram_required_gb.toFixed(1)} GB` },
                  { label: "GPU", fmt: (r: ModelComparisonEntry) => `${r.gpu_type} x${r.gpu_count}` },
                  { label: "Instance", fmt: (r: ModelComparisonEntry) => r.instance_type },
                  { label: "Monthly Cost", fmt: (r: ModelComparisonEntry) => `$${r.total_cost_monthly.toLocaleString()}`, highlight: true },
                  { label: "Compute Cost", fmt: (r: ModelComparisonEntry) => `$${r.compute_cost_monthly.toLocaleString()}` },
                  { label: "Storage Cost", fmt: (r: ModelComparisonEntry) => `$${r.storage_cost_monthly.toLocaleString()}` },
                ].map(({ label, fmt, highlight }) => {
                  const values = results.map((r) => r.total_cost_monthly);
                  const minCost = Math.min(...values);
                  return (
                    <tr key={label}>
                      <td className="py-2 pr-4 text-gray-400">{label}</td>
                      {results.map((r, i) => (
                        <td
                          key={r.model_name}
                          className={`py-2 pr-4 text-right ${
                            highlight && r.total_cost_monthly === minCost
                              ? "font-bold text-green-400"
                              : highlight
                              ? "font-medium text-white"
                              : "text-gray-300"
                          }`}
                        >
                          {fmt(r)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
