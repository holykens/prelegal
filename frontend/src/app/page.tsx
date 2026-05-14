"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import NDAForm from "./components/NDAForm";
import NDAPreview from "./components/NDAPreview";
import ChatPanel from "./components/ChatPanel";
import { defaultFormData } from "./types";
import type { NDAFormData, ChatMessage, Party } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function applyFields(base: NDAFormData, fields: Record<string, unknown>): NDAFormData {
  const result = { ...base };
  for (const [key, val] of Object.entries(fields)) {
    if (val === null || val === undefined) continue;
    if (key === "party1" || key === "party2") {
      result[key] = { ...base[key], ...(val as Partial<Party>) };
    } else {
      (result as Record<string, unknown>)[key] = val;
    }
  }
  return result;
}

export default function Home() {
  const router = useRouter();
  const [formData, setFormData] = useState<NDAFormData>(defaultFormData);
  const [sidebarTab, setSidebarTab] = useState<"chat" | "fields">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const formDataRef = useRef(formData);
  useEffect(() => { formDataRef.current = formData; }, [formData]);

  useEffect(() => {
    if (!localStorage.getItem("pl_logged_in")) {
      router.replace("/login");
    }
  }, [router]);

  async function handleSend(text: string) {
    const userMsg: ChatMessage = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updated, current_fields: formDataRef.current }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
      if (data.fields && Object.keys(data.fields).length > 0) {
        setFormData((prev) => applyFields(prev, data.fields));
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I encountered an error. Please try again." },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded flex items-center justify-center" style={{ backgroundColor: "#209dd7" }}>
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-none">Mutual NDA Creator</h1>
            <p className="text-xs text-gray-400 mt-0.5">Prelegal · CommonPaper v1.0</p>
          </div>
        </div>
        <button
          onClick={() => { localStorage.removeItem("pl_logged_in"); router.push("/login"); }}
          className="text-xs text-gray-500 hover:text-gray-800 transition-colors"
        >
          Sign out
        </button>
      </header>

      <div className="app-layout flex" style={{ height: "calc(100vh - 53px)" }}>
        <aside className="w-80 shrink-0 flex flex-col border-r border-gray-200 bg-white print:hidden">
          {/* Tab bar */}
          <div className="flex shrink-0 border-b border-gray-100">
            <button
              onClick={() => setSidebarTab("chat")}
              className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                sidebarTab === "chat"
                  ? "border-b-2 border-[#209dd7] text-[#209dd7]"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              AI Chat
            </button>
            <button
              onClick={() => setSidebarTab("fields")}
              className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                sidebarTab === "fields"
                  ? "border-b-2 border-[#209dd7] text-[#209dd7]"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              Edit Fields
            </button>
          </div>

          {/* Tab content */}
          {sidebarTab === "chat" ? (
            <ChatPanel messages={messages} isLoading={isLoading} onSend={handleSend} />
          ) : (
            <div className="flex-1 overflow-y-auto px-5 py-5">
              <NDAForm data={formData} onChange={setFormData} />
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto px-6 py-5">
          <NDAPreview data={formData} />
        </main>
      </div>
    </>
  );
}
