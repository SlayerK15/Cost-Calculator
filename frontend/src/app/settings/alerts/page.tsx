"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { CostAlert, ManagedDeployment } from "@/types";

export default function AlertsPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<CostAlert[]>([]);
  const [deployments, setDeployments] = useState<ManagedDeployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  // Create form
  const [selectedDeployment, setSelectedDeployment] = useState("");
  const [budget, setBudget] = useState(500);
  const [threshold, setThreshold] = useState(80);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    setAuthChecked(true);
    loadData();
  }, []);

  async function loadData() {
    try {
      const [alertList, depList] = await Promise.all([
        api.listCostAlerts(),
        api.listManagedDeployments(),
      ]);
      setAlerts(alertList);
      setDeployments(depList);
      // Default to first deployment without an alert
      const alertedIds = new Set(alertList.map((a: CostAlert) => a.managed_deployment_id));
      const available = depList.filter((d: ManagedDeployment) => !alertedIds.has(d.id));
      if (available.length > 0) setSelectedDeployment(available[0].id);
    } catch {}
    setLoading(false);
  }

  async function handleCreate() {
    if (!selectedDeployment) return;
    setSaving(true);
    try {
      await api.createCostAlert({
        managed_deployment_id: selectedDeployment,
        monthly_budget_usd: budget,
        alert_threshold_pct: threshold,
      });
      setShowCreate(false);
      await loadData();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(alertId: string) {
    if (!confirm("Remove this cost alert?")) return;
    try {
      await api.deleteCostAlert(alertId);
      await loadData();
    } catch {}
  }

  function getSpendPct(a: CostAlert) {
    return Math.min(100, (a.current_spend_usd / a.monthly_budget_usd) * 100);
  }

  function getSpendColor(pct: number) {
    if (pct >= 80) return "bg-red-500";
    if (pct >= 60) return "bg-yellow-500";
    return "bg-green-500";
  }

  function getSpendTextColor(pct: number) {
    if (pct >= 80) return "text-red-400";
    if (pct >= 60) return "text-yellow-400";
    return "text-green-400";
  }

  if (!authChecked) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    );
  }

  const alertedIds = new Set(alerts.map((a) => a.managed_deployment_id));
  const availableDeployments = deployments.filter((d) => !alertedIds.has(d.id));

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Cost Alerts</h1>
          <p className="mt-2 text-gray-400">
            Set monthly budgets and get alerts when spending approaches thresholds.
          </p>
        </div>
        {availableDeployments.length > 0 && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
          >
            New Alert
          </button>
        )}
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Create Cost Alert</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Deployment</label>
              <select
                value={selectedDeployment}
                onChange={(e) => setSelectedDeployment(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
              >
                {availableDeployments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.cloud_provider.toUpperCase()} - {d.instance_type} ({d.gpu_type})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Monthly Budget ($)</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                min={10}
                step={50}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Alert Threshold (%)</label>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                min={10}
                max={100}
                step={5}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleCreate}
              disabled={saving || !selectedDeployment}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm"
            >
              {saving ? "Creating..." : "Create Alert"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Alerts List */}
      {alerts.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-4xl mb-4 opacity-20">&#9888;</div>
          <p className="text-gray-400">No cost alerts configured yet.</p>
          {deployments.length === 0 ? (
            <p className="text-sm text-gray-500 mt-2">
              Deploy a managed instance first at{" "}
              <a href="/managed" className="text-blue-400 hover:text-blue-300">
                Managed Deployments
              </a>
            </p>
          ) : (
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 text-sm text-blue-400 hover:text-blue-300"
            >
              Create your first alert
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {alerts.map((alert) => {
            const dep = deployments.find((d) => d.id === alert.managed_deployment_id);
            const pct = getSpendPct(alert);
            return (
              <div key={alert.id} className="card">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-semibold">
                      {dep
                        ? `${dep.cloud_provider.toUpperCase()} - ${dep.instance_type}`
                        : alert.managed_deployment_id.slice(0, 8)}
                    </h3>
                    <span className="text-xs text-gray-500">
                      {dep?.gpu_type} x{dep?.gpu_count} &middot; {dep?.region}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {alert.alert_triggered && (
                      <span className="px-2 py-0.5 bg-red-900/30 text-red-400 border border-red-800 rounded-full text-xs font-bold uppercase">
                        Alert Triggered
                      </span>
                    )}
                    <button
                      onClick={() => handleDelete(alert.id)}
                      className="text-xs text-gray-500 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                </div>

                {/* Budget Progress Bar */}
                <div className="mb-2">
                  <div className="flex justify-between text-sm mb-1">
                    <span className={getSpendTextColor(pct)}>
                      ${alert.current_spend_usd.toFixed(2)} spent
                    </span>
                    <span className="text-gray-400">
                      ${alert.monthly_budget_usd.toFixed(2)} budget
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${getSpendColor(pct)}`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>{pct.toFixed(1)}% used</span>
                    <span>Alert at {alert.alert_threshold_pct}%</span>
                  </div>
                </div>

                {/* Threshold Marker */}
                <div className="relative h-1 mb-2">
                  <div
                    className="absolute top-0 w-px h-3 bg-yellow-500 -translate-y-1"
                    style={{ left: `${alert.alert_threshold_pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
