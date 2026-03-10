"use client";

import type { NodeData } from "./PipelineNode";

interface NodeEditorProps {
  node: NodeData;
  onUpdate: (id: string, config: Record<string, any>) => void;
  onToggle: (id: string, enabled: boolean) => void;
  onClose: () => void;
}

export function NodeEditor({ node, onUpdate, onToggle, onClose }: NodeEditorProps) {
  const c = node.config;
  const set = (key: string, value: any) => onUpdate(node.id, { ...c, [key]: value });

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 p-5 overflow-y-auto h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{node.label}</h3>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">&times;</button>
      </div>

      {/* Optional nodes get enable/disable toggle */}
      {(node.type === "adapter" || node.type === "merge" || node.type === "quantization") && (
        <label className="flex items-center gap-2 mb-4 text-sm">
          <input
            type="checkbox"
            checked={node.enabled}
            onChange={(e) => onToggle(node.id, e.target.checked)}
            className="rounded"
          />
          <span className="text-gray-300">Enable {node.label}</span>
        </label>
      )}

      {node.type === "base_model" && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">HuggingFace Model ID</label>
            <input
              type="text"
              value={c.base_model_hf_id || ""}
              onChange={(e) => set("base_model_hf_id", e.target.value)}
              placeholder="meta-llama/Llama-3.1-8B"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
          <div className="grid grid-cols-3 gap-1">
            {["meta-llama/Llama-3.1-8B", "mistralai/Mistral-7B-v0.3", "google/gemma-2-9b"].map((m) => (
              <button
                key={m}
                onClick={() => set("base_model_hf_id", m)}
                className={`text-xs px-2 py-1.5 rounded border ${
                  c.base_model_hf_id === m ? "border-blue-500 bg-blue-900/40 text-blue-300" : "border-gray-700 bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {m.split("/")[1]?.substring(0, 12) || m}
              </button>
            ))}
          </div>
        </div>
      )}

      {node.type === "adapter" && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">LoRA Adapter ID</label>
            <input
              type="text"
              value={c.adapter_hf_id || ""}
              onChange={(e) => set("adapter_hf_id", e.target.value)}
              placeholder="username/my-lora-adapter"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
          <p className="text-xs text-gray-500">
            Enter a HuggingFace LoRA adapter ID. The adapter will be loaded at inference time via vLLM.
          </p>
        </div>
      )}

      {node.type === "merge" && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Merge Method</label>
            <select
              value={c.merge_method || "slerp"}
              onChange={(e) => set("merge_method", e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="slerp">SLERP</option>
              <option value="linear">Linear</option>
              <option value="ties">TIES</option>
              <option value="dare">DARE</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Models to Merge</label>
            {(c.merge_models || []).map((m: any, i: number) => (
              <div key={i} className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={m.model_hf_id || ""}
                  onChange={(e) => {
                    const models = [...(c.merge_models || [])];
                    models[i] = { ...models[i], model_hf_id: e.target.value };
                    set("merge_models", models);
                  }}
                  placeholder="model/id"
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
                />
                <input
                  type="number"
                  value={m.weight || 0.5}
                  onChange={(e) => {
                    const models = [...(c.merge_models || [])];
                    models[i] = { ...models[i], weight: parseFloat(e.target.value) };
                    set("merge_models", models);
                  }}
                  step={0.1}
                  min={0}
                  max={1}
                  className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white"
                />
                <button
                  onClick={() => {
                    const models = (c.merge_models || []).filter((_: any, j: number) => j !== i);
                    set("merge_models", models);
                  }}
                  className="text-red-400 text-xs hover:text-red-300"
                >
                  X
                </button>
              </div>
            ))}
            <button
              onClick={() => set("merge_models", [...(c.merge_models || []), { model_hf_id: "", weight: 0.5 }])}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              + Add Model
            </button>
          </div>
        </div>
      )}

      {node.type === "quantization" && (
        <div className="space-y-2">
          <label className="block text-xs text-gray-400 mb-1">Method</label>
          {["none", "gptq", "awq", "bnb_int8", "bnb_int4"].map((method) => (
            <label key={method} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="quant"
                checked={c.quantization_method === method}
                onChange={() => set("quantization_method", method)}
                className="text-blue-500"
              />
              <span className={c.quantization_method === method ? "text-white" : "text-gray-400"}>
                {method === "none" ? "None (FP16)" : method.toUpperCase()}
              </span>
            </label>
          ))}
        </div>
      )}

      {node.type === "inference" && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">System Prompt</label>
            <textarea
              value={c.system_prompt || ""}
              onChange={(e) => set("system_prompt", e.target.value)}
              rows={3}
              placeholder="You are a helpful assistant."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Temperature: {c.default_temperature ?? 0.7}
            </label>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={c.default_temperature ?? 0.7}
              onChange={(e) => set("default_temperature", parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Max Tokens</label>
            <input
              type="number"
              value={c.default_max_tokens || 512}
              onChange={(e) => set("default_max_tokens", parseInt(e.target.value))}
              min={64}
              max={32768}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
        </div>
      )}
    </div>
  );
}
