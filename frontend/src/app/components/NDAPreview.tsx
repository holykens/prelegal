"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import type { NDAFormData } from "../types";
import {
  generateCoverPageMarkdown,
  generateFilledStandardTerms,
  generateDownloadMarkdown,
} from "../utils/ndaGenerator";

interface Props {
  data: NDAFormData;
}

function downloadMarkdown(data: NDAFormData) {
  const content = generateDownloadMarkdown(data);
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "Mutual-NDA.md";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function NDAPreview({ data }: Props) {
  const coverPage = generateCoverPageMarkdown(data);
  const standardTerms = generateFilledStandardTerms(data);

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
            onClick={() => downloadMarkdown(data)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download .md
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print / Save PDF
          </button>
        </div>
      </div>

      <div
        id="nda-document"
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
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{coverPage}</ReactMarkdown>
        <hr className="my-8 border-gray-300" />
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{standardTerms}</ReactMarkdown>
      </div>
    </div>
  );
}
