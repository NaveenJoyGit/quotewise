export interface Quote {
  id: string;
  buyer_phone: string;
  work_type: string;
  subtotal: string;
  gst_amount: string;
  total: string;
  status: string;
  pdf_url: string | null;
  validity_date: string | null;
  created_at: string;
  approved_at: string | null;
  sent_at: string | null;
  line_items: {
    description: string;
    quantity: string;
    unit: string;
    rate: string;
    amount: string;
  }[];
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function fetchQuotes(): Promise<Quote[]> {
  const res = await fetch(`${BACKEND_URL}/api/v1/quotes`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch quotes: ${res.status}`);
  }
  return res.json();
}
