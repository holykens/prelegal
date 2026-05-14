"use client";

import { useState } from "react";
import NDAForm from "./components/NDAForm";
import NDAPreview from "./components/NDAPreview";
import { defaultFormData } from "./types";
import type { NDAFormData } from "./types";

export default function Home() {
  const [formData, setFormData] = useState<NDAFormData>(defaultFormData);

  return (
    <>
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-600 rounded flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-none">Mutual NDA Creator</h1>
            <p className="text-xs text-gray-400 mt-0.5">Prelegal · CommonPaper v1.0</p>
          </div>
        </div>
        <span className="text-xs bg-blue-50 text-blue-700 font-medium px-2 py-1 rounded-full">Prototype</span>
      </header>

      <div className="app-layout flex" style={{ height: "calc(100vh - 53px)" }}>
        <aside className="w-80 shrink-0 overflow-y-auto border-r border-gray-200 bg-white px-5 py-5 print:hidden">
          <NDAForm data={formData} onChange={setFormData} />
        </aside>

        <main className="flex-1 overflow-y-auto px-6 py-5">
          <NDAPreview data={formData} />
        </main>
      </div>
    </>
  );
}
