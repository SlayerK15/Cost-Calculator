"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  isAuthenticated,
  listManagedDeployments,
  listDeployments,
  listCredentials,
  createManagedDeployment,
  getSubscriptionStatus,
} from "@/lib/api";
import type { ManagedDeployment, Deployment, CloudCredential } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-green-900/50 text-green-400",
  provisioning_infra: "bg-blue-900/50 text-blue-400",
  building_image: "bg-blue-900/50 text-blue-400",
  deploying_model: "bg-blue-900/50 text-blue-400",
  scaling: "bg-yellow-900/50 text-yellow-400",
  stopped: "bg-gray-800 text-gray-400",
  failed: "bg-red-900/50 text-red-400",
  terminated: "bg-red-900/50 text-red-400",
};

export default function ManagedDeploymentsPage() {
  const router = useRouter();
  const [tier, setTier] = useState<string>("free");
  const [managedDeps, setManagedDeps] = useState<ManagedDeployment[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [credentials, setCredentials] = useState<CloudCredential[]>([]);
  const [loading, setLoading] = useState(true);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [selectedDep, setSelectedDep] = useState("");
  const [selectedCred, setSelectedCred] = useState("");
  const [autoscaling, setAutoscaling] = useState(false);
  const [minReplicas, setMinReplicas] = useState(1);
  const [maxReplicas, setMaxReplicas] = useState(3);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    loadData();
  }, []);

  async function loadData() {
    try {
      const sub = await getSubscriptionStatus();
      setTier(sub.tier);
      if (sub.tier === "enterprise") {
        const [managed, deps, creds] = await Promise.all([
          listManagedDeployments(),
          listDeployments(),
          listCredentials(),
        ]);
        setManagedDeps(managed);
        setDeployments(deps);
        setCredentials(creds);
      }
    } catch {
      // error
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!selectedDep || !selectedCred) return;
    setError("");
    setCreating(true);
    try {
      await createManagedDeployment({
        deployment_id: selectedDep,
        credential_id: selectedCred,
        autoscaling_enabled: autoscaling,
        min_replicas: minReplicas,
        max_replicas: maxReplicas,
      });
      setShowCreate(false);
      await loadData();
    } catch (e: any) {
      setError(e.message || "Failed to create managed deployment");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    );
  }

  if (tier !== "enterprise") {
    return (
      <div className="min-h-screen bg-gray-950 text-white p-8">
        <div className="max-w-2xl mx-auto text-center mt-20">
          <div className="text-6xl mb-4">🚀</div>
          <h1 className="text-3xl font-bold mb-4">Managed Cloud Deployment</h1>
          <p className="text-gray-400 mb-8">
            Let us provision and manage your LLM infrastructure. Auto-scaling, monitoring, and one-click teardown included.
          </p>
          <button
            onClick={() => router.push("/pricing")}
            className="px-6 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg font-medium"
          >
            Upgrade to Enterprise
          </button>
        </div>
      </div>
    );
  }

  const validCredentials = credentials.filter((c) => c.status === "valid");

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Managed Deployments</h1>
            <p className="text-gray-400 mt-1">
              Fully managed LLM infrastructure with monitoring and auto-scaling
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push("/settings/credentials")}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm"
            >
              Manage Credentials
            </button>
            <button
              onClick={() => setShowCreate(true)}
              disabled={validCredentials.length === 0 || deployments.length === 0}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-medium"
            >
              + New Managed Deploy
            </button>
          </div>
        </div>

        {/* Warnings */}
        {validCredentials.length === 0 && (
          <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg p-4 mb-6 text-yellow-300 text-sm">
            No validated cloud credentials found.{" "}
            <button
              onClick={() => router.push("/settings/credentials")}
              className="text-yellow-200 underline"
            >
              Add and validate credentials
            </button>{" "}
            before creating a managed deployment.
          </div>
        )}

        {deployments.length === 0 && (
          <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-4 mb-6 text-blue-300 text-sm">
            No deployment configs found.{" "}
            <button
              onClick={() => router.push("/deploy")}
              className="text-blue-200 underline"
            >
              Create a deployment configuration
            </button>{" "}
            first using the Self-Deploy wizard.
          </div>
        )}

        {/* Create Form */}
        {showCreate && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">Create Managed Deployment</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Deployment Config</label>
                <select
                  value={selectedDep}
                  onChange={(e) => setSelectedDep(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">Select a deployment...</option>
                  {deployments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.cloud_provider.toUpperCase()} - {d.instance_type} ({d.gpu_type} x{d.gpu_count})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Cloud Credential</label>
                <select
                  value={selectedCred}
                  onChange={(e) => setSelectedCred(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">Select credentials...</option>
                  {validCredentials.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label} ({c.provider.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={autoscaling}
                  onChange={(e) => setAutoscaling(e.target.checked)}
                  className="rounded"
                />
                Enable Auto-scaling
              </label>
              {autoscaling && (
                <>
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-gray-400">Min:</label>
                    <input
                      type="number"
                      value={minReplicas}
                      onChange={(e) => setMinReplicas(Number(e.target.value))}
                      min={1}
                      max={10}
                      className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-gray-400">Max:</label>
                    <input
                      type="number"
                      value={maxReplicas}
                      onChange={(e) => setMaxReplicas(Number(e.target.value))}
                      min={1}
                      max={20}
                      className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                    />
                  </div>
                </>
              )}
            </div>

            {error && (
              <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg p-3 mt-4">
                {error}
              </div>
            )}

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleCreate}
                disabled={creating || !selectedDep || !selectedCred}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg font-medium"
              >
                {creating ? "Deploying..." : "Deploy to Cloud"}
              </button>
              <button
                onClick={() => { setShowCreate(false); setError(""); }}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Managed Deployments List */}
        {managedDeps.length === 0 && !showCreate ? (
          <div className="text-center py-16 text-gray-500">
            <div className="text-5xl mb-4">🌩️</div>
            <p className="text-lg">No managed deployments yet</p>
            <p className="text-sm mt-1">
              Create a self-deploy config, add cloud credentials, then launch a managed deployment
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {managedDeps.map((m) => (
              <div
                key={m.id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 cursor-pointer transition-colors"
                onClick={() => router.push(`/managed/${m.id}`)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-lg">
                          {m.cloud_provider.toUpperCase()} - {m.instance_type}
                        </h3>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[m.status] || "bg-gray-800 text-gray-400"}`}>
                          {m.status.replace(/_/g, " ").toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 mt-1">
                        {m.gpu_type} x{m.gpu_count} &middot; {m.region} &middot;
                        Health: <span className={m.health_status === "healthy" ? "text-green-400" : "text-gray-400"}>{m.health_status}</span>
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">${m.estimated_hourly_cost.toFixed(2)}/hr</div>
                    <div className="text-sm text-gray-400">
                      {m.autoscaling_enabled
                        ? `Auto-scale ${m.min_replicas}-${m.max_replicas} replicas`
                        : `${m.min_replicas} replica(s)`}
                    </div>
                  </div>
                </div>
                {m.cluster_endpoint && (
                  <div className="mt-3 text-xs text-gray-500 font-mono bg-gray-800 rounded px-3 py-1.5 inline-block">
                    {m.cluster_endpoint}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
