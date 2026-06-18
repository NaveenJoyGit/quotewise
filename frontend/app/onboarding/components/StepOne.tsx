"use client";

import { useState } from "react";
import {
  ContractorCreateRequest,
  ContractorResponse,
  createContractor,
} from "@/lib/onboarding-api";

interface Props {
  onComplete: (contractor: ContractorResponse) => void;
}

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

export default function StepOne({ onComplete }: Props) {
  const [form, setForm] = useState<ContractorCreateRequest>({
    business_name: "",
    phone: "",
    city: "",
    whatsapp_link_slug: "",
    gst_number: "",
    approval_mode: "always_approve",
    wa_phone_number_id: "",
  });
  const [slugEdited, setSlugEdited] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (name === "whatsapp_link_slug") setSlugEdited(true);
  }

  function handleNameBlur() {
    if (!slugEdited && form.business_name) {
      setForm((prev) => ({ ...prev, whatsapp_link_slug: toSlug(form.business_name) }));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: ContractorCreateRequest = {
        business_name: form.business_name,
        phone: form.phone,
        city: form.city || undefined,
        whatsapp_link_slug: form.whatsapp_link_slug,
        gst_number: form.gst_number || undefined,
        approval_mode: form.approval_mode,
        wa_phone_number_id: form.wa_phone_number_id || undefined,
      };
      const contractor = await createContractor(payload);
      onComplete(contractor);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Business name <span className="text-red-500">*</span>
        </label>
        <input
          name="business_name"
          value={form.business_name}
          onChange={handleChange}
          onBlur={handleNameBlur}
          required
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. Sharma Interiors"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          WhatsApp number (E.164) <span className="text-red-500">*</span>
        </label>
        <input
          name="phone"
          value={form.phone}
          onChange={handleChange}
          required
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="+919876543210"
        />
        <p className="mt-1 text-xs text-gray-500">Include country code, e.g. +91 for India</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
        <input
          name="city"
          value={form.city}
          onChange={handleChange}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Bangalore"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          WhatsApp link slug <span className="text-red-500">*</span>
        </label>
        <input
          name="whatsapp_link_slug"
          value={form.whatsapp_link_slug}
          onChange={handleChange}
          required
          pattern="^[a-z0-9-]{3,64}$"
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="sharma-interiors"
        />
        <p className="mt-1 text-xs text-gray-500">
          Buyers will message: <span className="font-mono">quote-{form.whatsapp_link_slug || "your-slug"}</span>
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          GST number (optional)
        </label>
        <input
          name="gst_number"
          value={form.gst_number}
          onChange={handleChange}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="22AAAAA0000A1Z5"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Twilio WA Phone Number ID (optional)
        </label>
        <input
          name="wa_phone_number_id"
          value={form.wa_phone_number_id}
          onChange={handleChange}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="+14155238886"
        />
        <p className="mt-1 text-xs text-gray-500">
          The Twilio Sandbox "To" number (E.164 format)
        </p>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Creating account..." : "Continue to Rate Card"}
      </button>
    </form>
  );
}
