"use client";

import type { DocumentState } from "../types";

interface Props {
  docState: DocumentState;
  onChange: (fields: Record<string, string>) => void;
}

const inputClass =
  "w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent";

export default function FieldsForm({ docState, onChange }: Props) {
  if (!docState.documentName || docState.allFields.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-center px-4">
        <p className="text-sm" style={{ color: "#888888" }}>
          Select a document in the AI Chat tab to see its fields here.
        </p>
      </div>
    );
  }

  function update(key: string, value: string) {
    onChange({ ...docState.fields, [key]: value });
  }

  return (
    <div className="text-sm space-y-4">
      <p className="text-xs font-semibold uppercase tracking-widest pb-1 border-b border-gray-100" style={{ color: "#888888" }}>
        {docState.documentName}
      </p>

      {docState.allFields.map((field) => (
        <div key={field}>
          <label className="block text-sm font-medium text-gray-700 mb-1">{field}</label>
          <input
            className={inputClass}
            value={docState.fields[field] ?? ""}
            onChange={(e) => update(field, e.target.value)}
            placeholder={`Enter ${field.toLowerCase()}`}
          />
        </div>
      ))}
    </div>
  );
}
