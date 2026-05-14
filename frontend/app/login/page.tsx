"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = apiKey.trim();
    if (!UUID_RE.test(trimmed)) {
      setError(
        "Invalid key format. It should look like: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      );
      return;
    }
    const maxAge = 30 * 24 * 60 * 60;
    document.cookie = `contractor_key=${trimmed}; path=/; max-age=${maxAge}; SameSite=Strict`;
    router.push("/quotes");
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-6 py-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-1">
            Sign in to QuoteWise
          </h1>
          <p className="text-sm text-gray-500 mb-6">
            Enter the API key you received when you signed up.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setError("");
                }}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
                autoComplete="off"
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <button
              type="submit"
              className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Sign In
            </button>
          </form>

          <p className="mt-4 text-xs text-gray-400 text-center">
            Don&apos;t have an account?{" "}
            <a href="/onboarding" className="text-blue-600 hover:underline">
              Sign up here
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
