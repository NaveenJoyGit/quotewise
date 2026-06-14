"use client";

import { useState } from "react";
import { ParsedRulesResponse, parseRateCard, savePricingConfig } from "@/lib/onboarding-api";

interface RateRow {
  conditions: Record<string, string>;
  base_rate: number;
}

interface Props {
  contractorId: string;
  apiKey: string;
  onComplete: (workType: string) => void;
}

export default function StepTwo({ contractorId, apiKey, onComplete }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [workTypeHint, setWorkTypeHint] = useState("");
  const [parsed, setParsed] = useState<ParsedRulesResponse | null>(null);
  const [rateRows, setRateRows] = useState<RateRow[]>([]);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleParse() {
    if (!file) return;
    setParseError(null);
    setParsed(null);
    setParsing(true);
    try {
      const result = await parseRateCard(file, workTypeHint);
      setParsed(result);
      const table = (result.rules as { rate_table?: RateRow[] }).rate_table ?? [];
      setRateRows(table.map((r) => ({ ...r, base_rate: Number(r.base_rate) })));
    } catch (err: unknown) {
      setParseError(err instanceof Error ? err.message : "Parsing failed.");
    } finally {
      setParsing(false);
    }
  }

  function handleRateChange(idx: number, value: string) {
    setRateRows((rows) =>
      rows.map((r, i) => (i === idx ? { ...r, base_rate: parseFloat(value) || 0 } : r))
    );
  }

  function toWorkTypeSlug(name: string): string {
    return name.trim().toLowerCase().replace(/[\s-]+/g, "_");
  }

  async function handleSave() {
    if (!parsed) return;
    setSaveError(null);
    setSaving(true);
    try {
      const slug = toWorkTypeSlug(workTypeHint);
      const updatedRules = { ...parsed.rules, rate_table: rateRows };
      await savePricingConfig(contractorId, slug, updatedRules, apiKey);
      onComplete(slug);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* File upload */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Work type
        </label>
        <input
          type="text"
          placeholder="e.g. electrical, plumbing, painting"
          value={workTypeHint}
          onChange={(e) => setWorkTypeHint(e.target.value)}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Rate card file <span className="text-red-500">*</span>
        </label>
        <input
          type="file"
          accept=".pdf,.txt,.csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
        />
        <p className="mt-1 text-xs text-gray-500">Supported: PDF, TXT, CSV</p>
      </div>

      <button
        onClick={handleParse}
        disabled={!file || parsing}
        className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {parsing ? "Parsing with AI..." : "Parse with AI"}
      </button>

      {parseError && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {parseError}
        </div>
      )}

      {/* Notes and validation errors */}
      {parsed && parsed.notes.length > 0 && (
        <div className="rounded-md bg-blue-50 border border-blue-200 px-4 py-3">
          <p className="text-sm font-medium text-blue-800 mb-1">AI notes</p>
          <ul className="list-disc list-inside space-y-0.5">
            {parsed.notes.map((n, i) => (
              <li key={i} className="text-sm text-blue-700">{n}</li>
            ))}
          </ul>
        </div>
      )}

      {parsed && parsed.validation_errors.length > 0 && (
        <div className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-3">
          <p className="text-sm font-medium text-yellow-800 mb-1">
            Schema issues — please review rates manually before saving
          </p>
          <ul className="list-disc list-inside space-y-0.5">
            {parsed.validation_errors.map((e, i) => (
              <li key={i} className="text-sm text-yellow-700">{e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Editable rate table */}
      {rateRows.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            Rate table — review and edit if needed
          </h3>
          <div className="overflow-x-auto rounded-md border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-600">Conditions</th>
                  <th className="px-4 py-2 text-right font-medium text-gray-600">Base Rate (₹)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rateRows.map((row, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2 text-gray-700">
                      {Object.entries(row.conditions)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(", ") || "(all)"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={row.base_rate}
                        onChange={(e) => handleRateChange(idx, e.target.value)}
                        className="w-24 text-right border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {saveError && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {saveError}
        </div>
      )}

      {parsed && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-green-600 text-white rounded-md py-2 text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
        >
          {saving ? "Saving..." : "Save Pricing & Continue"}
        </button>
      )}
    </div>
  );
}
