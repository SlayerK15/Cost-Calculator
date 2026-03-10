"use client";

import { useState, useCallback } from "react";
import { PipelineNode, getNodeOutputPort, getNodeInputPort } from "./PipelineNode";
import { ConnectionLine } from "./ConnectionLine";
import { NodeEditor } from "./NodeEditor";
import type { NodeData } from "./PipelineNode";

// Default layout for the 5 nodes
const DEFAULT_NODES: NodeData[] = [
  { id: "base_model", type: "base_model", label: "Base Model", x: 40, y: 120, config: { base_model_hf_id: "" }, enabled: true },
  { id: "adapter", type: "adapter", label: "LoRA Adapter", x: 300, y: 40, config: { adapter_hf_id: "" }, enabled: false },
  { id: "merge", type: "merge", label: "Model Merge", x: 300, y: 200, config: { merge_method: "slerp", merge_models: [] }, enabled: false },
  { id: "quantization", type: "quantization", label: "Quantization", x: 560, y: 120, config: { quantization_method: "none" }, enabled: true },
  { id: "inference", type: "inference", label: "Inference", x: 820, y: 120, config: { system_prompt: "", default_temperature: 0.7, default_max_tokens: 512 }, enabled: true },
];

// Connection definitions: from -> to
const CONNECTIONS = [
  { from: "base_model", to: "adapter" },
  { from: "base_model", to: "merge" },
  { from: "adapter", to: "quantization" },
  { from: "merge", to: "quantization" },
  { from: "base_model", to: "quantization" }, // direct path when no adapter/merge
  { from: "quantization", to: "inference" },
];

interface PipelineCanvasProps {
  initialNodes?: NodeData[];
  onSave: (nodes: NodeData[]) => void;
  configName: string;
}

export function PipelineCanvas({ initialNodes, onSave, configName }: PipelineCanvasProps) {
  const [nodes, setNodes] = useState<NodeData[]>(initialNodes || DEFAULT_NODES);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  const selectedNode = nodes.find((n) => n.id === selectedId) || null;

  const handleMove = useCallback((id: string, x: number, y: number) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, x, y } : n)));
    setDirty(true);
  }, []);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleUpdate = useCallback((id: string, config: Record<string, any>) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, config } : n)));
    setDirty(true);
  }, []);

  const handleToggle = useCallback((id: string, enabled: boolean) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, enabled } : n)));
    setDirty(true);
  }, []);

  const handleSave = () => {
    onSave(nodes);
    setDirty(false);
  };

  // Build active connections based on enabled nodes
  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const activeConnections = CONNECTIONS.filter((c) => {
    const from = nodeMap[c.from];
    const to = nodeMap[c.to];
    if (!from?.enabled || !to?.enabled) return false;

    // Skip direct base->quant if adapter or merge is enabled
    if (c.from === "base_model" && c.to === "quantization") {
      const adapterEnabled = nodeMap["adapter"]?.enabled;
      const mergeEnabled = nodeMap["merge"]?.enabled;
      if (adapterEnabled || mergeEnabled) return false;
    }
    // Skip adapter path if merge is enabled (they're alternatives)
    if ((c.from === "adapter" || c.to === "adapter") && nodeMap["merge"]?.enabled) return false;
    if ((c.from === "merge" || c.to === "merge") && nodeMap["adapter"]?.enabled) return false;

    return true;
  });

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-gray-950">
      {/* Canvas */}
      <div
        className="flex-1 relative overflow-hidden"
        onClick={() => setSelectedId(null)}
      >
        {/* Grid background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#1e293b" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Connection lines */}
          {activeConnections.map((c, i) => {
            const from = nodeMap[c.from];
            const to = nodeMap[c.to];
            if (!from || !to) return null;
            return (
              <ConnectionLine
                key={i}
                from={getNodeOutputPort(from)}
                to={getNodeInputPort(to)}
                color={
                  c.from === "base_model" ? "#3b82f6" :
                  c.from === "adapter" ? "#a855f7" :
                  c.from === "merge" ? "#f97316" :
                  c.from === "quantization" ? "#eab308" : "#6366f1"
                }
              />
            );
          })}
        </svg>

        {/* Header bar */}
        <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 py-3 bg-gray-900/80 backdrop-blur-sm border-b border-gray-800 z-10">
          <div>
            <h2 className="text-lg font-semibold text-white">Pipeline: {configName}</h2>
            <p className="text-xs text-gray-500">Drag nodes to rearrange. Click to edit. Toggle optional stages.</p>
          </div>
          <div className="flex gap-2">
            {dirty && <span className="text-xs text-yellow-400 self-center">Unsaved changes</span>}
            <button
              onClick={handleSave}
              disabled={!dirty}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium"
            >
              Save Pipeline
            </button>
          </div>
        </div>

        {/* Pipeline nodes */}
        <div className="pt-16">
          {nodes.map((node) => (
            <PipelineNode
              key={node.id}
              node={node}
              selected={selectedId === node.id}
              onSelect={handleSelect}
              onMove={handleMove}
              canvasOffset={{ x: 0, y: 0 }}
            />
          ))}
        </div>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 flex gap-3 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> Base Model</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500" /> Adapter</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> Merge</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> Quantization</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Inference</span>
        </div>
      </div>

      {/* Side editor panel */}
      {selectedNode && (
        <NodeEditor
          node={selectedNode}
          onUpdate={handleUpdate}
          onToggle={handleToggle}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
