const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface ContractorCreateRequest {
  business_name: string;
  phone: string;
  city?: string;
  whatsapp_link_slug: string;
  gst_number?: string;
  approval_mode?: string;
}

export interface ContractorResponse {
  id: string;
  business_name: string;
  phone: string;
  city: string | null;
  whatsapp_link_slug: string;
  gst_number: string | null;
  api_key: string;
}

export interface ParsedRulesResponse {
  rules: Record<string, unknown>;
  work_type_hint: string | null;
  notes: string[];
  validation_errors: string[];
}

export interface PricingConfigResponse {
  id: string;
  contractor_id: string;
  work_type: string;
  version: number;
}

export async function createContractor(
  data: ContractorCreateRequest
): Promise<ContractorResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/onboarding/contractors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to create contractor (${res.status})`);
  }
  return res.json();
}

export async function parseRateCard(
  file: File,
  workTypeHint?: string
): Promise<ParsedRulesResponse> {
  const form = new FormData();
  form.append("file", file);
  const url = new URL(`${BACKEND_URL}/api/v1/onboarding/rate-card/parse`);
  if (workTypeHint) url.searchParams.set("work_type_hint", workTypeHint);

  const res = await fetch(url.toString(), {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Rate card parsing failed (${res.status})`);
  }
  return res.json();
}

export async function savePricingConfig(
  contractorId: string,
  workType: string,
  rules: Record<string, unknown>,
  apiKey: string,
): Promise<PricingConfigResponse> {
  const res = await fetch(
    `${BACKEND_URL}/api/v1/contractors/${contractorId}/pricing/${workType}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Contractor-Key": apiKey,
      },
      body: JSON.stringify({ rules }),
      cache: "no-store",
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to save pricing config (${res.status})`);
  }
  return res.json();
}
