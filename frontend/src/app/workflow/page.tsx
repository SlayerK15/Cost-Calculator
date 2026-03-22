"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";

const STEPS = [
  { key: "pending", label: "Queued", icon: "1" },
  { key: "searching", label: "Finding Knowledge", icon: "2" },
  { key: "training", label: "Fine-tuning", icon: "3" },
  { key: "deploying", label: "Deploying", icon: "4" },
  { key: "completed", label: "Complete", icon: "5" },
];

function StepIndicator({ currentStatus }: { currentStatus: string }) {
  const stepOrder = STEPS.map((s) => s.key);
  const currentIdx = stepOrder.indexOf(currentStatus);
  const isFailed = currentStatus === "failed";

  return (
    <div className="flex items-center gap-2">
      {STEPS.map((step, i) => {
        const isActive = i === currentIdx && !isFailed;
        const isDone = i < currentIdx && !isFailed;
        const isCurrent = i === currentIdx;

        return (
          <div key={step.key} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition
                ${isDone ? "bg-green-600 text-white" : ""}
                ${isActive ? "bg-brand-600 text-white ring-2 ring-brand-400 animate-pulse" : ""}
                ${!isDone && !isActive ? "bg-gray-800 text-gray-500" : ""}
                ${isFailed && isCurrent ? "bg-red-600 text-white" : ""}
              `}
            >
              {isDone ? "\u2713" : step.icon}
            </div>
            <span
              className={`text-xs hidden sm:inline ${
                isActive ? "text-brand-400 font-medium" : isDone ? "text-green-400" : "text-gray-600"
              }`}
            >
              {step.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`h-px w-6 ${isDone ? "bg-green-600" : "bg-gray-700"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function WorkflowPage() {
  const [domain, setDomain] = useState("");
  const [useCase, setUseCase] = useState("");
  const [baseModel, setBaseModel] = useState("");
  const [runs, setRuns] = useState<any[]>([]);
  const [activeRun, setActiveRun] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchRuns = useCallback(async () => {
    try {
      const data = await api.listWorkflowRuns();
      setRuns(data);
    } catch {
      // Ignore — user may not be logged in
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Poll active run for status updates
  useEffect(() => {
    if (!activeRun || activeRun.status === "completed" || activeRun.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const updated = await api.getWorkflowRun(activeRun.id);
        setActiveRun(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          fetchRuns();
        }
      } catch {
        // ignore
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [activeRun, fetchRuns]);

  async function handleTrigger(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim() || !useCase.trim()) return;

    setLoading(true);
    setError("");
    try {
      const run = await api.triggerWorkflow({
        domain: domain.trim(),
        use_case: useCase.trim(),
        base_model: baseModel.trim() || undefined,
      });
      setActiveRun(run);
      setDomain("");
      setUseCase("");
      setBaseModel("");
      fetchRuns();
    } catch (err: any) {
      setError(err.message || "Failed to trigger workflow");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Autonomous LLM Builder</h1>
        <p className="mt-1 text-gray-400">
          Describe your problem and let AI find knowledge, build a dataset, fine-tune, and deploy a model for you.
        </p>
      </div>

      {/* Trigger Form */}
      <form onSubmit={handleTrigger} className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">Start New Workflow</h2>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Domain</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="e.g., Medical diagnosis, Legal contracts, Customer support"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-white placeholder:text-gray-500 focus:border-brand-500 focus:outline-none"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Use Case</label>
          <textarea
            value={useCase}
            onChange={(e) => setUseCase(e.target.value)}
            placeholder="Describe what you want the model to do..."
            rows={3}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-white placeholder:text-gray-500 focus:border-brand-500 focus:outline-none resize-none"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Base Model <span className="text-gray-500">(optional)</span>
          </label>
          <input
            type="text"
            value={baseModel}
            onChange={(e) => setBaseModel(e.target.value)}
            placeholder="e.g., llama3.1:8b-instruct-q4_K_M (defaults to best match)"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-white placeholder:text-gray-500 focus:border-brand-500 focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50 transition"
        >
          {loading ? "Starting..." : "Launch Workflow"}
        </button>
      </form>

      {/* Active Run Tracker */}
      {activeRun && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Current Run</h2>
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase ${
              activeRun.status === "completed" ? "bg-green-900/50 text-green-400" :
              activeRun.status === "failed" ? "bg-red-900/50 text-red-400" :
              "bg-brand-900/50 text-brand-400"
            }`}>
              {activeRun.status}
            </span>
          </div>

          <StepIndicator currentStatus={activeRun.status} />

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Domain:</span>{" "}
              <span className="text-gray-200">{activeRun.domain}</span>
            </div>
            <div>
              <span className="text-gray-500">Base Model:</span>{" "}
              <span className="text-gray-200">{activeRun.base_model || "Auto-select"}</span>
            </div>
          </div>

          {activeRun.error_message && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-sm text-red-300">
              {activeRun.error_message}
            </div>
          )}

          {activeRun.result_snapshot && (
            <div className="rounded-lg border border-green-800/50 bg-green-900/20 p-4 space-y-2">
              <h3 className="text-sm font-medium text-green-400">Result</h3>
              <pre className="text-xs text-gray-300 overflow-auto max-h-48">
                {JSON.stringify(activeRun.result_snapshot, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Run History */}
      {runs.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Previous Runs</h2>
          <div className="space-y-3">
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setActiveRun(run)}
                className="w-full flex items-center justify-between rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-3 text-left hover:border-gray-700 transition"
              >
                <div>
                  <span className="text-sm font-medium text-white">{run.domain}</span>
                  <span className="ml-2 text-xs text-gray-500">{run.use_case.slice(0, 60)}{run.use_case.length > 60 ? "..." : ""}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {new Date(run.created_at).toLocaleDateString()}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    run.status === "completed" ? "bg-green-900/50 text-green-400" :
                    run.status === "failed" ? "bg-red-900/50 text-red-400" :
                    "bg-yellow-900/50 text-yellow-400"
                  }`}>
                    {run.status}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
