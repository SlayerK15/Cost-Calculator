"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import type { PopularModel, LLMModel } from "@/types";
import * as api from "@/lib/api";

const PRECISIONS = [
  { value: "fp32", label: "FP32 (4 bytes/param)" },
  { value: "fp16", label: "FP16 (2 bytes/param)" },
  { value: "bf16", label: "BF16 (2 bytes/param)" },
  { value: "int8", label: "INT8 (1 byte/param)" },
  { value: "int4", label: "INT4 (0.5 bytes/param)" },
];

export default function ModelsPage() {
  const [tab, setTab] = useState<"popular" | "huggingface" | "upload">("popular");
  const [popularModels, setPopularModels] = useState<PopularModel[]>([]);
  const [userModels, setUserModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isAuthed, setIsAuthed] = useState(false);

  // HF form
  const [hfId, setHfId] = useState("");
  const [hfPrecision, setHfPrecision] = useState("fp16");
  const [hfContext, setHfContext] = useState(4096);

  // Upload form
  const [uploadName, setUploadName] = useState("");
  const [uploadSize, setUploadSize] = useState("");
  const [uploadPrecision, setUploadPrecision] = useState("fp16");
  const [uploadContext, setUploadContext] = useState(4096);
  const [uploadParams, setUploadParams] = useState("");

  useEffect(() => {
    setIsAuthed(api.isAuthenticated());
    loadPopularModels();
    if (api.isAuthenticated()) {
      loadUserModels();
    }
  }, []);

  async function loadPopularModels() {
    try {
      const models = await api.getPopularModels();
      setPopularModels(models);
    } catch {
      // API may not be running
    }
  }

  async function loadUserModels() {
    try {
      const models = await api.listModels();
      setUserModels(models);
    } catch {
      // Not authenticated or API down
    }
  }

  async function addHFModel(modelId?: string) {
    if (!api.isAuthenticated()) {
      setError("Please sign in first to add models.");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const id = modelId || hfId;
      await api.addHuggingFaceModel({
        huggingface_id: id,
        precision: hfPrecision,
        context_length: hfContext,
      });
      setSuccess(`Added model: ${id}`);
      setHfId("");
      loadUserModels();
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  async function addUploadModel() {
    if (!api.isAuthenticated()) {
      setError("Please sign in first to add models.");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const sizeBytes = parseFloat(uploadSize) * 1024 * 1024 * 1024; // GB to bytes
      await api.addCustomModel({
        name: uploadName,
        file_size_bytes: sizeBytes,
        precision: uploadPrecision,
        context_length: uploadContext,
        parameters_billion: uploadParams ? parseFloat(uploadParams) : undefined,
      });
      setSuccess(`Added custom model: ${uploadName}`);
      setUploadName("");
      setUploadSize("");
      loadUserModels();
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">Model Library</h1>
      <p className="mt-2 text-gray-400">
        Browse popular open-source LLMs and their specs. Click any model to estimate deployment costs instantly.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-800 bg-red-900/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-4 rounded-lg border border-green-800 bg-green-900/30 p-3 text-sm text-green-300">
          {success}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 flex gap-2 border-b border-gray-800 pb-2">
        <button
          onClick={() => setTab("popular")}
          className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
            tab === "popular"
              ? "bg-gray-800 text-white"
              : "text-gray-500 hover:text-gray-300"
          }`}
        >
          Popular Models
        </button>
        {isAuthed && (
          <>
            <button
              onClick={() => setTab("huggingface")}
              className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
                tab === "huggingface"
                  ? "bg-gray-800 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Hugging Face
            </button>
            <button
              onClick={() => setTab("upload")}
              className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
                tab === "upload"
                  ? "bg-gray-800 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Custom Upload
            </button>
          </>
        )}
      </div>

      {/* Popular models */}
      {tab === "popular" && (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {popularModels.length === 0 && (
            <p className="text-gray-500 col-span-full">
              Loading popular models...
            </p>
          )}
          {popularModels.map((m) => (
            <div key={m.id} className="card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-brand-400">{m.organization}</span>
                  <span className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
                    {m.parameters_billion}B params
                  </span>
                </div>
                <h3 className="mt-1 font-semibold text-white">{m.name}</h3>
                <p className="mt-1 text-xs text-gray-500">
                  {m.architecture} · {m.context_length.toLocaleString()} ctx
                </p>
              </div>
              <Link
                href={`/estimate?model=${encodeURIComponent(m.name)}&params=${m.parameters_billion}&ctx=${m.context_length}`}
                className="btn-primary mt-4 text-sm text-center"
              >
                Estimate Cost
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* Hugging Face search (auth only) */}
      {tab === "huggingface" && isAuthed && (
        <div className="mt-6 max-w-lg space-y-4">
          <div>
            <label className="label">Hugging Face Model ID</label>
            <input
              className="input"
              placeholder="e.g. meta-llama/Meta-Llama-3-8B"
              value={hfId}
              onChange={(e) => setHfId(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Precision</label>
              <select
                className="input"
                value={hfPrecision}
                onChange={(e) => setHfPrecision(e.target.value)}
              >
                {PRECISIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Context Length</label>
              <input
                className="input"
                type="number"
                value={hfContext}
                onChange={(e) => setHfContext(Number(e.target.value))}
              />
            </div>
          </div>
          <button
            onClick={() => addHFModel()}
            disabled={loading || !hfId}
            className="btn-primary"
          >
            {loading ? "Adding..." : "Add Model"}
          </button>
        </div>
      )}

      {/* Custom upload (auth only) */}
      {tab === "upload" && isAuthed && (
        <div className="mt-6 max-w-lg space-y-4">
          <div>
            <label className="label">Model Name</label>
            <input
              className="input"
              placeholder="My Custom Model"
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Model File Size (GB)</label>
            <input
              className="input"
              type="number"
              step="0.1"
              placeholder="e.g. 14.5"
              value={uploadSize}
              onChange={(e) => setUploadSize(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Precision</label>
              <select
                className="input"
                value={uploadPrecision}
                onChange={(e) => setUploadPrecision(e.target.value)}
              >
                {PRECISIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Context Length</label>
              <input
                className="input"
                type="number"
                value={uploadContext}
                onChange={(e) => setUploadContext(Number(e.target.value))}
              />
            </div>
          </div>
          <div>
            <label className="label">Parameters (Billion) — leave blank to auto-infer</label>
            <input
              className="input"
              type="number"
              step="0.1"
              placeholder="Auto-inferred from file size"
              value={uploadParams}
              onChange={(e) => setUploadParams(e.target.value)}
            />
          </div>
          <button
            onClick={addUploadModel}
            disabled={loading || !uploadName || !uploadSize}
            className="btn-primary"
          >
            {loading ? "Registering..." : "Register Model"}
          </button>
        </div>
      )}

      {/* User's models (auth only) */}
      {isAuthed && userModels.length > 0 && (
        <div className="mt-12">
          <h2 className="text-xl font-bold">Your Models</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-800 text-gray-500">
                <tr>
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Source</th>
                  <th className="pb-2 pr-4">Parameters</th>
                  <th className="pb-2 pr-4">Precision</th>
                  <th className="pb-2 pr-4">Context</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {userModels.map((m) => (
                  <tr key={m.id}>
                    <td className="py-3 pr-4 font-medium text-white">{m.name}</td>
                    <td className="py-3 pr-4 text-gray-400">{m.source}</td>
                    <td className="py-3 pr-4 text-gray-400">
                      {m.parameters_billion}B
                      {m.is_parameters_estimated && (
                        <span className="ml-1 text-xs text-yellow-500">(est.)</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-gray-400">{m.precision}</td>
                    <td className="py-3 pr-4 text-gray-400">{m.context_length.toLocaleString()}</td>
                    <td className="py-3">
                      <Link
                        href={`/estimate?model=${encodeURIComponent(m.name)}&params=${m.parameters_billion}&ctx=${m.context_length}`}
                        className="text-brand-400 hover:text-brand-300 text-sm"
                      >
                        Estimate Cost
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
