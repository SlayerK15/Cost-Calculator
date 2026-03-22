"use client";

import { useRef, useEffect, useState } from "react";
import { useAgentChat } from "@/contexts/AgentChatContext";

export function AgentChatWidget() {
  const { messages, isOpen, isLoading, toggleOpen, sendMessage, clearMessages } =
    useAgentChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    sendMessage(text);
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={toggleOpen}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg hover:bg-brand-500 transition"
        title="AI Assistant"
      >
        {isOpen ? (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-50 flex w-96 flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl" style={{ height: "32rem" }}>
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
            <div>
              <h3 className="text-sm font-bold text-white">AI Cost Assistant</h3>
              <p className="text-[11px] text-gray-500">Ask about costs, models, or deployments</p>
            </div>
            <button
              onClick={clearMessages}
              className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300 transition text-xs"
              title="Clear chat"
            >
              Clear
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <p className="text-sm text-gray-500">Hi! I can help you with:</p>
                <div className="mt-3 space-y-1.5">
                  {[
                    "Estimate cost for Llama 3.1 8B on AWS",
                    "Compare AWS vs GCP for a 70B model",
                    "Recommend a model for chatbot under $500/mo",
                    "What GPU do I need for Mistral 7B?",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => {
                        setInput(q);
                        sendMessage(q);
                      }}
                      className="block w-full rounded-lg bg-gray-800 px-3 py-2 text-left text-xs text-gray-400 hover:bg-gray-750 hover:text-gray-300 transition"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-gray-800 text-gray-300"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}

            {isLoading && messages[messages.length - 1]?.content === "" && (
              <div className="flex justify-start">
                <div className="rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-500">
                  <span className="animate-pulse">Thinking...</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-700 px-3 py-3">
            <div className="flex gap-2">
              <input
                className="flex-1 rounded-lg bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="Ask about costs, models..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                disabled={isLoading}
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="rounded-lg bg-brand-600 px-3 py-2 text-sm text-white hover:bg-brand-500 disabled:opacity-50 transition"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
