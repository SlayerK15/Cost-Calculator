"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { ModelConfig, PlaygroundResponse } from "@/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  tokens?: number;
  latency?: number;
  cost?: number;
}

export default function PlaygroundPage() {
  const router = useRouter();
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    setAuthChecked(true);
    loadConfigs();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadConfigs() {
    try {
      const list = await api.listModelConfigs();
      setConfigs(list);
      if (list.length > 0) setSelectedConfig(list[0].id);
    } catch {}
    setConfigLoading(false);
  }

  async function handleSend() {
    if (!input.trim() || !selectedConfig || loading) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const result: PlaygroundResponse = await api.simulatePlayground({
        config_id: selectedConfig,
        prompt: input.trim(),
      });

      const assistantMessage: Message = {
        role: "assistant",
        content: result.response_text,
        tokens: result.tokens_used,
        latency: result.estimated_latency_ms,
        cost: result.estimated_cost_per_request,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const selectedConfigData = configs.find((c) => c.id === selectedConfig);

  if (!authChecked) return null;

  return (
    <div className="flex flex-col h-[calc(100vh-65px)]">
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-4">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold">Playground</h1>
            <p className="text-sm text-gray-400 mt-1">
              Test your model configs with simulated inference
            </p>
          </div>
          <div className="flex items-center gap-3">
            {configLoading ? (
              <div className="text-sm text-gray-500">Loading configs...</div>
            ) : configs.length === 0 ? (
              <div className="text-sm text-gray-500">
                No configs.{" "}
                <a href="/builder" className="text-blue-400 hover:text-blue-300">
                  Create one
                </a>
              </div>
            ) : (
              <select
                value={selectedConfig}
                onChange={(e) => setSelectedConfig(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
              >
                {configs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
            {selectedConfig && (
              <button
                onClick={() => router.push(`/deploy?config=${selectedConfig}`)}
                className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium"
              >
                Deploy This Model
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Model Info Bar */}
      {selectedConfigData && (
        <div className="border-b border-gray-800/50 px-6 py-2 bg-gray-900/50">
          <div className="flex items-center gap-4 max-w-5xl mx-auto text-xs text-gray-500">
            <span>
              Base:{" "}
              <span className="text-gray-300">
                {selectedConfigData.base_model_hf_id || "Custom"}
              </span>
            </span>
            <span>
              Params:{" "}
              <span className="text-gray-300">
                {selectedConfigData.effective_parameters_billion?.toFixed(1) || "?"}B
              </span>
            </span>
            <span>
              Quant:{" "}
              <span className="text-gray-300">
                {selectedConfigData.quantization_method || "none"}
              </span>
            </span>
            <span>
              VRAM:{" "}
              <span className="text-gray-300">
                {selectedConfigData.estimated_vram_gb?.toFixed(1) || "?"}GB
              </span>
            </span>
            <span>
              Context:{" "}
              <span className="text-gray-300">
                {selectedConfigData.effective_context_length || selectedConfigData.default_max_tokens}
              </span>
            </span>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <div className="text-4xl mb-4 opacity-20">&#9672;</div>
              <h3 className="text-lg font-medium text-gray-400">
                Start a conversation
              </h3>
              <p className="text-sm text-gray-500 mt-2">
                Select a model config and type a prompt to simulate inference
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-blue-600/20 border border-blue-800/50"
                    : "bg-gray-800 border border-gray-700"
                }`}
              >
                <div className="text-xs text-gray-500 mb-1 font-medium uppercase">
                  {msg.role === "user" ? "You" : selectedConfigData?.name || "Model"}
                </div>
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </div>
                {msg.role === "assistant" && msg.tokens && (
                  <div className="mt-2 flex gap-3 text-xs text-gray-500 border-t border-gray-700 pt-2">
                    <span>{msg.tokens} tokens</span>
                    <span>{msg.latency?.toFixed(0)}ms latency</span>
                    <span>${msg.cost?.toFixed(6)}/request</span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0.1s]" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0.2s]" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder={
              selectedConfig
                ? "Type a prompt to test your model..."
                : "Select a model config first"
            }
            disabled={!selectedConfig || loading}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm placeholder:text-gray-500 disabled:opacity-50 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || !selectedConfig || loading}
            className="px-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-sm font-medium"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
