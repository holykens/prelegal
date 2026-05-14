"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import type { DocumentState } from "../types";

interface Props {
  docState: DocumentState;
}

const FIELD_SPAN_CLASSES = ["coverpage_link", "keyterms_link", "orderform_link"];

function variantsOf(key: string): string[] {
  const v = [key, key + "s", key + "'s", key + "'s"];
  if (key.endsWith("s") && key.length > 2) v.push(key.slice(0, -1));
  return v;
}

function fillTemplate(content: string, fields: Record<string, string>): string {
  let result = content;
  for (const [key, value] of Object.entries(fields)) {
    // Skip intentionally-empty fields — don't highlight "None" in the document
    if (!value.trim() || value === "None") continue;
    for (const cls of FIELD_SPAN_CLASSES) {
      for (const variant of variantsOf(key)) {
        result = result
          .split(`<span class="${cls}">${variant}</span>`)
          .join(`<span class="filled-value">${value}</span>`);
      }
    }
  }
  return result;
}

function downloadMarkdown(docState: DocumentState) {
  if (!docState.templateContent) return;
  const content = fillTemplate(docState.templateContent, docState.fields)
    .replace(/<span class="filled-value">([^<]+)<\/span>/g, "$1")
    .replace(/<span[^>]*>([^<]*)<\/span>/g, "$1");
  const name = (docState.documentName ?? "document").replace(/\s+/g, "-");
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function DocumentPreview({ docState }: Props) {
  if (!docState.documentName || !docState.templateContent) {
    return (
      <div className="flex flex-col h-full items-center justify-center text-center px-8">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ backgroundColor: "#f0f9ff" }}>
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: "#209dd7" }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h2 className="text-base font-semibold mb-2" style={{ color: "#032147" }}>No document selected</h2>
        <p className="text-sm" style={{ color: "#888888" }}>
          Start a conversation in the AI Chat tab to select a document and fill it in.
        </p>
      </div>
    );
  }

  const rendered = fillTemplate(docState.templateContent, docState.fields);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4 print:hidden">
        <p className="text-sm text-gray-500">
          Values you enter are{" "}
          <span className="inline-block bg-amber-100 text-amber-800 text-xs font-medium px-1.5 py-0.5 rounded">
            highlighted
          </span>{" "}
          in the document.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => downloadMarkdown(docState)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download .md
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white rounded-md hover:opacity-90 transition-opacity"
            style={{ backgroundColor: "#209dd7" }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print / Save PDF
          </button>
        </div>
      </div>

      <div
        id="document-content"
        className="flex-1 bg-white rounded-lg border border-gray-200 p-8 overflow-y-auto prose prose-sm max-w-none
          prose-headings:font-serif prose-headings:text-gray-900
          prose-h1:text-2xl prose-h1:text-center prose-h1:mb-6
          prose-h2:text-base prose-h2:font-semibold prose-h2:text-gray-700 prose-h2:border-b prose-h2:pb-1
          prose-h3:text-sm prose-h3:font-semibold prose-h3:text-gray-600
          prose-p:text-gray-800 prose-p:leading-relaxed
          prose-li:text-gray-800 prose-li:leading-relaxed
          prose-strong:text-gray-900
          prose-table:w-full prose-td:border prose-td:border-gray-300 prose-td:px-3 prose-td:py-2 prose-td:text-sm
          prose-th:border prose-th:border-gray-300 prose-th:px-3 prose-th:py-2 prose-th:text-sm prose-th:bg-gray-50
          prose-a:text-blue-600"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{rendered}</ReactMarkdown>
      </div>
    </div>
  );
}
