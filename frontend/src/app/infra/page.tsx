"use client";

import { useState } from "react";
import * as api from "@/lib/api";

const CLOUD_PROVIDERS = [
  { value: "aws", label: "AWS" },
  { value: "gcp", label: "GCP" },
  { value: "azure", label: "Azure" },
];

const IAC_LANGUAGES = [
  { value: "terraform", label: "Terraform (HCL)" },
  { value: "cloudformation", label: "CloudFormation (AWS)" },
  { value: "pulumi", label: "Pulumi (Python)" },
  { value: "kubernetes", label: "Kubernetes Only" },
];

const PRECISIONS = [
  { value: "fp16", label: "FP16" },
  { value: "bf16", label: "BF16" },
  { value: "int8", label: "INT8" },
  { value: "int4", label: "INT4" },
];

const REGIONS: Record<string, { value: string; label: string }[]> = {
  aws: [
    { value: "us-east-1", label: "US East (N. Virginia)" },
    { value: "us-west-2", label: "US West (Oregon)" },
    { value: "eu-west-1", label: "EU (Ireland)" },
    { value: "ap-southeast-1", label: "Asia (Singapore)" },
  ],
  gcp: [
    { value: "us-central1", label: "US Central (Iowa)" },
    { value: "us-east1", label: "US East (S. Carolina)" },
    { value: "europe-west1", label: "Europe West (Belgium)" },
    { value: "asia-east1", label: "Asia East (Taiwan)" },
  ],
  azure: [
    { value: "eastus", label: "East US" },
    { value: "westus2", label: "West US 2" },
    { value: "westeurope", label: "West Europe" },
    { value: "southeastasia", label: "Southeast Asia" },
  ],
};

interface InfraFile {
  filename: string;
  content: string;
  language: string;
}

interface InfraResult {
  deployment_id: string;
  cloud_provider: string;
  iac_language: string;
  region: string;
  instance_type: string;
  gpu_type: string;
  gpu_count: number;
  estimated_monthly_cost: number;
  files: InfraFile[];
  quickstart: string;
  summary: string;
}

interface SearchResult {
  source: string;
  title: string;
  snippet: string;
  relevance: number;
}

export default function InfraPage() {
  // Form state
  const [modelName, setModelName] = useState("Llama-3-8B");
  const [paramsBillion, setParamsBillion] = useState(8);
  const [precision, setPrecision] = useState("fp16");
  const [contextLength, setContextLength] = useState(4096);
  const [cloudProvider, setCloudProvider] = useState("aws");
  const [iacLanguage, setIacLanguage] = useState("terraform");
  const [region, setRegion] = useState("us-east-1");
  const [gpuCount, setGpuCount] = useState(1);
  const [replicas, setReplicas] = useState(1);
  const [enableMonitoring, setEnableMonitoring] = useState(true);
  const [enableAutoscaling, setEnableAutoscaling] = useState(true);
  const [customRequirements, setCustomRequirements] = useState("");

  // Results state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<InfraResult | null>(null);
  const [activeFile, setActiveFile] = useState(0);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

  async function handleGenerate() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.generateInfra({
        model_name: modelName,
        parameters_billion: paramsBillion,
        precision,
        context_length: contextLength,
        cloud_provider: cloudProvider,
        iac_language: iacLanguage,
        region,
        gpu_count: gpuCount,
        replicas,
        enable_monitoring: enableMonitoring,
        enable_autoscaling: enableAutoscaling,
        custom_requirements: customRequirements,
      });
      setResult(res);
      setActiveFile(0);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await api.searchInfra({ query: searchQuery, cloud_provider: cloudProvider });
      setSearchResults(res.results);
    } catch {
      setSearchResults([]);
    }
    setSearching(false);
  }

  function downloadFile(file: InfraFile) {
    const blob = new Blob([file.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.filename.split("/").pop() || file.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadAll() {
    if (!result) return;
    result.files.forEach(downloadFile);
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">Infrastructure Agent</h1>
      <p className="mt-2 text-gray-400">
        Generate deployment files for any LLM on any cloud — Terraform, CloudFormation, Pulumi, or
        plain Kubernetes. Powered by real-time cost engine.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-800 bg-red-900/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Left: Config Form ── */}
        <div className="lg:col-span-1 space-y-4">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Model</h2>
            <div>
              <label className="label">Model Name</label>
              <input className="input" value={modelName} onChange={(e) => setModelName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Parameters (B)</label>
                <input className="input" type="number" step="0.1" value={paramsBillion} onChange={(e) => setParamsBillion(Number(e.target.value))} />
              </div>
              <div>
                <label className="label">Precision</label>
                <select className="input" value={precision} onChange={(e) => setPrecision(e.target.value)}>
                  {PRECISIONS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="label">Context Length</label>
              <input className="input" type="number" value={contextLength} onChange={(e) => setContextLength(Number(e.target.value))} />
            </div>
          </div>

          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Infrastructure</h2>
            <div>
              <label className="label">Cloud Provider</label>
              <div className="flex gap-2">
                {CLOUD_PROVIDERS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => {
                      setCloudProvider(p.value);
                      setRegion(REGIONS[p.value][0].value);
                    }}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                      cloudProvider === p.value
                        ? "bg-brand-600 text-white"
                        : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label">IaC Language</label>
              <select className="input" value={iacLanguage} onChange={(e) => setIacLanguage(e.target.value)}>
                {IAC_LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
              {iacLanguage === "cloudformation" && cloudProvider !== "aws" && (
                <p className="mt-1 text-xs text-yellow-400">
                  CloudFormation is AWS-only. Terraform will be used as fallback.
                </p>
              )}
            </div>
            <div>
              <label className="label">Region</label>
              <select className="input" value={region} onChange={(e) => setRegion(e.target.value)}>
                {(REGIONS[cloudProvider] || []).map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">GPU Count</label>
                <input className="input" type="number" min={1} max={16} value={gpuCount} onChange={(e) => setGpuCount(Number(e.target.value))} />
              </div>
              <div>
                <label className="label">Replicas</label>
                <input className="input" type="number" min={1} max={20} value={replicas} onChange={(e) => setReplicas(Number(e.target.value))} />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input type="checkbox" checked={enableAutoscaling} onChange={(e) => setEnableAutoscaling(e.target.checked)} className="rounded border-gray-600" />
                Enable Autoscaling
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input type="checkbox" checked={enableMonitoring} onChange={(e) => setEnableMonitoring(e.target.checked)} className="rounded border-gray-600" />
                Enable Monitoring (Prometheus + Grafana)
              </label>
            </div>
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Custom Requirements</h2>
            <textarea
              className="input min-h-[80px] resize-y"
              placeholder="e.g. 'Use spot instances', 'Add Redis cache', 'Enable VPN'..."
              value={customRequirements}
              onChange={(e) => setCustomRequirements(e.target.value)}
            />
          </div>

          <button onClick={handleGenerate} disabled={loading || !modelName} className="btn-primary w-full">
            {loading ? "Generating..." : "Generate Deployment Files"}
          </button>

          {/* ── Search Panel ── */}
          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Search Infrastructure</h2>
            <p className="text-xs text-gray-500">
              Search GPU instances, pricing, and best practices.
            </p>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="e.g. 'A100 pricing', 'H100 aws'"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <button onClick={handleSearch} disabled={searching} className="btn-primary px-4">
                {searching ? "..." : "Search"}
              </button>
            </div>
            {searchResults.length > 0 && (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {searchResults.map((r, i) => (
                  <div key={i} className="rounded-lg border border-gray-700 bg-gray-800/50 p-2">
                    <p className="text-sm font-medium text-gray-200">{r.title}</p>
                    <p className="text-xs text-gray-400 mt-1">{r.snippet}</p>
                    <span className="text-[10px] text-gray-600 mt-1 inline-block">{r.source}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Results ── */}
        <div className="lg:col-span-2">
          {result ? (
            <div className="space-y-4">
              {/* Summary Card */}
              <div className="card">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">{result.summary}</h2>
                    <div className="mt-2 flex flex-wrap gap-3 text-sm text-gray-400">
                      <span>Provider: <strong className="text-white">{result.cloud_provider.toUpperCase()}</strong></span>
                      <span>IaC: <strong className="text-white">{result.iac_language}</strong></span>
                      <span>Instance: <strong className="text-white">{result.instance_type}</strong></span>
                      <span>GPU: <strong className="text-white">{result.gpu_type} x{result.gpu_count}</strong></span>
                      <span>Region: <strong className="text-white">{result.region}</strong></span>
                    </div>
                  </div>
                  {result.estimated_monthly_cost > 0 && (
                    <div className="text-right">
                      <p className="text-2xl font-bold text-brand-400">
                        ${result.estimated_monthly_cost.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </p>
                      <p className="text-xs text-gray-500">est. /month</p>
                    </div>
                  )}
                </div>
              </div>

              {/* File Tabs */}
              <div className="card p-0 overflow-hidden">
                <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2">
                  <div className="flex gap-1 overflow-x-auto">
                    {result.files.map((f, i) => (
                      <button
                        key={f.filename}
                        onClick={() => setActiveFile(i)}
                        className={`whitespace-nowrap rounded-md px-3 py-1 text-xs font-medium transition ${
                          activeFile === i
                            ? "bg-brand-600/20 text-brand-400"
                            : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                        }`}
                      >
                        {f.filename}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2 ml-2 shrink-0">
                    <button
                      onClick={() => downloadFile(result.files[activeFile])}
                      className="rounded-md bg-gray-800 px-3 py-1 text-xs text-gray-300 hover:bg-gray-700 transition"
                    >
                      Download
                    </button>
                    <button
                      onClick={downloadAll}
                      className="rounded-md bg-brand-600/80 px-3 py-1 text-xs text-white hover:bg-brand-600 transition"
                    >
                      Download All
                    </button>
                  </div>
                </div>
                <div className="relative">
                  <button
                    className="absolute right-3 top-3 rounded bg-gray-700 px-2 py-1 text-[10px] text-gray-300 hover:bg-gray-600 transition z-10"
                    onClick={() => {
                      navigator.clipboard.writeText(result.files[activeFile].content);
                    }}
                  >
                    Copy
                  </button>
                  <pre className="overflow-x-auto p-4 text-sm leading-relaxed text-gray-300 bg-gray-950 max-h-[600px] overflow-y-auto">
                    <code>{result.files[activeFile]?.content}</code>
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="card flex flex-col items-center justify-center min-h-[400px] text-center">
              <div className="text-6xl text-gray-700 mb-4">&#9881;</div>
              <h3 className="text-xl font-semibold text-gray-400">Configure & Generate</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-md">
                Select your model, cloud provider, and IaC language, then click
                &ldquo;Generate Deployment Files&rdquo; to get production-ready infrastructure code.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-3 text-left text-xs text-gray-500">
                <div className="rounded-lg border border-gray-800 p-3">
                  <strong className="text-gray-300">Terraform</strong>
                  <p>AWS EKS, GCP GKE, Azure AKS — full VPC, node pools, container registry</p>
                </div>
                <div className="rounded-lg border border-gray-800 p-3">
                  <strong className="text-gray-300">CloudFormation</strong>
                  <p>AWS-native stack with EKS, ECR, S3, IAM — one-click deploy URL</p>
                </div>
                <div className="rounded-lg border border-gray-800 p-3">
                  <strong className="text-gray-300">Pulumi</strong>
                  <p>Python IaC for AWS/GCP/Azure — type-safe, programmable infra</p>
                </div>
                <div className="rounded-lg border border-gray-800 p-3">
                  <strong className="text-gray-300">Kubernetes</strong>
                  <p>Deployment, Service, HPA — with GPU scheduling and health checks</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
