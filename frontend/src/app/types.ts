export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface DocumentState {
  documentName: string | null;
  templateContent: string | null;
  allFields: string[];
  fields: Record<string, string>;
}

export const defaultDocumentState: DocumentState = {
  documentName: null,
  templateContent: null,
  allFields: [],
  fields: {},
};

export interface Session {
  token: string;
  email: string;
}

export interface SavedDocument {
  id: number;
  document_name: string;
  fields: Record<string, string>;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("pl_session");
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(session: Session) {
  localStorage.setItem("pl_session", JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem("pl_session");
}

export function authHeaders(session: Session | null): Record<string, string> {
  const base: Record<string, string> = { "Content-Type": "application/json" };
  if (session) base["Authorization"] = `Bearer ${session.token}`;
  return base;
}
