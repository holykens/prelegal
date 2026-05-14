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
