"use client";

import { useState } from "react";
import Link from "next/link";
import type { RecommendationResult } from "@/types";
import * as api from "@/lib/api";

const USE_CASES = [
  { value: "general", label: "General Purpose" },
  { value: "coding", label: "Coding" },
  { value: "chat", label: "Chat / Conversation" },
  { value: "reasoning", label: "Reasoning / Logic" },
  { value: "multilingual", label: "Multilingual" },
  { value: "summarization", label: "Summarization" },
];

const QUALITY_BADGE: Record<string, string> = {
  good: "bg-gray-700 text-gray-300",
  great: "bg-blue-900/40 text-blue-400",
  excellent: "bg-purple-900/40 text-purple-400",
};

export default function RecommendPage() {
  const [useCase, setUseCase] = useState("general");
  const [budget, setBudget] = useState(1000);
  const [provider, setProvider] = useState("");
  const [results, setResults] = useState<RecommendationResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  async function search() {
    setLoading(true);
    try {
      const res = await api.recommendModels({
        use_case: useCase,
        max_budget_monthly: budget,
        cloud_provider: provider || undefined,
      });
      setResults(res.results);
      setSearched(true);
    } catch {}
    setLoading(false);
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">Model Recommender</h1>
      <p className="mt-2 text-gray-400">
        Find the best open-source model for your use case and budget.
      </p>

      <div className="mt-6 card max-w-2xl space-y-4">
        <div>
          <label className="label">Use Case</label>
          <select className="input" value={useCase} onChange={(e) => setUseCase(e.target.value)}>
            {USE_CASES.map((uc) => (
              <option key={uc.value} value={uc.value}>{uc.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Max Monthly Budget ($)</label>
          <input
            className="input"
            type="number"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            placeholder="e.g. 1000"
          />
        </div>

        <div>
          <label className="label">Cloud Provider (optional)</label>
          <div className="flex gap-2">
            <button
              onClick={() => setProvider("")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                !provider ? "bg-brand-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              Any
            </button>
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

        <button onClick={search} disabled={loading} className="btn-primary w-full">
          {loading ? "Searching..." : "Find Models"}
        </button>
      </div>

      {searched && (
        <div className="mt-8">
          {results.length === 0 ? (
            <div className="card text-center text-gray-400 py-8">
              No models found within ${budget.toLocaleString()}/mo for {useCase}. Try a higher budget.
            </div>
          ) : (
            <div className="space-y-4">
              <h2 className="text-xl font-bold">
                Top {results.length} Models for {USE_CASES.find((u) => u.value === useCase)?.label}
              </h2>
              {results.map((r, i) => (
                <div key={r.model_name} className="card flex items-start gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-900/40 text-brand-400 font-bold text-lg flex-shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-white">{r.model_name}</h3>
                      <span className="text-xs text-gray-500">{r.parameters_billion}B</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${QUALITY_BADGE[r.quality_tier] || QUALITY_BADGE.good}`}>
                        {r.quality_tier}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.tags.map((tag) => (
                        <span key={tag} className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-gray-400 sm:grid-cols-4">
                      <div>
                        <span className="text-gray-500">Provider:</span>{" "}
                        <span className="text-gray-300">{r.cloud_provider.toUpperCase()}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">GPU:</span>{" "}
                        <span className="text-gray-300">{r.gpu_type} x{r.gpu_count}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">VRAM:</span>{" "}
                        <span className="text-gray-300">{r.vram_required_gb.toFixed(1)} GB</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Instance:</span>{" "}
                        <span className="text-gray-300">{r.instance_type}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-xl font-bold text-white">${r.monthly_cost.toLocaleString()}</div>
                    <div className="text-xs text-gray-500">/month</div>
                    <Link
                      href={`/estimate?model=${encodeURIComponent(r.model_name)}&params=${r.parameters_billion}&ctx=4096`}
                      className="mt-2 inline-block rounded-lg bg-brand-600/80 px-3 py-1 text-xs font-medium text-white hover:bg-brand-600 transition"
                    >
                      Full Estimate
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
