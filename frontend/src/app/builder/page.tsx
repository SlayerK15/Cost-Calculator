"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { ModelConfig, SubscriptionStatus } from "@/types";

export default function BuilderPage() {
  const router = useRouter();
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState<string>("free");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      if (!api.isAuthenticated()) {
        router.push("/auth");
        return;
      }
      try {
        const status = await api.getSubscriptionStatus();
        setTier(status.tier);
        if (status.tier === "free") {
          setLoading(false);
          return;
        }
        const list = await api.listModelConfigs();
        setConfigs(list);
      } catch (err: any) {
        if (err.message?.includes("403")) {
          setTier("free");
        } else {
          setError(err.message);
        }
      }
      setLoading(false);
    }
    load();
  }, [router]);

  async function handleCreate() {
    if (!newName.trim()) return;
    try {
      const config = await api.createModelConfig({ name: newName.trim() });
      router.push(`/builder/${config.id}`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (tier === "free") {
    return (
      <div className="py-20 text-center">
        <h1 className="text-3xl font-bold text-white mb-4">
          No-Code Model Builder
        </h1>
        <p className="text-gray-400 mb-8 max-w-xl mx-auto">
          Compose custom LLM configurations with LoRA adapters, model merging,
          quantization, and more. Available on the PRO plan.
        </p>
        <button
          onClick={() => router.push("/pricing")}
          className="rounded-lg bg-brand-600 px-6 py-3 text-white font-medium hover:bg-brand-500 transition"
        >
          Upgrade to PRO
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Model Builder</h1>
          <p className="text-gray-400 mt-1">
            Compose, configure, and save custom LLM configurations
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 transition"
        >
          + New Configuration
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-900/30 border border-red-800 px-4 py-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {creating && (
        <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Configuration Name
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. My Custom Llama 3.1"
              className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-white text-sm focus:border-brand-500 focus:outline-none"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              autoFocus
            />
            <button
              onClick={handleCreate}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 transition"
            >
              Create
            </button>
            <button
              onClick={() => {
                setCreating(false);
                setNewName("");
              }}
              className="rounded-lg border border-gray-600 px-4 py-2 text-sm text-gray-400 hover:text-white transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {configs.length === 0 && !creating ? (
        <div className="text-center py-16 border border-dashed border-gray-700 rounded-lg">
          <p className="text-gray-400 mb-4">No configurations yet</p>
          <button
            onClick={() => setCreating(true)}
            className="text-brand-400 hover:text-brand-300 text-sm font-medium"
          >
            Create your first model configuration
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {configs.map((config) => (
            <button
              key={config.id}
              onClick={() => router.push(`/builder/${config.id}`)}
              className="text-left rounded-lg border border-gray-700 bg-gray-800/50 p-5 hover:border-brand-500/50 hover:bg-gray-800 transition"
            >
              <h3 className="font-semibold text-white truncate">
                {config.name}
              </h3>
              {config.description && (
                <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                  {config.description}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {config.base_model_hf_id && (
                  <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                    {config.base_model_hf_id.split("/").pop()}
                  </span>
                )}
                {config.adapter_hf_id && (
                  <span className="text-xs bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded">
                    LoRA
                  </span>
                )}
                {config.is_merge && (
                  <span className="text-xs bg-blue-900/40 text-blue-300 px-2 py-0.5 rounded">
                    Merge ({config.merge_method})
                  </span>
                )}
                {config.quantization_method !== "none" && (
                  <span className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">
                    {config.quantization_method.toUpperCase()}
                  </span>
                )}
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                <span>v{config.version}</span>
                {config.estimated_vram_gb && (
                  <span>{config.estimated_vram_gb} GB VRAM</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
