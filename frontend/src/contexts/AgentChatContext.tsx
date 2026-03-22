"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { AgentMessage } from "@/types";
import * as api from "@/lib/api";

interface AgentChatState {
  messages: AgentMessage[];
  isOpen: boolean;
  isLoading: boolean;
  context: Record<string, any>;
  toggleOpen: () => void;
  sendMessage: (text: string) => Promise<void>;
  setContext: (ctx: Record<string, any>) => void;
  clearMessages: () => void;
}

const AgentChatCtx = createContext<AgentChatState | null>(null);

export function useAgentChat() {
  const ctx = useContext(AgentChatCtx);
  if (!ctx) throw new Error("useAgentChat must be used within AgentChatProvider");
  return ctx;
}

export function AgentChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [context, setContext] = useState<Record<string, any>>({});

  const toggleOpen = useCallback(() => setIsOpen((o) => !o), []);

  const clearMessages = useCallback(() => setMessages([]), []);

  const sendMessage = useCallback(
    async (text: string) => {
      const userMsg: AgentMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        // Try streaming first, fall back to sync
        let responseText = "";
        const assistantPlaceholder: AgentMessage = { role: "assistant", content: "" };
        setMessages((prev) => [...prev, assistantPlaceholder]);

        try {
          responseText = await api.sendAgentMessage(
            text,
            context,
            history,
            (chunk) => {
              responseText += "";
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                if (last.role === "assistant") {
                  copy[copy.length - 1] = {
                    ...last,
                    content: last.content + chunk,
                  };
                }
                return copy;
              });
            }
          );
        } catch {
          // Fallback to sync endpoint
          responseText = await api.sendAgentMessageSync(text, context, history);
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: "assistant", content: responseText };
            return copy;
          });
        }
      } catch (e: any) {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            role: "assistant",
            content: `Sorry, I encountered an error: ${e.message}`,
          },
        ]);
      }
      setIsLoading(false);
    },
    [messages, context]
  );

  return (
    <AgentChatCtx.Provider
      value={{
        messages,
        isOpen,
        isLoading,
        context,
        toggleOpen,
        sendMessage,
        setContext,
        clearMessages,
      }}
    >
      {children}
    </AgentChatCtx.Provider>
  );
}
