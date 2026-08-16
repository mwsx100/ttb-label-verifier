"use client";

import { useState } from "react";

export default function Home() {
  const [brand, setBrand] = useState("");
  const [abv, setAbv] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!file) {
      alert("Please select a label image.");
      return;
    }

    const formData = new FormData();
    formData.append("label", file);
    formData.append("expected_brand", brand);
    formData.append("expected_abv", abv);

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/verify", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      setResult(data);
    } catch (error) {
      console.error(error);
      alert("Could not connect to the verification server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-8">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-bold text-gray-900">
          Alcohol Label Verification
        </h1>

        <p className="mt-2 text-gray-600">
          Compare label artwork against application information.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-8 rounded-lg bg-white p-6 shadow"
        >
          <div className="mb-5">
            <label className="mb-2 block font-medium text-gray-800">
              Brand Name
            </label>

            <input
              type="text"
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
              required
              className="w-full rounded border border-gray-300 p-3 text-black"
              placeholder="Noilly Prat"
            />
          </div>

          <div className="mb-5">
            <label className="mb-2 block font-medium text-gray-800">
              Alcohol by Volume (%)
            </label>

            <input
              type="number"
              step="0.1"
              value={abv}
              onChange={(event) => setAbv(event.target.value)}
              required
              className="w-full rounded border border-gray-300 p-3 text-black"
              placeholder="16"
            />
          </div>

          <div className="mb-6">
            <label className="mb-2 block font-medium text-gray-800">
              Label Image
            </label>

            <input
              type="file"
              accept="image/*"
              onChange={(event) =>
                setFile(event.target.files?.[0] ?? null)
              }
              required
              className="block w-full text-gray-700"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="rounded bg-blue-700 px-6 py-3 font-semibold text-white disabled:opacity-50"
          >
            {loading ? "Verifying..." : "Verify Label"}
          </button>
        </form>

        {result && (
          <div className="mt-8 rounded-lg bg-white p-6 shadow">
            <h2 className="text-2xl font-bold text-gray-900">
              Verification Results
            </h2>

            <div className="mt-5 space-y-4">
              <ResultRow
                label="Brand Name"
                status={result.verification?.brand?.status}
                message={result.verification?.brand?.message}
              />

              <ResultRow
                label="Alcohol Content"
                status={result.verification?.abv?.status}
                message={result.verification?.abv?.message}
              />

              <ResultRow
                label="Government Warning"
                status={
                  result.extracted_fields?.government_warning?.found
                    ? "pass"
                    : "needs_review"
                }
                message={
                  result.extracted_fields?.government_warning?.found
                    ? "Government warning detected."
                    : "Government warning could not be confidently detected."
                }
              />

              <ResultRow
                label="Net Contents"
                status={
                  result.extracted_fields?.net_contents
                    ? "pass"
                    : "needs_review"
                }
                message={
                  result.extracted_fields?.net_contents
                    ? `Detected: ${result.extracted_fields.net_contents}`
                    : "Not detected. Check label or container marking."
                }
              />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function ResultRow({
  label,
  status,
  message,
}: {
  label: string;
  status?: string;
  message?: string;
}) {
  const symbol =
    status === "pass"
      ? "✓"
      : status === "fail"
        ? "✕"
        : "⚠";

  return (
    <div className="rounded border border-gray-200 p-4">
      <div className="font-semibold text-gray-900">
        {symbol} {label}
      </div>

      <div className="mt-1 text-sm text-gray-600">
        {message ?? "No result available."}
      </div>
    </div>
  );
}