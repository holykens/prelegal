"use client";

import type { NDAFormData, Party } from "../types";

interface Props {
  data: NDAFormData;
  onChange: (data: NDAFormData) => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 pb-1 border-b border-gray-100">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {hint && <span className="ml-1 text-xs text-gray-400 font-normal">({hint})</span>}
      </label>
      {children}
    </div>
  );
}

const inputClass =
  "w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

const textareaClass = `${inputClass} resize-none`;

function PartyFields({
  label,
  party,
  onChange,
}: {
  label: string;
  party: Party;
  onChange: (p: Party) => void;
}) {
  const update = (field: keyof Party) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    onChange({ ...party, [field]: e.target.value });

  return (
    <Section title={label}>
      <Field label="Print Name">
        <input className={inputClass} placeholder="Full name" value={party.name} onChange={update("name")} />
      </Field>
      <Field label="Title">
        <input className={inputClass} placeholder="e.g. CEO" value={party.title} onChange={update("title")} />
      </Field>
      <Field label="Company">
        <input className={inputClass} placeholder="Company name" value={party.company} onChange={update("company")} />
      </Field>
      <Field label="Notice Address" hint="email or postal">
        <textarea
          className={textareaClass}
          rows={2}
          placeholder="email@example.com or 123 Main St, City, State ZIP"
          value={party.noticeAddress}
          onChange={update("noticeAddress")}
        />
      </Field>
    </Section>
  );
}

export default function NDAForm({ data, onChange }: Props) {
  const set = <K extends keyof NDAFormData>(key: K) =>
    (val: NDAFormData[K]) => onChange({ ...data, [key]: val });

  return (
    <div className="text-sm">
      <Section title="Cover Page">
        <Field label="Purpose" hint="how confidential information may be used">
          <textarea
            className={textareaClass}
            rows={3}
            value={data.purpose}
            onChange={(e) => set("purpose")(e.target.value)}
          />
        </Field>

        <Field label="Effective Date">
          <input
            type="date"
            className={inputClass}
            value={data.effectiveDate}
            onChange={(e) => set("effectiveDate")(e.target.value)}
          />
        </Field>

        <Field label="MNDA Term" hint="length of this agreement">
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mndaTermType"
                checked={data.mndaTermType === "expires"}
                onChange={() => set("mndaTermType")("expires")}
                className="text-blue-600"
              />
              <span>Expires after</span>
              <input
                type="number"
                min={1}
                max={10}
                className="w-16 rounded border border-gray-200 px-2 py-1 text-sm"
                value={data.mndaTermYears}
                onChange={(e) => set("mndaTermYears")(Number(e.target.value))}
                disabled={data.mndaTermType !== "expires"}
              />
              <span>year(s) from Effective Date</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mndaTermType"
                checked={data.mndaTermType === "continues"}
                onChange={() => set("mndaTermType")("continues")}
                className="text-blue-600"
              />
              <span>Continues until terminated</span>
            </label>
          </div>
        </Field>

        <Field label="Term of Confidentiality" hint="how long information is protected">
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="confidentialityTermType"
                checked={data.confidentialityTermType === "years"}
                onChange={() => set("confidentialityTermType")("years")}
                className="text-blue-600"
              />
              <input
                type="number"
                min={1}
                max={10}
                className="w-16 rounded border border-gray-200 px-2 py-1 text-sm"
                value={data.confidentialityTermYears}
                onChange={(e) => set("confidentialityTermYears")(Number(e.target.value))}
                disabled={data.confidentialityTermType !== "years"}
              />
              <span>year(s) from Effective Date</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="confidentialityTermType"
                checked={data.confidentialityTermType === "perpetuity"}
                onChange={() => set("confidentialityTermType")("perpetuity")}
                className="text-blue-600"
              />
              <span>In perpetuity</span>
            </label>
          </div>
        </Field>

        <Field label="Governing Law" hint="state">
          <input
            className={inputClass}
            placeholder="e.g. Delaware"
            value={data.governingLaw}
            onChange={(e) => set("governingLaw")(e.target.value)}
          />
        </Field>

        <Field label="Jurisdiction" hint="city/county and state">
          <input
            className={inputClass}
            placeholder='e.g. courts located in New Castle, DE'
            value={data.jurisdiction}
            onChange={(e) => set("jurisdiction")(e.target.value)}
          />
        </Field>

        <Field label="MNDA Modifications">
          <textarea
            className={textareaClass}
            rows={2}
            placeholder="List any modifications, or leave blank for none"
            value={data.mndaModifications}
            onChange={(e) => set("mndaModifications")(e.target.value)}
          />
        </Field>
      </Section>

      <PartyFields
        label="Party 1"
        party={data.party1}
        onChange={set("party1")}
      />
      <PartyFields
        label="Party 2"
        party={data.party2}
        onChange={set("party2")}
      />
    </div>
  );
}
