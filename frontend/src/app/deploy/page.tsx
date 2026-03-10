"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  isAuthenticated,
  getSubscriptionStatus,
  listModelConfigs,
  listModels,
  generateDeployFromConfig,
  generateDeployConfigs,
  getDeployBundleUrl,
  listDeployments,
} from "@/lib/api";
import type {
  ModelConfig,
  LLMModel,
  DeploymentConfig,
  Deployment,
  SubscriptionStatus,
} from "@/types";

const CLOUD_PROVIDERS = [
  { id: "aws", name: "Amazon Web Services", icon: "AWS", regions: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"] },
  { id: "gcp", name: "Google Cloud Platform", icon: "GCP", regions: ["us-central1", "us-east1", "europe-west1", "asia-east1"] },
  { id: "azure", name: "Microsoft Azure", icon: "Azure", regions: ["eastus", "westus2", "westeurope", "southeastasia"] },
];

const STEPS = ["Select Model", "Cloud & Region", "Review Configs", "Download"];

type ModelSource = { type: "config"; config: ModelConfig } | { type: "model"; model: LLMModel };

export default function DeployPage() {
  const router = useRouter();
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  // Wizard state
  const [step, setStep] = useState(0);
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selected, setSelected] = useState<ModelSource | null>(null);
  const [cloud, setCloud] = useState("aws");
  const [region, setRegion] = useState("us-east-1");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<DeploymentConfig | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("dockerfile");

  useEffect(() => {
    (async () => {
      if (!isAuthenticated()) {
        setLoading(false);
        return;
      }
      try {
        const [s, c, m, d] = await Promise.all([
          getSubscriptionStatus(),
          listModelConfigs().catch(() => []),
          listModels().catch(() => []),
          listDeployments().catch(() => []),
        ]);
        setSub(s);
        setConfigs(c);
        setModels(m);
        setDeployments(d);
      } catch {
        // Not logged in or error
      }
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return <div className="text-center py-20 text-gray-400">Loading...</div>;
  }

  if (!isAuthenticated()) {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold">Deploy Your LLM</h1>
        <p className="mt-2 text-gray-400">Sign in to access the deploy wizard.</p>
        <Link href="/auth/login" className="btn-primary mt-4 inline-block">
          Sign In
        </Link>
      </div>
    );
  }

  if (sub && sub.tier === "free") {
    return (
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold">Deploy Your LLM</h1>
        <p className="mt-2 text-gray-400 max-w-md mx-auto">
          The deploy wizard generates production-ready IaC configs (Dockerfile, K8s, Terraform, CI/CD)
          and bundles them as a downloadable ZIP. Upgrade to Pro to get started.
        </p>
        <Link href="/pricing" className="btn-primary mt-4 inline-block">
          Upgrade to Pro
        </Link>
      </div>
    );
  }

  const currentRegions = CLOUD_PROVIDERS.find((p) => p.id === cloud)?.regions || [];

  async function handleGenerate() {
    if (!selected) return;
    setGenerating(true);
    setError("");
    try {
      let res: DeploymentConfig;
      if (selected.type === "config") {
        res = await generateDeployFromConfig({
          config_id: selected.config.id,
          cloud_provider: cloud,
          region,
        });
      } else {
        res = await generateDeployConfigs({
          model_id: selected.model.id,
          cloud_provider: cloud,
          region,
        });
      }
      setResult(res);
      setStep(3);
    } catch (e: any) {
      setError(e.message || "Failed to generate configs");
    }
    setGenerating(false);
  }

  function downloadBundle() {
    if (!result) return;
    const token = localStorage.getItem("token");
    // Open in new tab with auth header via fetch + blob
    fetch(getDeployBundleUrl(result.deployment_id), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `deploy-${result.deployment_id.slice(0, 8)}.zip`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => setError("Failed to download bundle"));
  }

  const CONFIG_TABS: { key: string; label: string; field: keyof DeploymentConfig }[] = [
    { key: "dockerfile", label: "Dockerfile", field: "dockerfile" },
    { key: "kubernetes", label: "Kubernetes", field: "kubernetes_yaml" },
    { key: "terraform", label: "Terraform", field: "terraform_config" },
    { key: "cicd", label: "CI/CD", field: "ci_cd_pipeline" },
    { key: "cloudformation", label: "CloudFormation", field: "cloudformation" },
    { key: "quickstart", label: "Quickstart", field: "quickstart" },
    { key: "merge", label: "Merge Config", field: "merge_config" },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold">Deploy Wizard</h1>
        <p className="mt-1 text-gray-400">
          Generate production-ready deployment configs and download as a ZIP bundle.
        </p>
      </div>

      {/* Step indicators */}
      <div className="flex justify-center gap-1 mb-8">
        {STEPS.map((s, i) => (
          <button
            key={s}
            onClick={() => {
              if (i < step) setStep(i);
            }}
            className={`px-4 py-2 text-sm rounded-lg transition ${
              i === step
                ? "bg-brand-600 text-white"
                : i < step
                ? "bg-gray-700 text-gray-300 hover:bg-gray-600 cursor-pointer"
                : "bg-gray-800/50 text-gray-500 cursor-default"
            }`}
          >
            {i + 1}. {s}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Step 0: Select Model */}
      {step === 0 && (
        <div className="space-y-6">
          {configs.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-3">Builder Configurations</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {configs.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelected({ type: "config", config: c })}
                    className={`text-left p-4 rounded-xl border transition ${
                      selected?.type === "config" && selected.config.id === c.id
                        ? "border-brand-500 bg-brand-900/20"
                        : "border-gray-700 bg-gray-800/50 hover:border-gray-500"
                    }`}
                  >
                    <div className="font-medium text-white">{c.name}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs">
                      {c.base_model_hf_id && (
                        <span className="px-2 py-0.5 bg-blue-900/40 text-blue-300 rounded">
                          {c.base_model_hf_id.split("/").pop()}
                        </span>
                      )}
                      {c.quantization_method && c.quantization_method !== "none" && (
                        <span className="px-2 py-0.5 bg-purple-900/40 text-purple-300 rounded">
                          {c.quantization_method.toUpperCase()}
                        </span>
                      )}
                      {c.adapter_hf_id && (
                        <span className="px-2 py-0.5 bg-green-900/40 text-green-300 rounded">
                          LoRA
                        </span>
                      )}
                      {c.is_merge && (
                        <span className="px-2 py-0.5 bg-orange-900/40 text-orange-300 rounded">
                          Merge
                        </span>
                      )}
                      {c.estimated_vram_gb && (
                        <span className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                          {c.estimated_vram_gb.toFixed(1)} GB VRAM
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {models.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-3">Model Library</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {models.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setSelected({ type: "model", model: m })}
                    className={`text-left p-4 rounded-xl border transition ${
                      selected?.type === "model" && selected.model.id === m.id
                        ? "border-brand-500 bg-brand-900/20"
                        : "border-gray-700 bg-gray-800/50 hover:border-gray-500"
                    }`}
                  >
                    <div className="font-medium text-white">{m.name}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs">
                      {m.parameters_billion && (
                        <span className="px-2 py-0.5 bg-blue-900/40 text-blue-300 rounded">
                          {m.parameters_billion}B params
                        </span>
                      )}
                      <span className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                        {m.precision}
                      </span>
                      <span className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                        {m.context_length.toLocaleString()} ctx
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {configs.length === 0 && models.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <p>No models available. Create one in the Builder first.</p>
              <Link href="/builder" className="btn-primary mt-4 inline-block">
                Go to Builder
              </Link>
            </div>
          )}

          <div className="flex justify-end">
            <button
              disabled={!selected}
              onClick={() => setStep(1)}
              className="btn-primary disabled:opacity-50"
            >
              Next: Cloud & Region
            </button>
          </div>
        </div>
      )}

      {/* Step 1: Cloud & Region */}
      {step === 1 && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Choose Cloud Provider</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {CLOUD_PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setCloud(p.id);
                  setRegion(p.regions[0]);
                }}
                className={`p-6 rounded-xl border transition text-center ${
                  cloud === p.id
                    ? "border-brand-500 bg-brand-900/20"
                    : "border-gray-700 bg-gray-800/50 hover:border-gray-500"
                }`}
              >
                <div className="text-2xl font-bold text-white">{p.icon}</div>
                <div className="mt-1 text-sm text-gray-400">{p.name}</div>
              </button>
            ))}
          </div>

          <div>
            <label className="label">Region</label>
            <select
              className="input"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              {currentRegions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div className="card">
            <h3 className="font-semibold text-white mb-2">Selected Model</h3>
            <p className="text-gray-300">
              {selected?.type === "config"
                ? `${selected.config.name} (Builder Config)`
                : selected?.type === "model"
                ? `${selected.model.name} (Model Library)`
                : "None"}
            </p>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(0)} className="btn-secondary">
              Back
            </button>
            <button
              onClick={() => setStep(2)}
              className="btn-primary"
            >
              Next: Review
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Review & Generate */}
      {step === 2 && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Deployment Summary</h2>
          <div className="card">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Model:</span>{" "}
                <span className="text-white">
                  {selected?.type === "config"
                    ? selected.config.name
                    : selected?.model.name}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Cloud:</span>{" "}
                <span className="text-white">{cloud.toUpperCase()}</span>
              </div>
              <div>
                <span className="text-gray-500">Region:</span>{" "}
                <span className="text-white">{region}</span>
              </div>
              {selected?.type === "config" && (
                <>
                  <div>
                    <span className="text-gray-500">Base Model:</span>{" "}
                    <span className="text-white">
                      {selected.config.base_model_hf_id || "N/A"}
                    </span>
                  </div>
                  {selected.config.quantization_method &&
                    selected.config.quantization_method !== "none" && (
                      <div>
                        <span className="text-gray-500">Quantization:</span>{" "}
                        <span className="text-white">
                          {selected.config.quantization_method.toUpperCase()}
                        </span>
                      </div>
                    )}
                  {selected.config.adapter_hf_id && (
                    <div>
                      <span className="text-gray-500">LoRA:</span>{" "}
                      <span className="text-white">
                        {selected.config.adapter_hf_id}
                      </span>
                    </div>
                  )}
                  {selected.config.is_merge && (
                    <div>
                      <span className="text-gray-500">Merge:</span>{" "}
                      <span className="text-white">
                        {selected.config.merge_method?.toUpperCase() || "Yes"}
                      </span>
                    </div>
                  )}
                  {selected.config.estimated_vram_gb && (
                    <div>
                      <span className="text-gray-500">Est. VRAM:</span>{" "}
                      <span className="text-white">
                        {selected.config.estimated_vram_gb.toFixed(1)} GB
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4 text-sm text-yellow-300">
            This will generate Dockerfile, Kubernetes YAML, Terraform configs, CI/CD pipeline,
            and quickstart commands for your deployment. GPU instance will be auto-selected
            based on your model&apos;s VRAM requirements.
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(1)} className="btn-secondary">
              Back
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="btn-primary disabled:opacity-50"
            >
              {generating ? "Generating..." : "Generate Configs"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Download & View */}
      {step === 3 && result && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Generated Configs</h2>
            <button onClick={downloadBundle} className="btn-primary">
              Download ZIP Bundle
            </button>
          </div>

          {/* Config tabs */}
          <div className="flex gap-1 flex-wrap">
            {CONFIG_TABS.filter((t) => result[t.field]).map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-3 py-1.5 text-sm rounded-lg transition ${
                  activeTab === t.key
                    ? "bg-brand-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Config content */}
          <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
            <pre className="p-4 text-sm text-gray-300 overflow-x-auto max-h-[500px] overflow-y-auto">
              <code>
                {result[
                  CONFIG_TABS.find((t) => t.key === activeTab)?.field || "dockerfile"
                ] || "Not applicable for this provider."}
              </code>
            </pre>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => {
                setStep(0);
                setResult(null);
              }}
              className="btn-secondary"
            >
              Deploy Another
            </button>
          </div>
        </div>
      )}

      {/* Previous deployments */}
      {deployments.length > 0 && step === 0 && (
        <div className="mt-12">
          <h2 className="text-lg font-semibold mb-3">Previous Deployments</h2>
          <div className="space-y-2">
            {deployments.slice(0, 5).map((d) => (
              <div
                key={d.id}
                className="card flex items-center justify-between"
              >
                <div>
                  <span className="text-white text-sm font-medium">
                    {d.id.slice(0, 8)}
                  </span>
                  <span className="ml-3 text-xs text-gray-500">
                    {d.cloud_provider.toUpperCase()} &middot; {d.region} &middot;{" "}
                    {d.gpu_type} x{d.gpu_count}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      d.status === "running"
                        ? "bg-green-900/40 text-green-300"
                        : d.status === "pending"
                        ? "bg-yellow-900/40 text-yellow-300"
                        : "bg-gray-700 text-gray-400"
                    }`}
                  >
                    {d.status}
                  </span>
                  <a
                    href={getDeployBundleUrl(d.id)}
                    onClick={(e) => {
                      e.preventDefault();
                      const token = localStorage.getItem("token");
                      fetch(getDeployBundleUrl(d.id), {
                        headers: { Authorization: `Bearer ${token}` },
                      })
                        .then((r) => r.blob())
                        .then((blob) => {
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `deploy-${d.id.slice(0, 8)}.zip`;
                          a.click();
                          URL.revokeObjectURL(url);
                        });
                    }}
                    className="text-xs text-brand-400 hover:text-brand-300"
                  >
                    Download
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
