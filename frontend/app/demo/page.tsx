"use client";

import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  role: "buyer" | "bot";
  text: string;
}

interface QuoteData {
  id: string;
  subtotal: string;
  gst_amount: string;
  total: string;
  work_type: string;
  line_items: Array<{ description: string; amount: string; [k: string]: string }>;
  status: string;
}

type DecisionState = "none" | "deciding" | "approved" | "rejected";

export default function DemoPage() {
  const [sessionId] = useState<string>(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [decision, setDecision] = useState<DecisionState>("none");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "buyer", text }]);
    setSending(true);
    try {
      const res = await fetch(`${API}/api/v1/demo/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: sessionId }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setMessages((m) => [...m, { role: "bot", text: data.reply ?? "" }]);
      if (data.quote) setQuote(data.quote);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: "⚠️ Could not reach the backend. Is the server running?" },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function handleDecide(action: "approve" | "reject") {
    if (!quote || decision === "deciding") return;
    setDecision("deciding");
    setDecisionError(null);
    try {
      const res = await fetch(`${API}/api/v1/demo/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quote_id: quote.id, action }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setDecision(action === "approve" ? "approved" : "rejected");
      if (data.pdf_url) setPdfUrl(data.pdf_url);
    } catch (e) {
      setDecisionError(e instanceof Error ? e.message : "Request failed");
      setDecision("none");
    }
  }

  function reset() {
    window.location.reload();
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">QuoteWise Demo</h1>
          <p className="text-xs text-gray-500">No WhatsApp required — runs against local backend</p>
        </div>
        <button
          onClick={reset}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Reset conversation
        </button>
      </header>

      {/* Two-pane body */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Buyer chat ── */}
        <div className="flex flex-col w-1/2 border-r border-gray-200">
          <div className="bg-[#075e54] text-white px-4 py-2 text-sm font-medium">
            Buyer view — WhatsApp simulation
          </div>

          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto px-4 py-4 space-y-2"
            style={{ background: "#e5ddd5" }}
          >
            {messages.length === 0 && (
              <p className="text-center text-xs text-gray-500 mt-8">
                Type a message below to start the conversation
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "buyer" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-xs rounded-lg px-3 py-2 text-sm shadow-sm whitespace-pre-wrap ${
                    m.role === "buyer"
                      ? "bg-[#dcf8c6] text-gray-900 rounded-br-none"
                      : "bg-white text-gray-900 rounded-bl-none"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-white rounded-lg px-3 py-2 text-sm shadow-sm text-gray-400 italic">
                  typing…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="bg-white border-t border-gray-200 px-3 py-2 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
              placeholder="Type a message…"
              disabled={sending || !!quote}
              className="flex-1 rounded-full border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || sending || !!quote}
              className="rounded-full bg-[#128c7e] text-white px-4 py-2 text-sm font-medium hover:bg-[#075e54] disabled:opacity-50 transition-colors"
            >
              Send
            </button>
          </div>
        </div>

        {/* ── RIGHT: Contractor view ── */}
        <div className="flex flex-col w-1/2 overflow-y-auto">
          <div className="bg-blue-700 text-white px-4 py-2 text-sm font-medium">
            Contractor view
          </div>

          <div className="flex-1 p-6">
            {!quote && (
              <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
                <svg
                  className="w-16 h-16 mb-4 opacity-30"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <p className="text-sm">Waiting for quote to be generated…</p>
                <p className="mt-1 text-xs">
                  Chat on the left until the AI produces a price.
                </p>
              </div>
            )}

            {quote && (
              <div className="space-y-5">
                <div className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-3">
                  <p className="text-yellow-800 font-semibold text-sm">
                    New quote pending your approval
                  </p>
                  <p className="text-yellow-700 text-xs mt-0.5 capitalize">
                    Work type: {quote.work_type.replace("_", " ")}
                  </p>
                </div>

                {/* Line items */}
                {quote.line_items.length > 0 && (
                  <div className="rounded-md border border-gray-200 overflow-hidden">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left font-medium text-gray-600">Item</th>
                          <th className="px-4 py-2 text-right font-medium text-gray-600">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {quote.line_items.map((item, i) => (
                          <tr key={i}>
                            <td className="px-4 py-2 text-gray-700">{item.description ?? JSON.stringify(item)}</td>
                            <td className="px-4 py-2 text-right text-gray-700">
                              {item.amount != null ? `Rs. ${item.amount}` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Totals */}
                <div className="rounded-md bg-gray-50 border border-gray-200 divide-y divide-gray-100">
                  <div className="flex justify-between px-4 py-2 text-sm">
                    <span className="text-gray-600">Subtotal</span>
                    <span className="font-medium">Rs. {quote.subtotal}</span>
                  </div>
                  <div className="flex justify-between px-4 py-2 text-sm">
                    <span className="text-gray-600">GST</span>
                    <span className="font-medium">Rs. {quote.gst_amount}</span>
                  </div>
                  <div className="flex justify-between px-4 py-2 text-sm font-semibold">
                    <span className="text-gray-900">Total</span>
                    <span className="text-gray-900">Rs. {quote.total}</span>
                  </div>
                </div>

                {/* Decision buttons */}
                {decision === "none" && (
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleDecide("approve")}
                      className="flex-1 bg-green-600 text-white rounded-md py-2 text-sm font-medium hover:bg-green-700 transition-colors"
                    >
                      Approve & Generate PDF
                    </button>
                    <button
                      onClick={() => handleDecide("reject")}
                      className="flex-1 bg-red-600 text-white rounded-md py-2 text-sm font-medium hover:bg-red-700 transition-colors"
                    >
                      Reject
                    </button>
                  </div>
                )}

                {decision === "deciding" && (
                  <p className="text-center text-sm text-gray-500">Processing…</p>
                )}

                {decisionError && (
                  <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                    {decisionError}
                  </div>
                )}

                {decision === "approved" && (
                  <div className="rounded-md bg-green-50 border border-green-200 px-4 py-4 space-y-2">
                    <p className="text-green-800 font-semibold text-sm">Quote approved!</p>
                    {pdfUrl ? (
                      <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block rounded-md bg-green-600 text-white px-4 py-2 text-sm font-medium hover:bg-green-700 transition-colors"
                      >
                        Open PDF
                      </a>
                    ) : (
                      <p className="text-green-700 text-xs">
                        PDF generation skipped (WeasyPrint not installed).
                      </p>
                    )}
                  </div>
                )}

                {decision === "rejected" && (
                  <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3">
                    <p className="text-red-800 font-semibold text-sm">Quote rejected.</p>
                    <p className="text-red-700 text-xs mt-0.5">
                      Click "Reset conversation" to start again.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
