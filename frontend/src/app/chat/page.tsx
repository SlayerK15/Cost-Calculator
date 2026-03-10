"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import type { ChatMessage, Deployment } from "@/types";
import * as api from "@/lib/api";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const preselectedDeployment = searchParams.get("deployment");

  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [maxTokens, setMaxTokens] = useState(512);
  const [temperature, setTemperature] = useState(0.7);
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDeployments();
  }, []);

  useEffect(() => {
    if (preselectedDeployment) {
      setSelectedDeployment(preselectedDeployment);
    }
  }, [preselectedDeployment]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadDeployments() {
    try {
      const deps = await api.listDeployments();
      setDeployments(deps);
      if (preselectedDeployment) {
        setSelectedDeployment(preselectedDeployment);
      } else if (deps.length > 0) {
        setSelectedDeployment(deps[0].id);
      }
    } catch {}
  }

  async function sendMessage() {
    if (!input.trim() || !selectedDeployment || loading) return;

    const userMessage: ChatMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await api.sendMessage({
        deployment_id: selectedDeployment,
        message: input,
        max_tokens: maxTokens,
        temperature,
      });
      setMessages((prev) => [...prev, response.message]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${e.message}`,
        },
      ]);
    }
    setLoading(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Chat</h1>
          <p className="mt-1 text-gray-400 text-sm">
            Chat with your deployed LLM.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input max-w-xs"
            value={selectedDeployment}
            onChange={(e) => {
              setSelectedDeployment(e.target.value);
              setMessages([]);
            }}
          >
            <option value="">-- Select deployment --</option>
            {deployments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.id.slice(0, 8)} ({d.cloud_provider.toUpperCase()} · {d.status})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="btn-secondary text-sm"
          >
            Settings
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="mt-3 card flex gap-6">
          <div>
            <label className="label">Max Tokens</label>
            <input
              className="input w-32"
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Temperature</label>
            <input
              className="input w-32"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="mt-4 flex-1 overflow-y-auto rounded-xl border border-gray-800 bg-gray-900/50 p-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-600">
            {selectedDeployment
              ? "Send a message to start chatting."
              : "Select a deployment to start."}
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`mb-4 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[70%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-brand-600 text-white"
                  : "bg-gray-800 text-gray-200"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="mb-4 flex justify-start">
            <div className="rounded-2xl bg-gray-800 px-4 py-3 text-sm text-gray-400">
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="mt-3 flex gap-2">
        <textarea
          className="input resize-none"
          rows={1}
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!selectedDeployment}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !selectedDeployment || !input.trim()}
          className="btn-primary whitespace-nowrap"
        >
          Send
        </button>
      </div>
    </div>
  );
}
