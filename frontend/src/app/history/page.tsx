"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, clearSession, authHeaders } from "../types";
import type { Session, SavedDocument } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function formatDate(iso: string): string {
  try {
    return new Date(iso + "Z").toLocaleString(undefined, {
      month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fieldCount(doc: SavedDocument): number {
  return Object.values(doc.fields).filter((v) => v && v !== "None").length;
}

export default function HistoryPage() {
  const router = useRouter();
  const [session, setSessionState] = useState<Session | null>(null);
  const [documents, setDocuments] = useState<SavedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const s = getSession();
    if (!s) { router.replace("/login"); return; }
    setSessionState(s);
    fetchDocuments(s);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchDocuments(s: Session) {
    try {
      const res = await fetch(`${API_BASE}/api/documents`, {
        headers: authHeaders(s),
      });
      if (res.status === 401) { clearSession(); router.replace("/login"); return; }
      if (!res.ok) { setError("Failed to load documents."); return; }
      setDocuments(await res.json());
    } catch {
      setError("Unable to connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  async function openDocument(doc: SavedDocument) {
    // Store the session ID to restore and navigate to main page
    sessionStorage.setItem("pl_restore_doc_id", String(doc.id));
    router.push("/");
  }

  function handleSignOut() {
    clearSession();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-5 flex items-center justify-between print:hidden" style={{ height: 53 }}>
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: "#209dd7" }}>
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-none">Document History</h1>
            <p className="text-xs mt-0.5" style={{ color: "#888888" }}>Prelegal</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {session && (
            <span className="text-xs hidden sm:block" style={{ color: "#888888" }}>{session.email}</span>
          )}
          <a href="/" className="text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors">
            New Document
          </a>
          <button
            onClick={handleSignOut}
            className="text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold" style={{ color: "#032147" }}>Your Documents</h2>
          <a
            href="/"
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: "#753991" }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Document
          </a>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <svg className="w-5 h-5 animate-spin mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading documents…
          </div>
        )}

        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && documents.length === 0 && (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "#f0f9ff" }}>
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                style={{ color: "#209dd7" }}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-base font-semibold mb-1" style={{ color: "#032147" }}>No documents yet</h3>
            <p className="text-sm" style={{ color: "#888888" }}>
              Start a chat to draft your first legal document.
            </p>
          </div>
        )}

        {!loading && documents.length > 0 && (
          <div className="flex flex-col gap-3">
            {documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => openDocument(doc)}
                className="w-full text-left bg-white rounded-xl border border-gray-200 px-5 py-4 hover:border-[#209dd7] hover:shadow-sm transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ backgroundColor: "#f0f9ff" }}>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                        style={{ color: "#209dd7" }}>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900 group-hover:text-[#032147] transition-colors">
                        {doc.document_name}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "#888888" }}>
                        {fieldCount(doc)} field{fieldCount(doc) !== 1 ? "s" : ""} filled
                        {doc.messages.length > 0 && ` · ${doc.messages.length} message${doc.messages.length !== 1 ? "s" : ""}`}
                      </p>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs" style={{ color: "#888888" }}>
                      {formatDate(doc.updated_at)}
                    </p>
                    <svg className="w-4 h-4 ml-auto mt-1 text-gray-300 group-hover:text-[#209dd7] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
