"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ContractorResponse } from "@/lib/onboarding-api";

const BOT_NUMBER = process.env.NEXT_PUBLIC_WA_BOT_NUMBER ?? "0000000000";

interface Props {
  contractor: ContractorResponse;
  workType: string;
}

export default function StepThree({ contractor, workType }: Props) {
  const waLink = `https://wa.me/${BOT_NUMBER}?text=quote-${contractor.whatsapp_link_slug}`;
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  useEffect(() => {
    // Save the API key as a cookie so the dashboard works immediately after onboarding.
    const maxAge = 30 * 24 * 60 * 60;
    document.cookie = `contractor_key=${contractor.api_key}; path=/; max-age=${maxAge}; SameSite=Strict`;
  }, [contractor.api_key]);

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(waLink);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      // Clipboard not available in HTTP context.
    }
  }

  async function handleCopyKey() {
    try {
      await navigator.clipboard.writeText(contractor.api_key);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    } catch {
      // Clipboard not available in HTTP context.
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-md bg-green-50 border border-green-200 px-4 py-4">
        <p className="text-green-800 font-semibold text-sm">
          You&apos;re all set, {contractor.business_name}!
        </p>
        <p className="text-green-700 text-sm mt-1">
          Your account is live. Share the link below with buyers to start receiving AI-handled
          enquiries.
        </p>
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-md border border-gray-200 divide-y divide-gray-100">
        <div className="px-4 py-3 flex justify-between text-sm">
          <span className="text-gray-600">Business</span>
          <span className="font-medium text-gray-900">{contractor.business_name}</span>
        </div>
        <div className="px-4 py-3 flex justify-between text-sm">
          <span className="text-gray-600">Phone</span>
          <span className="font-medium text-gray-900">{contractor.phone}</span>
        </div>
        {contractor.city && (
          <div className="px-4 py-3 flex justify-between text-sm">
            <span className="text-gray-600">City</span>
            <span className="font-medium text-gray-900">{contractor.city}</span>
          </div>
        )}
        <div className="px-4 py-3 flex justify-between text-sm">
          <span className="text-gray-600">Work type configured</span>
          <span className="font-medium text-gray-900 capitalize">
            {workType.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* API key — shown once */}
      <div className="rounded-md bg-amber-50 border border-amber-200 px-4 py-4">
        <p className="text-amber-800 font-semibold text-sm mb-1">
          Save your API key — it won&apos;t be shown again
        </p>
        <p className="text-amber-700 text-xs mb-3">
          You need this key to sign in to your dashboard. It has been saved to this browser,
          but copy it somewhere safe in case you switch devices.
        </p>
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-white border border-amber-300 rounded-md px-3 py-2 text-xs font-mono text-gray-700 break-all select-all">
            {contractor.api_key}
          </div>
          <button
            onClick={handleCopyKey}
            className="shrink-0 bg-amber-100 hover:bg-amber-200 border border-amber-300 rounded-md px-3 py-2 text-xs transition-colors"
          >
            {copiedKey ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>

      {/* WhatsApp link */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">WhatsApp buyer link</p>
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-white border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-700 break-all">
            {waLink}
          </div>
          <button
            onClick={handleCopyLink}
            className="shrink-0 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-3 py-2 text-sm transition-colors"
          >
            {copiedLink ? "Copied!" : "Copy"}
          </button>
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Share this link with buyers — they tap it and the AI quote conversation starts automatically.
        </p>
      </div>

      {/* Navigation */}
      <div className="flex gap-3 pt-2">
        <Link
          href="/quotes"
          className="flex-1 text-center bg-blue-600 text-white rounded-md py-2 text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          View Quote Dashboard
        </Link>
      </div>
    </div>
  );
}
