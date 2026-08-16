"use client";

import { useEffect, useState } from "react";

type VerificationStatus = "pass" | "fail" | "needs_review";

type Result = {
  extracted_fields?: {
    abv?: number | null;
    net_contents?: string | null;
    government_warning?: {
      found: boolean;
      matched_words: string[];
      match_count: number;
    };
  };
  verification?: {
    abv?: {
      status: VerificationStatus;
      expected: number;
      detected: number | null;
      message: string;
    };
    brand?: {
      status: VerificationStatus;
      expected: string;
      message: string;
    };
    class_type?: {
      status: VerificationStatus;
      expected: string;
      score: number;
      message: string;
    };
  };
  ocr_confidence?: number;
  extracted_text?: string;
};

export default function Home() {
  const [brand, setBrand] = useState("");
  const [abv, setAbv] = useState("");
  const [classType, setClassType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingTime, setProcessingTime] = useState<number | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }

    const url = URL.createObjectURL(file);
    setPreview(url);

    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!file) return;

    const formData = new FormData();
    formData.append("label", file);
    formData.append("expected_brand", brand);
    formData.append("expected_abv", abv);
    formData.append("expected_class_type", classType);

    setLoading(true);
    setResult(null);
    setProcessingTime(null);

    const start = performance.now();

    try {
      const response = await fetch("http://127.0.0.1:8000/verify", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Verification failed.");
      }

      const data = await response.json();

      setResult(data);
      setProcessingTime((performance.now() - start) / 1000);
    } catch (error) {
      console.error(error);
      alert("Could not verify this label.");
    } finally {
      setLoading(false);
    }
  }

  const results = result
    ? [
        {
          label: "Brand Name",
          status: result.verification?.brand?.status ?? "needs_review",
          expected: brand,
          detected:
            result.verification?.brand?.status === "pass"
              ? brand
              : "Not confidently detected",
        },

        {
          label: "Class / Type",
          status:
            result.verification?.class_type?.status ??
            "needs_review",
          expected: classType,
          detected:
            result.verification?.class_type?.status === "pass"
              ? classType
              : "Not confidently detected",
        },

        {
          label: "Alcohol Content",
          status: result.verification?.abv?.status ?? "needs_review",
          expected: `${abv}%`,
          detected:
            result.extracted_fields?.abv != null
              ? `${result.extracted_fields.abv}%`
              : "Not detected",
        },
        {
          label: "Government Warning",
          status:
            result.extracted_fields?.government_warning?.status ??
            "needs_review",
          expected: "Required",
          detected:
          result.extracted_fields?.government_warning?.detected
            ? "Warning language detected; exact compliance requires review"
            : "Not confidently detected",
        },
        {
          label: "Net Contents",
          status: result.extracted_fields?.net_contents
            ? "pass"
            : "needs_review",
          expected: "Required",
          detected:
            result.extracted_fields?.net_contents ??
            "Check label or container marking",
        },
      ]
    : [];

  const passed = results.filter((r) => r.status === "pass").length;
  const failed = results.filter((r) => r.status === "fail").length;
  const review = results.filter((r) => r.status === "needs_review").length;

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-6xl px-6 py-5">
          <h1 className="text-2xl font-semibold text-slate-900">
            Alcohol Label Verification
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            AI-assisted review of beverage label artwork.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <form onSubmit={handleSubmit}>
          <div className="grid gap-6 lg:grid-cols-2">

            <section className="rounded-xl border bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">
                Application Information
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Enter the information submitted with the application.
              </p>

              <div className="mt-6">
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Brand Name
                </label>

                <input
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  required
                  placeholder="Noilly Prat"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-900"
                />
              </div>
              <div className="mt-5">
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Class / Type
                </label>

                <input
                  value={classType}
                  onChange={(e) => setClassType(e.target.value)}
                  required
                  placeholder="French Vermouth"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-900"
                />
              </div>
              <div className="mt-5">
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Alcohol by Volume
                </label>

                <div className="relative">
                  <input
                    type="number"
                    step="0.1"
                    value={abv}
                    onChange={(e) => setAbv(e.target.value)}
                    required
                    placeholder="16"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-slate-900"
                  />

                  <span className="absolute right-3 top-2.5 text-slate-500">
                    %
                  </span>
                </div>
              </div>
              
            </section>

            <section className="rounded-xl border bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">
                Label Artwork
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Upload an image of the beverage label.
              </p>

              <label className="mt-6 flex min-h-64 cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-4">
                {preview ? (
                  <img
                    src={preview}
                    alt="Label preview"
                    className="max-h-72 rounded object-contain"
                  />
                ) : (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-700">
                      Select label image
                    </div>

                    <div className="mt-1 text-xs text-slate-500">
                      JPG, PNG, or other common image format
                    </div>
                  </div>
                )}

                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </section>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              type="submit"
              disabled={loading || !file}
              className="rounded-lg bg-slate-900 px-6 py-3 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Analyzing Label..." : "Verify Label"}
            </button>
          </div>
        </form>

        {result && (
          <section className="mt-8 rounded-xl border bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">
                  Verification Summary
                </h2>

                {processingTime !== null && (
                  <p className="mt-1 text-sm text-slate-500">
                    Processed in {processingTime.toFixed(2)} seconds
                  </p>
                )}
              </div>

              <div className="flex gap-2 text-sm">
                <SummaryBadge label={`${passed} Passed`} type="pass" />

                {review > 0 && (
                  <SummaryBadge
                    label={`${review} Needs Review`}
                    type="needs_review"
                  />
                )}

                {failed > 0 && (
                  <SummaryBadge label={`${failed} Failed`} type="fail" />
                )}
              </div>
            </div>

            <div className="mt-6 overflow-hidden rounded-lg border">
              {results.map((item) => (
                <ResultRow key={item.label} {...item} />
              ))}
            </div>

            <details className="mt-6 rounded-lg border p-4">
              <summary className="cursor-pointer font-medium text-slate-700">
                OCR Details
              </summary>

              <div className="mt-4">
                <p className="text-sm text-slate-600">
                  OCR confidence:{" "}
                  <strong>
                    {result.ocr_confidence?.toFixed(1) ?? "N/A"}%
                  </strong>
                </p>

                <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-100 p-4 text-xs text-slate-700">
                  {result.extracted_text}
                </pre>
              </div>
            </details>
          </section>
        )}
      </div>
    </main>
  );
}

function ResultRow({
  label,
  status,
  expected,
  detected,
}: {
  label: string;
  status: VerificationStatus;
  expected: string;
  detected: string;
}) {
  const statusText = {
    pass: "Pass",
    fail: "Fail",
    needs_review: "Needs Review",
  }[status];

  return (
    <div className="grid gap-3 border-b p-4 last:border-b-0 md:grid-cols-4">
      <div className="font-medium text-slate-900">{label}</div>

      <div>
        <div className="text-xs uppercase text-slate-400">Expected</div>
        <div className="mt-1 text-sm text-slate-700">{expected}</div>
      </div>

      <div>
        <div className="text-xs uppercase text-slate-400">Detected</div>
        <div className="mt-1 text-sm text-slate-700">{detected}</div>
      </div>

      <div className="md:text-right">
        <StatusBadge label={statusText} type={status} />
      </div>
    </div>
  );
}

function StatusBadge({
  label,
  type,
}: {
  label: string;
  type: VerificationStatus;
}) {
  const styles = {
    pass: "bg-green-100 text-green-800",
    fail: "bg-red-100 text-red-800",
    needs_review: "bg-amber-100 text-amber-800",
  };

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${styles[type]}`}
    >
      {label}
    </span>
  );
}

function SummaryBadge({
  label,
  type,
}: {
  label: string;
  type: VerificationStatus;
}) {
  return <StatusBadge label={label} type={type} />;
}