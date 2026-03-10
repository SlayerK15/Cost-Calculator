"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  isAuthenticated,
  getManagedDeployment,
  getManagedMetrics,
  scaleManagedDeployment,
  stopManagedDeployment,
  startManagedDeployment,
  teardownManagedDeployment,
} from "@/lib/api";
import type { ManagedDeployment, DeploymentMetrics } from "@/types";

function MetricCard({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-sm text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color || "text-white"}`}>
        {value}
        {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function MiniChart({ data, dataKey, color, height = 60 }: { data: any[]; dataKey: string; color: string; height?: number }) {
  if (!data.length) return null;
  const values = data.map((d) => d[dataKey] as number);
  const max = Math.max(...values) || 1;
  const min = Math.min(...values);
  const range = max - min || 1;
  const width = 100;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ManagedDeploymentDetail() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [deployment, setDeployment] = useState<ManagedDeployment | null>(null);
  const [metrics, setMetrics] = useState<DeploymentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [timeRange, setTimeRange] = useState(24);

  // Scale form
  const [showScale, setShowScale] = useState(false);
  const [scaleMin, setScaleMin] = useState(1);
  const [scaleMax, setScaleMax] = useState(3);
  const [scaleAutoEnabled, setScaleAutoEnabled] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    loadData();
  }, [id, timeRange]);

  async function loadData() {
    try {
      const [dep, met] = await Promise.all([
        getManagedDeployment(id),
        getManagedMetrics(id, timeRange),
      ]);
      setDeployment(dep);
      setMetrics(met);
      setScaleMin(dep.min_replicas);
      setScaleMax(dep.max_replicas);
      setScaleAutoEnabled(dep.autoscaling_enabled);
    } catch {
      // error
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    if (!confirm("Stop this deployment? It can be restarted later.")) return;
    setActionLoading(true);
    try {
      await stopManagedDeployment(id);
      await loadData();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStart() {
    setActionLoading(true);
    try {
      await startManagedDeployment(id);
      await loadData();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleTeardown() {
    if (!confirm("PERMANENTLY tear down all infrastructure? This cannot be undone.")) return;
    setActionLoading(true);
    try {
      await teardownManagedDeployment(id);
      await loadData();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleScale() {
    setActionLoading(true);
    try {
      await scaleManagedDeployment(id, {
        min_replicas: scaleMin,
        max_replicas: scaleMax,
        autoscaling_enabled: scaleAutoEnabled,
      });
      setShowScale(false);
      await loadData();
    } finally {
      setActionLoading(false);
    }
  }

  if (loading || !deployment) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    );
  }

  const isRunning = deployment.status === "running";
  const isStopped = deployment.status === "stopped";
  const isTerminated = deployment.status === "terminated";
  const current = metrics?.current;
  const summary = metrics?.summary;
  const series = metrics?.time_series || [];
  const scalingEvents = metrics?.scaling_events || [];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <button
              onClick={() => router.push("/managed")}
              className="text-sm text-gray-400 hover:text-white mb-2 inline-block"
            >
              &larr; Back to Managed Deployments
            </button>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              {deployment.cloud_provider.toUpperCase()} - {deployment.instance_type}
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  isRunning
                    ? "bg-green-900/50 text-green-400"
                    : isStopped
                    ? "bg-gray-800 text-gray-400"
                    : isTerminated
                    ? "bg-red-900/50 text-red-400"
                    : "bg-blue-900/50 text-blue-400"
                }`}
              >
                {deployment.status.replace(/_/g, " ").toUpperCase()}
              </span>
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              {deployment.gpu_type} x{deployment.gpu_count} &middot; {deployment.region}
              {deployment.cluster_endpoint && (
                <span className="ml-2 font-mono text-gray-500">{deployment.cluster_endpoint}</span>
              )}
            </p>
          </div>
          <div className="flex gap-2">
            {isRunning && (
              <>
                <button
                  onClick={() => setShowScale(!showScale)}
                  className="px-3 py-2 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-sm"
                >
                  Scale
                </button>
                <button
                  onClick={handleStop}
                  disabled={actionLoading}
                  className="px-3 py-2 bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30 rounded-lg text-sm"
                >
                  Stop
                </button>
              </>
            )}
            {isStopped && (
              <button
                onClick={handleStart}
                disabled={actionLoading}
                className="px-3 py-2 bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg text-sm"
              >
                Start
              </button>
            )}
            {!isTerminated && (
              <button
                onClick={handleTeardown}
                disabled={actionLoading}
                className="px-3 py-2 bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg text-sm"
              >
                Teardown
              </button>
            )}
          </div>
        </div>

        {/* Scale Form */}
        {showScale && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
            <h3 className="font-semibold mb-3">Scaling Configuration</h3>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={scaleAutoEnabled}
                  onChange={(e) => setScaleAutoEnabled(e.target.checked)}
                  className="rounded"
                />
                Auto-scaling
              </label>
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400">Min:</label>
                <input
                  type="number"
                  value={scaleMin}
                  onChange={(e) => setScaleMin(Number(e.target.value))}
                  min={1}
                  max={10}
                  className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400">Max:</label>
                <input
                  type="number"
                  value={scaleMax}
                  onChange={(e) => setScaleMax(Number(e.target.value))}
                  min={1}
                  max={20}
                  className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                />
              </div>
              <button
                onClick={handleScale}
                disabled={actionLoading}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm"
              >
                Apply
              </button>
            </div>
          </div>
        )}

        {/* Current Metrics */}
        {current && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <MetricCard
              label="GPU Utilization"
              value={`${(current.gpu_utilization * 100).toFixed(1)}%`}
              color={current.gpu_utilization > 0.8 ? "text-red-400" : current.gpu_utilization > 0.6 ? "text-yellow-400" : "text-green-400"}
            />
            <MetricCard label="Avg Latency" value={current.avg_latency_ms.toFixed(0)} unit="ms" />
            <MetricCard label="Requests/min" value={current.requests_count} />
            <MetricCard label="Active Replicas" value={current.active_replicas} />
          </div>
        )}

        {/* Summary Stats */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <MetricCard label={`Requests (${timeRange}h)`} value={summary.total_requests.toLocaleString()} />
            <MetricCard label="Tokens Generated" value={(summary.total_tokens / 1000).toFixed(0)} unit="K" />
            <MetricCard label={`Cost (${timeRange}h)`} value={`$${summary.total_cost_usd.toFixed(2)}`} color="text-blue-400" />
            <MetricCard label="Avg Latency" value={summary.avg_latency_ms.toFixed(0)} unit="ms" />
            <MetricCard label="Avg GPU" value={`${(summary.avg_gpu_utilization * 100).toFixed(1)}%`} />
          </div>
        )}

        {/* Time Range Selector */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm text-gray-400">Time Range:</span>
          {[6, 12, 24, 48].map((h) => (
            <button
              key={h}
              onClick={() => setTimeRange(h)}
              className={`px-3 py-1 rounded text-sm ${
                timeRange === h ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {h}h
            </button>
          ))}
        </div>

        {/* Charts */}
        {series.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400 mb-2">GPU Utilization</div>
              <MiniChart data={series} dataKey="gpu_utilization" color="#22c55e" height={80} />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{timeRange}h ago</span>
                <span>Now</span>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400 mb-2">Request Latency (ms)</div>
              <MiniChart data={series} dataKey="avg_latency_ms" color="#3b82f6" height={80} />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{timeRange}h ago</span>
                <span>Now</span>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400 mb-2">Requests / Interval</div>
              <MiniChart data={series} dataKey="requests_count" color="#a855f7" height={80} />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{timeRange}h ago</span>
                <span>Now</span>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400 mb-2">Cost per Interval ($)</div>
              <MiniChart data={series} dataKey="cost_usd" color="#f59e0b" height={80} />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>{timeRange}h ago</span>
                <span>Now</span>
              </div>
            </div>
          </div>
        )}

        {/* Scaling Events */}
        {scalingEvents.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-8">
            <h3 className="text-lg font-semibold mb-4">Auto-Scaling Events</h3>
            <div className="space-y-3">
              {scalingEvents.map((ev, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <div
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      ev.event === "scale_up" ? "bg-green-400" : "bg-yellow-400"
                    }`}
                  />
                  <span className="text-gray-500 font-mono text-xs w-40 flex-shrink-0">
                    {new Date(ev.timestamp).toLocaleString()}
                  </span>
                  <span
                    className={`font-medium w-20 flex-shrink-0 ${
                      ev.event === "scale_up" ? "text-green-400" : "text-yellow-400"
                    }`}
                  >
                    {ev.event === "scale_up" ? "Scale Up" : "Scale Down"}
                  </span>
                  <span className="text-gray-300">
                    {ev.from_replicas} &rarr; {ev.to_replicas} replicas
                  </span>
                  <span className="text-gray-500 text-xs">{ev.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Deployment Details */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold mb-4">Deployment Details</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Cloud Provider</span>
              <div className="font-medium">{deployment.cloud_provider.toUpperCase()}</div>
            </div>
            <div>
              <span className="text-gray-400">Region</span>
              <div className="font-medium">{deployment.region}</div>
            </div>
            <div>
              <span className="text-gray-400">Instance Type</span>
              <div className="font-medium">{deployment.instance_type}</div>
            </div>
            <div>
              <span className="text-gray-400">GPU</span>
              <div className="font-medium">{deployment.gpu_type} x{deployment.gpu_count}</div>
            </div>
            <div>
              <span className="text-gray-400">Hourly Cost</span>
              <div className="font-medium">${deployment.estimated_hourly_cost.toFixed(2)}/hr</div>
            </div>
            <div>
              <span className="text-gray-400">Auto-scaling</span>
              <div className="font-medium">
                {deployment.autoscaling_enabled
                  ? `Enabled (${deployment.min_replicas}-${deployment.max_replicas} replicas)`
                  : "Disabled"}
              </div>
            </div>
            <div>
              <span className="text-gray-400">Created</span>
              <div className="font-medium">{new Date(deployment.created_at).toLocaleString()}</div>
            </div>
            <div>
              <span className="text-gray-400">Health</span>
              <div className={`font-medium ${deployment.health_status === "healthy" ? "text-green-400" : "text-gray-400"}`}>
                {deployment.health_status}
              </div>
            </div>
            <div>
              <span className="text-gray-400">Endpoint</span>
              <div className="font-mono text-xs break-all">{deployment.cluster_endpoint || "N/A"}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
