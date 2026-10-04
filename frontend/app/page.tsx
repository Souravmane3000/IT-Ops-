"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";

const DEFAULT_GOAL =
  "Onboard Alex, who is joining as a Marketing Manager. Give Alex the applications required by the company's access policy, but ask me for approval before granting any privileged access.";

export default function HomePage() {
  const router = useRouter();
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onStart() {
    setLoading(true);
    setError(null);
    try {
      const run = await createRun(goal);
      router.push(`/run/${run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="font-display text-4xl text-ink">Employee Onboarding</h1>
        <p className="mt-2 text-slate-600">
          Enter a goal. The operator uses a real browser, pauses for privileged
          approval, recovers from failure, and verifies the result.
        </p>
      </div>

      <label className="block space-y-2">
        <span className="text-sm font-medium text-slate-700">
          Natural-language onboarding goal
        </span>
        <textarea
          className="min-h-36 w-full rounded-lg border border-slate-300 bg-white/90 p-3 text-sm shadow-sm outline-none focus:border-accent"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
        />
      </label>

      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onStart}
          disabled={loading || !goal.trim()}
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Starting…" : "Start Run"}
        </button>
      </div>

      <p className="text-xs text-slate-500">
        Variation: Onboard Priya as a Finance Analyst and give her the
        applications required by policy.
      </p>
    </section>
  );
}
