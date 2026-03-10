"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import * as api from "@/lib/api";
import { PipelineCanvas } from "@/components/pipeline/PipelineCanvas";
import type { NodeData } from "@/components/pipeline/PipelineNode";
import type {
  ModelConfig,
  SpecsCalculation,
  HFModelResult,
  HFAdapterResult,
  PopularModel,
} from "@/types";

const STEPS = [
  "Base Model",
  "Adapter",
  "Merge",
  "Quantization",
  "Inference",
  "Review",
];

const QUANT_OPTIONS = [
  { value: "none", label: "None (original precision)" },
  { value: "gptq", label: "GPTQ (INT4, fast)" },
  { value: "awq", label: "AWQ (INT4, quality)" },
  { value: "bnb_int8", label: "BitsAndBytes INT8" },
  { value: "bnb_int4", label: "BitsAndBytes INT4" },
];

const MERGE_METHODS = [
  { value: "linear", label: "Linear", desc: "Weighted average of model parameters" },
  { value: "slerp", label: "SLERP", desc: "Spherical linear interpolation" },
  { value: "ties", label: "TIES", desc: "Trim, elect sign, merge (sparsity-aware)" },
  { value: "dare", label: "DARE", desc: "Drop and rescale (delta-aware)" },
];

export default function ConfigEditorPage() {
  const router = useRouter();
  const params = useParams();
  const configId = params.id as string;

  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [specs, setSpecs] = useState<SpecsCalculation | null>(null);
  const [viewMode, setViewMode] = useState<"wizard" | "pipeline">("wizard");

  // Base model state
  const [popularModels, setPopularModels] = useState<PopularModel[]>([]);
  const [hfSearch, setHfSearch] = useState("");
  const [hfResults, setHfResults] = useState<HFModelResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Adapter state
  const [adapterSearch, setAdapterSearch] = useState("");
  const [adapterResults, setAdapterResults] = useState<HFAdapterResult[]>([]);
  const [adapterSearching, setAdapterSearching] = useState(false);

  // Local form state
  const [form, setForm] = useState({
    base_model_hf_id: "",
    adapter_hf_id: "",
    is_merge: false,
    merge_method: "linear",
    merge_models: [
      { model_hf_id: "", weight: 0.5 },
      { model_hf_id: "", weight: 0.5 },
    ],
    quantization_method: "none",
    system_prompt: "",
    default_temperature: 0.7,
    default_top_p: 0.9,
    default_max_tokens: 512,
  });

  useEffect(() => {
    async function load() {
      if (!api.isAuthenticated()) {
        router.push("/auth");
        return;
      }
      try {
        const [cfg, models] = await Promise.all([
          api.getModelConfig(configId),
          api.getPopularModels(),
        ]);
        setConfig(cfg);
        setPopularModels(models);
        setForm({
          base_model_hf_id: cfg.base_model_hf_id || "",
          adapter_hf_id: cfg.adapter_hf_id || "",
          is_merge: cfg.is_merge,
          merge_method: cfg.merge_method || "linear",
          merge_models:
            cfg.merge_models_json && cfg.merge_models_json.length >= 2
              ? cfg.merge_models_json
              : [
                  { model_hf_id: "", weight: 0.5 },
                  { model_hf_id: "", weight: 0.5 },
                ],
          quantization_method: cfg.quantization_method || "none",
          system_prompt: cfg.system_prompt || "",
          default_temperature: cfg.default_temperature,
          default_top_p: cfg.default_top_p,
          default_max_tokens: cfg.default_max_tokens,
        });
      } catch (err: any) {
        setError(err.message);
      }
      setLoading(false);
    }
    load();
  }, [configId, router]);

  const saveConfig = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await api.updateModelConfig(configId, {
        base_model_hf_id: form.base_model_hf_id || null,
        adapter_hf_id: form.is_merge ? null : form.adapter_hf_id || null,
        is_merge: form.is_merge,
        merge_method: form.is_merge ? form.merge_method : null,
        merge_models: form.is_merge
          ? form.merge_models.filter((m) => m.model_hf_id)
          : null,
        quantization_method: form.quantization_method,
        system_prompt: form.system_prompt || null,
        default_temperature: form.default_temperature,
        default_top_p: form.default_top_p,
        default_max_tokens: form.default_max_tokens,
      });
      setConfig(updated);
      setError("");
    } catch (err: any) {
      setError(err.message);
    }
    setSaving(false);
  }, [configId, form]);

  async function handleSearchModels() {
    if (!hfSearch.trim()) return;
    setSearching(true);
    try {
      const results = await api.searchHFModels(hfSearch);
      setHfResults(results);
    } catch {
      /* ignore */
    }
    setSearching(false);
  }

  async function handleSearchAdapters() {
    if (!adapterSearch.trim()) return;
    setAdapterSearching(true);
    try {
      const results = await api.searchHFAdapters(adapterSearch);
      setAdapterResults(results);
    } catch {
      /* ignore */
    }
    setAdapterSearching(false);
  }

  async function handleCalculateSpecs() {
    try {
      await saveConfig();
      const result = await api.calculateConfigSpecs(configId);
      setSpecs(result);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleSaveToLibrary() {
    try {
      if (!specs) await handleCalculateSpecs();
      const result = await api.promoteConfigToModel(configId);
      alert(result.message);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleSaveVersion() {
    try {
      await saveConfig();
      await api.saveConfigVersion(configId, `Version from editor`);
      const cfg = await api.getModelConfig(configId);
      setConfig(cfg);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function nextStep() {
    saveConfig();
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }
  function prevStep() {
    setStep((s) => Math.max(s - 1, 0));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-400">Loading configuration...</div>
      </div>
    );
  }
  if (!config) {
    return (
      <div className="py-20 text-center text-red-400">
        Configuration not found. {error}
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => router.push("/builder")}
            className="text-sm text-gray-400 hover:text-white mb-1"
          >
            &larr; Back to Builder
          </button>
          <h1 className="text-xl font-bold text-white">{config.name}</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSaveVersion}
            className="rounded-lg border border-gray-600 px-3 py-1.5 text-sm text-gray-300 hover:text-white transition"
          >
            Save Version (v{config.version})
          </button>
          <button
            onClick={saveConfig}
            disabled={saving}
            className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-500 transition disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* View mode toggle */}
      <div className="flex gap-1 mb-4 bg-gray-900 rounded-lg p-1 w-fit">
        <button
          onClick={() => setViewMode("wizard")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            viewMode === "wizard" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Wizard
        </button>
        <button
          onClick={() => setViewMode("pipeline")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
            viewMode === "pipeline" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Pipeline View
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-900/30 border border-red-800 px-4 py-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {viewMode === "pipeline" ? (
        <PipelineCanvas
          configName={config.name}
          initialNodes={config.pipeline_json?.nodes || undefined}
          onSave={async (nodes: NodeData[]) => {
            try {
              // Sync pipeline node configs back to the form/config
              const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
              const baseNode = nodeMap["base_model"];
              const adapterNode = nodeMap["adapter"];
              const mergeNode = nodeMap["merge"];
              const quantNode = nodeMap["quantization"];
              const inferNode = nodeMap["inference"];
              await api.updateModelConfig(configId, {
                base_model_hf_id: baseNode?.config.base_model_hf_id || form.base_model_hf_id,
                adapter_hf_id: adapterNode?.enabled ? adapterNode.config.adapter_hf_id : "",
                is_merge: mergeNode?.enabled || false,
                merge_method: mergeNode?.config.merge_method || "linear",
                merge_models_json: mergeNode?.enabled ? mergeNode.config.merge_models : [],
                quantization_method: quantNode?.config.quantization_method || "none",
                system_prompt: inferNode?.config.system_prompt || "",
                default_temperature: inferNode?.config.default_temperature ?? 0.7,
                default_max_tokens: inferNode?.config.default_max_tokens ?? 512,
                pipeline_json: { nodes },
              });
              const updated = await api.getModelConfig(configId);
              setConfig(updated);
            } catch (e: any) {
              setError(e.message || "Failed to save pipeline");
            }
          }}
        />
      ) : (
      <>

      {/* Step indicators */}
      <div className="flex gap-1 mb-8">
        {STEPS.map((s, i) => (
          <button
            key={s}
            onClick={() => setStep(i)}
            className={`flex-1 py-2 text-xs font-medium rounded transition ${
              i === step
                ? "bg-brand-600/20 text-brand-400 border border-brand-500/30"
                : i < step
                ? "bg-gray-800 text-gray-300 border border-gray-700"
                : "bg-gray-900 text-gray-500 border border-gray-800"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Step content */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 min-h-[400px]">
        {/* Step 0: Base Model */}
        {step === 0 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">
              Choose Base Model
            </h2>

            {/* Popular models */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-300 mb-3">
                Popular Models
              </h3>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {popularModels.slice(0, 9).map((m) => (
                  <button
                    key={m.id}
                    onClick={() =>
                      setForm({ ...form, base_model_hf_id: m.id })
                    }
                    className={`text-left rounded-lg border p-3 text-sm transition ${
                      form.base_model_hf_id === m.id
                        ? "border-brand-500 bg-brand-600/10 text-white"
                        : "border-gray-700 text-gray-300 hover:border-gray-500"
                    }`}
                  >
                    <div className="font-medium">{m.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {m.parameters_billion}B params &middot;{" "}
                      {m.context_length.toLocaleString()} ctx
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* HuggingFace search */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">
                Search HuggingFace
              </h3>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={hfSearch}
                  onChange={(e) => setHfSearch(e.target.value)}
                  placeholder="Search models..."
                  className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                  onKeyDown={(e) => e.key === "Enter" && handleSearchModels()}
                />
                <button
                  onClick={handleSearchModels}
                  disabled={searching}
                  className="rounded-lg bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600 transition"
                >
                  {searching ? "..." : "Search"}
                </button>
              </div>
              {hfResults.length > 0 && (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {hfResults.map((r) => (
                    <button
                      key={r.model_id}
                      onClick={() =>
                        setForm({ ...form, base_model_hf_id: r.model_id })
                      }
                      className={`w-full text-left rounded px-3 py-2 text-sm transition ${
                        form.base_model_hf_id === r.model_id
                          ? "bg-brand-600/20 text-brand-400"
                          : "text-gray-300 hover:bg-gray-700"
                      }`}
                    >
                      <span className="font-medium">{r.model_id}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        {r.downloads.toLocaleString()} downloads
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {form.base_model_hf_id && (
              <div className="mt-4 p-3 rounded-lg bg-brand-600/10 border border-brand-500/30">
                <span className="text-sm text-gray-300">Selected: </span>
                <span className="text-sm font-medium text-brand-400">
                  {form.base_model_hf_id}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Step 1: LoRA Adapter */}
        {step === 1 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-2">
              LoRA Adapter
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Optionally add a LoRA adapter for task-specific fine-tuning
              without modifying the base model.
            </p>

            {form.is_merge && (
              <div className="p-3 rounded-lg bg-yellow-900/20 border border-yellow-800/40 text-yellow-300 text-sm mb-4">
                Adapters are disabled when model merging is enabled. Disable
                merge to add an adapter.
              </div>
            )}

            {!form.is_merge && (
              <>
                <div className="flex gap-2 mb-3">
                  <input
                    type="text"
                    value={adapterSearch}
                    onChange={(e) => setAdapterSearch(e.target.value)}
                    placeholder="Search LoRA adapters on HuggingFace..."
                    className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                    onKeyDown={(e) =>
                      e.key === "Enter" && handleSearchAdapters()
                    }
                  />
                  <button
                    onClick={handleSearchAdapters}
                    disabled={adapterSearching}
                    className="rounded-lg bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600 transition"
                  >
                    {adapterSearching ? "..." : "Search"}
                  </button>
                </div>

                {adapterResults.length > 0 && (
                  <div className="space-y-1 max-h-48 overflow-y-auto mb-4">
                    {adapterResults.map((r) => (
                      <button
                        key={r.adapter_id}
                        onClick={() =>
                          setForm({ ...form, adapter_hf_id: r.adapter_id })
                        }
                        className={`w-full text-left rounded px-3 py-2 text-sm transition ${
                          form.adapter_hf_id === r.adapter_id
                            ? "bg-purple-600/20 text-purple-300"
                            : "text-gray-300 hover:bg-gray-700"
                        }`}
                      >
                        <span className="font-medium">{r.adapter_id}</span>
                        {r.base_model && (
                          <span className="text-xs text-gray-500 ml-2">
                            base: {r.base_model}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}

                <div className="mt-2">
                  <label className="block text-sm text-gray-300 mb-1">
                    Or enter adapter ID directly
                  </label>
                  <input
                    type="text"
                    value={form.adapter_hf_id}
                    onChange={(e) =>
                      setForm({ ...form, adapter_hf_id: e.target.value })
                    }
                    placeholder="e.g. username/my-lora-adapter"
                    className="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                  />
                </div>

                {form.adapter_hf_id && (
                  <div className="mt-3 flex items-center gap-2">
                    <span className="text-xs bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded">
                      LoRA: {form.adapter_hf_id}
                    </span>
                    <button
                      onClick={() => setForm({ ...form, adapter_hf_id: "" })}
                      className="text-xs text-gray-500 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Step 2: Model Merge */}
        {step === 2 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-2">
              Model Merging
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Combine multiple models into one using advanced merge techniques.
              The merge happens at build time during deployment.
            </p>

            <label className="flex items-center gap-3 mb-6">
              <input
                type="checkbox"
                checked={form.is_merge}
                onChange={(e) =>
                  setForm({ ...form, is_merge: e.target.checked })
                }
                className="rounded border-gray-600 bg-gray-900 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-300">
                Enable model merging
              </span>
            </label>

            {form.is_merge && (
              <>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Merge Method
                  </label>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {MERGE_METHODS.map((m) => (
                      <button
                        key={m.value}
                        onClick={() =>
                          setForm({ ...form, merge_method: m.value })
                        }
                        className={`text-left rounded-lg border p-3 transition ${
                          form.merge_method === m.value
                            ? "border-brand-500 bg-brand-600/10"
                            : "border-gray-700 hover:border-gray-500"
                        }`}
                      >
                        <div className="text-sm font-medium text-white">
                          {m.label}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">
                          {m.desc}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Models to Merge
                  </label>
                  {form.merge_models.map((m, i) => (
                    <div key={i} className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={m.model_hf_id}
                        onChange={(e) => {
                          const models = [...form.merge_models];
                          models[i] = {
                            ...models[i],
                            model_hf_id: e.target.value,
                          };
                          setForm({ ...form, merge_models: models });
                        }}
                        placeholder="HuggingFace model ID"
                        className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                      />
                      <input
                        type="number"
                        value={m.weight}
                        onChange={(e) => {
                          const models = [...form.merge_models];
                          models[i] = {
                            ...models[i],
                            weight: parseFloat(e.target.value) || 0,
                          };
                          setForm({ ...form, merge_models: models });
                        }}
                        step="0.1"
                        min="0"
                        max="1"
                        className="w-20 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white text-center focus:border-brand-500 focus:outline-none"
                      />
                      {form.merge_models.length > 2 && (
                        <button
                          onClick={() => {
                            const models = form.merge_models.filter(
                              (_, j) => j !== i
                            );
                            setForm({ ...form, merge_models: models });
                          }}
                          className="text-red-400 hover:text-red-300 text-sm px-2"
                        >
                          X
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    onClick={() =>
                      setForm({
                        ...form,
                        merge_models: [
                          ...form.merge_models,
                          { model_hf_id: "", weight: 0.5 },
                        ],
                      })
                    }
                    className="text-sm text-brand-400 hover:text-brand-300 mt-1"
                  >
                    + Add Model
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Step 3: Quantization */}
        {step === 3 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-2">
              Quantization
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Reduce model precision to lower VRAM usage and cost. Trade-off:
              slight quality reduction.
            </p>
            <div className="space-y-2">
              {QUANT_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-center gap-3 rounded-lg border p-4 cursor-pointer transition ${
                    form.quantization_method === opt.value
                      ? "border-brand-500 bg-brand-600/10"
                      : "border-gray-700 hover:border-gray-500"
                  }`}
                >
                  <input
                    type="radio"
                    name="quantization"
                    value={opt.value}
                    checked={form.quantization_method === opt.value}
                    onChange={() =>
                      setForm({ ...form, quantization_method: opt.value })
                    }
                    className="text-brand-600 focus:ring-brand-500"
                  />
                  <span className="text-sm text-white">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Inference Config */}
        {step === 4 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">
              Inference Configuration
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  System Prompt
                </label>
                <textarea
                  value={form.system_prompt}
                  onChange={(e) =>
                    setForm({ ...form, system_prompt: e.target.value })
                  }
                  rows={4}
                  placeholder="You are a helpful assistant..."
                  className="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Temperature ({form.default_temperature})
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={form.default_temperature}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        default_temperature: parseFloat(e.target.value),
                      })
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Top P ({form.default_top_p})
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={form.default_top_p}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        default_top_p: parseFloat(e.target.value),
                      })
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Max Tokens
                  </label>
                  <input
                    type="number"
                    value={form.default_max_tokens}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        default_max_tokens: parseInt(e.target.value) || 512,
                      })
                    }
                    className="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div>
            <h2 className="text-lg font-semibold text-white mb-4">
              Configuration Review
            </h2>

            <div className="grid gap-4 sm:grid-cols-2 mb-6">
              <div className="rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">
                  Base Model
                </h3>
                <p className="text-white">
                  {form.base_model_hf_id || "Not selected"}
                </p>
              </div>

              <div className="rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">
                  Adapter
                </h3>
                <p className="text-white">
                  {form.adapter_hf_id || (form.is_merge ? "N/A (merging)" : "None")}
                </p>
              </div>

              <div className="rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">
                  Merge
                </h3>
                <p className="text-white">
                  {form.is_merge
                    ? `${form.merge_method.toUpperCase()} — ${form.merge_models.filter((m) => m.model_hf_id).length} models`
                    : "Disabled"}
                </p>
              </div>

              <div className="rounded-lg border border-gray-700 p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">
                  Quantization
                </h3>
                <p className="text-white">
                  {form.quantization_method === "none"
                    ? "None"
                    : form.quantization_method.toUpperCase()}
                </p>
              </div>
            </div>

            {/* Calculate specs */}
            <div className="mb-6">
              <button
                onClick={handleCalculateSpecs}
                className="rounded-lg bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600 transition"
              >
                Calculate Effective Specs
              </button>

              {specs && (
                <div className="mt-4 rounded-lg border border-brand-500/30 bg-brand-600/10 p-4">
                  <h3 className="text-sm font-medium text-brand-400 mb-3">
                    Computed Specs
                  </h3>
                  <div className="grid gap-3 sm:grid-cols-3 text-sm">
                    <div>
                      <span className="text-gray-400">Parameters: </span>
                      <span className="text-white font-medium">
                        {specs.effective_parameters_billion}B
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Precision: </span>
                      <span className="text-white font-medium">
                        {specs.effective_precision.toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Context: </span>
                      <span className="text-white font-medium">
                        {specs.effective_context_length.toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Total VRAM: </span>
                      <span className="text-white font-medium">
                        {specs.estimated_vram_gb} GB
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Base VRAM: </span>
                      <span className="text-white font-medium">
                        {specs.base_vram_gb} GB
                      </span>
                    </div>
                    {specs.adapter_overhead_gb > 0 && (
                      <div>
                        <span className="text-gray-400">
                          Adapter overhead:{" "}
                        </span>
                        <span className="text-white font-medium">
                          +{specs.adapter_overhead_gb} GB
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={handleSaveToLibrary}
                className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-500 transition"
              >
                Save to Model Library
              </button>
              <button
                onClick={() => router.push("/estimate")}
                className="rounded-lg border border-gray-600 px-4 py-2.5 text-sm text-gray-300 hover:text-white transition"
              >
                Estimate Cost
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between mt-6">
        <button
          onClick={prevStep}
          disabled={step === 0}
          className="rounded-lg border border-gray-600 px-4 py-2 text-sm text-gray-300 hover:text-white transition disabled:opacity-30"
        >
          Previous
        </button>
        <button
          onClick={nextStep}
          disabled={step === STEPS.length - 1}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 transition disabled:opacity-30"
        >
          Next
        </button>
      </div>
      </>
      )}
    </div>
  );
}
