"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "./components/ChatPanel";
import DocumentPreview from "./components/DocumentPreview";
import FieldsForm from "./components/FieldsForm";
import { defaultDocumentState, getSession, clearSession, authHeaders } from "./types";
import type { ChatMessage, DocumentState, Session } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [session, setSessionState] = useState<Session | null>(null);
  const [docState, setDocState] = useState<DocumentState>(defaultDocumentState);
  const [sidebarTab, setSidebarTab] = useState<"chat" | "fields">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [documentId, setDocumentId] = useState<number | null>(null);
  const docStateRef = useRef(docState);
  const messagesRef = useRef(messages);
  const documentIdRef = useRef(documentId);
  const sessionRef = useRef(session);

  useEffect(() => { docStateRef.current = docState; }, [docState]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { documentIdRef.current = documentId; }, [documentId]);
  useEffect(() => { sessionRef.current = session; }, [session]);

  async function autoSave(
    currentSession: Session,
    docName: string,
    fields: Record<string, string>,
    msgs: ChatMessage[],
    currentDocId: number | null,
  ): Promise<number | null> {
    const body = JSON.stringify({ document_name: docName, fields, messages: msgs });
    const headers = authHeaders(currentSession);
    try {
      if (currentDocId) {
        await fetch(`${API_BASE}/api/documents/${currentDocId}`, {
          method: "PUT", headers, body,
        });
        return currentDocId;
      } else {
        const res = await fetch(`${API_BASE}/api/documents`, { method: "POST", headers, body });
        if (res.ok) {
          const data = await res.json();
          return data.id as number;
        }
      }
    } catch {
      // auto-save failure is non-fatal
    }
    return currentDocId;
  }

  async function callChat(
    messagesToSend: ChatMessage[],
    documentName: string | null,
    currentFields: Record<string, string>,
  ) {
    const currentSession = sessionRef.current;
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: authHeaders(currentSession),
        body: JSON.stringify({ messages: messagesToSend, document_name: documentName, fields: currentFields }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const incomingDoc: string | null = data.document_name ?? null;
      const incomingFields: Record<string, string> = data.fields ?? {};

      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);

      if (incomingDoc && incomingDoc !== documentName) {
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

          const withConfirmation: ChatMessage[] = [
            ...messagesToSend,
            { role: "assistant", content: data.reply },
          ];
          const followRes = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: authHeaders(currentSession),
            body: JSON.stringify({
              messages: withConfirmation,
              document_name: incomingDoc,
              fields: newFields,
            }),
          });
          if (followRes.ok) {
            const followData = await followRes.json();
            const updatedMessages: ChatMessage[] = [
              ...withConfirmation,
              { role: "assistant", content: followData.reply },
            ];
            setMessages(updatedMessages);
            const updatedFields = followData.fields && Object.keys(followData.fields).length > 0
              ? { ...newFields, ...followData.fields }
              : newFields;
            setDocState((prev) => ({ ...prev, fields: updatedFields }));

            if (currentSession) {
              const newId = await autoSave(
                currentSession, incomingDoc, updatedFields, updatedMessages,
                documentIdRef.current,
              );
              if (newId !== documentIdRef.current) setDocumentId(newId);
            }
          }
        }
      } else if (Object.keys(incomingFields).length > 0) {
        setDocState((prev) => {
          const updatedFields = { ...prev.fields, ...incomingFields };
          if (currentSession && prev.documentName) {
            const updatedMessages: ChatMessage[] = [
              ...messagesToSend,
              { role: "assistant", content: data.reply },
            ];
            autoSave(currentSession, prev.documentName, updatedFields, updatedMessages,
              documentIdRef.current).then((newId) => {
              if (newId !== documentIdRef.current) setDocumentId(newId);
            });
          }
          return { ...prev, fields: updatedFields };
        });
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

  async function restoreDocument(s: Session, docId: number) {
    setIsLoading(true);
    let restored = false;
    try {
      const docRes = await fetch(`${API_BASE}/api/documents/${docId}`, {
        headers: authHeaders(s),
      });
      if (docRes.ok) {
        const doc = await docRes.json();
        const tmplRes = await fetch(
          `${API_BASE}/api/template?document_name=${encodeURIComponent(doc.document_name)}`
        );
        if (tmplRes.ok) {
          const tmpl = await tmplRes.json();
          setDocState({
            documentName: doc.document_name,
            templateContent: tmpl.content,
            allFields: tmpl.fields,
            fields: doc.fields,
          });
          setMessages(doc.messages ?? []);
          setDocumentId(docId);
          restored = true;
        }
      }
    } catch {
      // fall through to fresh start
    } finally {
      setIsLoading(false);
    }
    if (!restored) {
      callChat([], null, {});
    }
  }

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    setSessionState(s);
    const restoreId = sessionStorage.getItem("pl_restore_doc_id");
    if (restoreId) {
      sessionStorage.removeItem("pl_restore_doc_id");
      restoreDocument(s, parseInt(restoreId, 10));
    } else {
      callChat([], null, {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend(text: string) {
    const userMsg: ChatMessage = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    await callChat(updated, docStateRef.current.documentName, docStateRef.current.fields);
  }

  function handleSignOut() {
    clearSession();
    router.push("/login");
  }

  function handleNewDocument() {
    setDocState(defaultDocumentState);
    setMessages([]);
    setDocumentId(null);
    setSidebarTab("chat");
    callChat([], null, {});
  }

  const docTitle = docState.documentName ?? "Legal Document Assistant";

  return (
    <>
      <header className="bg-white border-b border-gray-100 px-5 py-0 flex items-center justify-between print:hidden" style={{ height: 53 }}>
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: "#209dd7" }}>
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-none">{docTitle}</h1>
            <p className="text-xs mt-0.5" style={{ color: "#888888" }}>Prelegal</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {session && (
            <span className="text-xs hidden sm:block" style={{ color: "#888888" }}>
              {session.email}
            </span>
          )}
          <button
            onClick={handleNewDocument}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: "#753991" }}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Document
          </button>
          <a
            href="/history"
            className="flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            History
          </a>
          <button
            onClick={handleSignOut}
            className="text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="app-layout flex" style={{ height: "calc(100vh - 53px)" }}>
        <aside className="w-80 shrink-0 flex flex-col border-r border-gray-100 bg-white print:hidden">
          <div className="flex shrink-0 border-b border-gray-100">
            <button
              onClick={() => setSidebarTab("chat")}
              className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                sidebarTab === "chat"
                  ? "border-b-2 text-[#209dd7]"
                  : "text-gray-400 hover:text-gray-600"
              }`}
              style={sidebarTab === "chat" ? { borderBottomColor: "#209dd7" } : {}}
            >
              AI Chat
            </button>
            <button
              onClick={() => setSidebarTab("fields")}
              className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                sidebarTab === "fields"
                  ? "border-b-2 text-[#209dd7]"
                  : "text-gray-400 hover:text-gray-600"
              }`}
              style={sidebarTab === "fields" ? { borderBottomColor: "#209dd7" } : {}}
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
