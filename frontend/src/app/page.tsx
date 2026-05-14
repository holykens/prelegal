"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "./components/ChatPanel";
import DocumentPreview from "./components/DocumentPreview";
import FieldsForm from "./components/FieldsForm";
import { defaultDocumentState } from "./types";
import type { ChatMessage, DocumentState } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [docState, setDocState] = useState<DocumentState>(defaultDocumentState);
  const [sidebarTab, setSidebarTab] = useState<"chat" | "fields">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const docStateRef = useRef(docState);
  useEffect(() => { docStateRef.current = docState; }, [docState]);

  // Core chat caller. Stays loading for the entire turn (including auto-follow-up
  // after document selection) so the UI never flickers between two AI messages.
  async function callChat(
    messagesToSend: ChatMessage[],
    documentName: string | null,
    currentFields: Record<string, string>,
  ) {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: messagesToSend, document_name: documentName, fields: currentFields }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const incomingDoc: string | null = data.document_name ?? null;
      const incomingFields: Record<string, string> = data.fields ?? {};

      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);

      if (incomingDoc && incomingDoc !== documentName) {
        // A document was just selected — fetch the template, then immediately ask
        // the first field question so the user never has to send a blank message.
        const tmplRes = await fetch(
          `${API_BASE}/api/template?document_name=${encodeURIComponent(incomingDoc)}`
        );
        if (tmplRes.ok) {
          const tmpl = await tmplRes.json();
          const newFields = { ...currentFields, ...incomingFields };
          setDocState({
            documentName: incomingDoc,
            templateContent: tmpl.content,
            allFields: tmpl.fields,
            fields: newFields,
          });

          // Auto-trigger: now that we know the template fields, ask the first question
          const withConfirmation: ChatMessage[] = [
            ...messagesToSend,
            { role: "assistant", content: data.reply },
          ];
          const followRes = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              messages: withConfirmation,
              document_name: incomingDoc,
              fields: newFields,
            }),
          });
          if (followRes.ok) {
            const followData = await followRes.json();
            setMessages((prev) => [...prev, { role: "assistant", content: followData.reply }]);
            if (followData.fields && Object.keys(followData.fields).length > 0) {
              setDocState((prev) => ({ ...prev, fields: { ...prev.fields, ...followData.fields } }));
            }
          }
        }
      } else if (Object.keys(incomingFields).length > 0) {
        setDocState((prev) => ({ ...prev, fields: { ...prev.fields, ...incomingFields } }));
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

  // Auth check + auto-initialize the chat with an AI greeting on mount
  useEffect(() => {
    if (!localStorage.getItem("pl_logged_in")) {
      router.replace("/login");
      return;
    }
    callChat([], null, {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend(text: string) {
    const userMsg: ChatMessage = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    await callChat(updated, docStateRef.current.documentName, docStateRef.current.fields);
  }

  const docTitle = docState.documentName ?? "Legal Document Assistant";

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
            <h1 className="text-sm font-semibold text-gray-900 leading-none">{docTitle}</h1>
            <p className="text-xs text-gray-400 mt-0.5">Prelegal</p>
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

          {sidebarTab === "chat" ? (
            <ChatPanel messages={messages} isLoading={isLoading} onSend={handleSend} />
          ) : (
            <div className="flex-1 overflow-y-auto px-5 py-5">
              <FieldsForm
                docState={docState}
                onChange={(fields) => setDocState((prev) => ({ ...prev, fields }))}
              />
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto px-6 py-5">
          <DocumentPreview docState={docState} />
        </main>
      </div>
    </>
  );
}
