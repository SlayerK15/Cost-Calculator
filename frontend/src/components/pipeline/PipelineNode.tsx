"use client";

import { useState, useRef, useEffect } from "react";

export interface NodeData {
  id: string;
  type: "base_model" | "adapter" | "merge" | "quantization" | "inference";
  label: string;
  x: number;
  y: number;
  config: Record<string, any>;
  enabled: boolean;
}

const NODE_ICONS: Record<string, string> = {
  base_model: "\u{1F9E0}",
  adapter: "\u{1F9E9}",
  merge: "\u{1F500}",
  quantization: "\u{26A1}",
  inference: "\u{1F680}",
};

const NODE_COLORS: Record<string, string> = {
  base_model: "border-blue-500 bg-blue-950/60",
  adapter: "border-purple-500 bg-purple-950/60",
  merge: "border-orange-500 bg-orange-950/60",
  quantization: "border-yellow-500 bg-yellow-950/60",
  inference: "border-green-500 bg-green-950/60",
};

const NODE_SUMMARIES: Record<string, (c: Record<string, any>) => string> = {
  base_model: (c) => c.base_model_hf_id || "Not selected",
  adapter: (c) => c.adapter_hf_id || "None",
  merge: (c) => c.merge_method ? `${c.merge_method.toUpperCase()} (${(c.merge_models || []).length} models)` : "Not configured",
  quantization: (c) => c.quantization_method === "none" ? "None (FP16)" : (c.quantization_method || "none").toUpperCase(),
  inference: (c) => `T=${c.default_temperature || 0.7} / max=${c.default_max_tokens || 512}`,
};

interface PipelineNodeProps {
  node: NodeData;
  selected: boolean;
  onSelect: (id: string) => void;
  onMove: (id: string, x: number, y: number) => void;
  canvasOffset: { x: number; y: number };
}

export function PipelineNode({ node, selected, onSelect, onMove, canvasOffset }: PipelineNodeProps) {
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 });

  useEffect(() => {
    if (!dragging) return;
    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStart.current.x;
      const dy = e.clientY - dragStart.current.y;
      onMove(node.id, dragStart.current.nodeX + dx, dragStart.current.nodeY + dy);
    };
    const handleMouseUp = () => setDragging(false);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, node.id, onMove]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    dragStart.current = { x: e.clientX, y: e.clientY, nodeX: node.x, nodeY: node.y };
    setDragging(true);
    onSelect(node.id);
  };

  const summary = NODE_SUMMARIES[node.type]?.(node.config) || "";
  const isDisabled = !node.enabled && node.type !== "base_model" && node.type !== "inference";

  return (
    <div
      className={`absolute select-none cursor-grab active:cursor-grabbing transition-shadow
        w-52 rounded-xl border-2 p-3
        ${NODE_COLORS[node.type] || "border-gray-600 bg-gray-900"}
        ${selected ? "ring-2 ring-white/30 shadow-lg shadow-indigo-500/20" : ""}
        ${isDisabled ? "opacity-40" : ""}
      `}
      style={{ left: node.x, top: node.y }}
      onMouseDown={handleMouseDown}
      onClick={(e) => { e.stopPropagation(); onSelect(node.id); }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{NODE_ICONS[node.type]}</span>
        <span className="text-sm font-semibold text-white truncate">{node.label}</span>
      </div>
      <div className="text-xs text-gray-400 truncate">{summary}</div>
      {/* Output port */}
      <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-gray-600 border-2 border-gray-400" />
      {/* Input port */}
      {node.type !== "base_model" && (
        <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-gray-600 border-2 border-gray-400" />
      )}
    </div>
  );
}

// Utility to get port positions for connection lines
export function getNodeOutputPort(node: NodeData) {
  return { x: node.x + 208 + 6, y: node.y + 30 }; // right side center
}

export function getNodeInputPort(node: NodeData) {
  return { x: node.x - 6, y: node.y + 30 }; // left side center
}
