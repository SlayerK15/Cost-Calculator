"use client";

import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar,
} from "recharts";
import type { Deployment, UsageSummary } from "@/types";
import * as api from "@/lib/api";

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#3b82f6", "#ec4899"];

export default function DashboardPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [usage, setUsage] = useState<Record<string, UsageSummary>>({});
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [usageSeries, setUsageSeries] = useState<any[]>([]);
  const [costBreakdown, setCostBreakdown] = useState<any[]>([]);
  const [chartDays, setChartDays] = useState(30);

  useEffect(() => {
    loadData();
  }, [chartDays]);

  async function loadData() {
    try {
      const deps = await api.listDeployments();
      setDeployments(deps);

      const usageMap: Record<string, UsageSummary> = {};
      for (const dep of deps) {
        try { usageMap[dep.id] = await api.getUsage(dep.id); } catch {}
      }
      setUsage(usageMap);

      // Analytics
      try {
        const [sum, series, breakdown] = await Promise.all([
          api.getAnalyticsSummary(),
          api.getUsageSeries(chartDays),
          api.getCostBreakdown(),
        ]);
        setSummary(sum);
        setUsageSeries(series);
        setCostBreakdown(breakdown);
      } catch {}
    } catch {}
    setLoading(false);
  }

  const totalCost = summary?.total_cost_usd ?? deployments.reduce((s, d) => s + d.total_cost_incurred, 0);
  const totalRequests = summary?.total_requests ?? deployments.reduce((s, d) => s + d.total_requests, 0);
  const totalTokens = summary?.total_tokens ?? deployments.reduce((s, d) => s + d.total_tokens_generated, 0);
  const activeDeployments = summary?.active_deployments ?? deployments.filter((d) => d.status === "running").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <p className="mt-2 text-gray-400">Monitor your deployments, usage, and billing.</p>

      {/* Summary cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active Deployments" value={activeDeployments.toString()} sub={`${summary?.total_deployments || deployments.length} total`} />
        <StatCard label="Total Requests" value={totalRequests.toLocaleString()} sub="All time" />
        <StatCard label="Tokens Generated" value={formatNumber(totalTokens)} sub="All time" />
        <StatCard label="Total Cost" value={`$${totalCost.toFixed(2)}`} sub="All deployments" color="text-blue-400" />
      </div>

      {/* Charts Row */}
      {usageSeries.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Usage Trends</h2>
            <div className="flex gap-1">
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => setChartDays(d)}
                  className={`px-3 py-1 rounded text-sm ${chartDays === d ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Requests Chart */}
            <div className="card">
              <div className="text-sm text-gray-400 mb-3">Requests per Day</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={usageSeries}>
                  <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8, color: "#fff" }} />
                  <Bar dataKey="requests" fill="#6366f1" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Cost Chart */}
            <div className="card">
              <div className="text-sm text-gray-400 mb-3">Daily Cost ($)</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={usageSeries}>
                  <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8, color: "#fff" }} />
                  <Line type="monotone" dataKey="cost_usd" stroke="#22c55e" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Latency Chart */}
            <div className="card">
              <div className="text-sm text-gray-400 mb-3">Avg Latency (ms)</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={usageSeries}>
                  <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8, color: "#fff" }} />
                  <Line type="monotone" dataKey="avg_latency_ms" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Cost Breakdown Pie */}
            {costBreakdown.length > 0 && (
              <div className="card">
                <div className="text-sm text-gray-400 mb-3">Cost by Deployment</div>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={costBreakdown}
                      dataKey="cost_usd"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      outerRadius={70}
                      label={({ label, percent }) => `${label.slice(0, 15)} (${(percent * 100).toFixed(0)}%)`}
                      labelLine={{ stroke: "#4b5563" }}
                    >
                      {costBreakdown.map((_: any, i: number) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8, color: "#fff" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Deployment Table */}
      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">Deployments</h2>
        {deployments.length === 0 ? (
          <div className="card text-center text-gray-500">
            <p>No deployments yet.</p>
            <a href="/deploy" className="text-brand-400 hover:text-brand-300 text-sm">Create your first deployment</a>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-500">
                  <th className="py-3 px-2">Status</th>
                  <th className="py-3 px-2">ID</th>
                  <th className="py-3 px-2">Provider</th>
                  <th className="py-3 px-2">Instance</th>
                  <th className="py-3 px-2">GPU</th>
                  <th className="py-3 px-2">Requests</th>
                  <th className="py-3 px-2">Cost</th>
                  <th className="py-3 px-2">Created</th>
                  <th className="py-3 px-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {deployments.map((d) => {
                  const u = usage[d.id];
                  return (
                    <tr key={d.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="py-3 px-2"><StatusBadge status={d.status} /></td>
                      <td className="py-3 px-2 font-mono text-xs text-gray-500">{d.id.slice(0, 8)}</td>
                      <td className="py-3 px-2 text-gray-300">{d.cloud_provider.toUpperCase()}</td>
                      <td className="py-3 px-2 text-gray-300">{d.instance_type}</td>
                      <td className="py-3 px-2 text-gray-400">{d.gpu_type} x{d.gpu_count}</td>
                      <td className="py-3 px-2 text-gray-300">{(u?.total_requests ?? d.total_requests).toLocaleString()}</td>
                      <td className="py-3 px-2 text-gray-300">${d.total_cost_incurred.toFixed(2)}</td>
                      <td className="py-3 px-2 text-gray-500">{new Date(d.created_at).toLocaleDateString()}</td>
                      <td className="py-3 px-2">
                        <div className="flex gap-1">
                          {d.status === "running" && (
                            <a href={`/chat?deployment=${d.id}`} className="text-xs text-blue-400 hover:text-blue-300">Chat</a>
                          )}
                          <a href={`/estimate?model=${d.model_id}`} className="text-xs text-gray-400 hover:text-white">Cost</a>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub: string; color?: string }) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${color || "text-white"}`}>{value}</div>
      <div className="mt-0.5 text-xs text-gray-600">{sub}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-green-900/30 text-green-400 border-green-800",
    pending: "bg-yellow-900/30 text-yellow-400 border-yellow-800",
    provisioning: "bg-blue-900/30 text-blue-400 border-blue-800",
    deploying: "bg-blue-900/30 text-blue-400 border-blue-800",
    failed: "bg-red-900/30 text-red-400 border-red-800",
    stopped: "bg-gray-800 text-gray-500 border-gray-700",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-bold uppercase ${colors[status] || colors.stopped}`}>
      {status}
    </span>
  );
}

function formatNumber(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toString();
}
