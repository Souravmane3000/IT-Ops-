"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getEmployee, grantApplication } from "@/lib/api";

type EmployeeDetail = Awaited<ReturnType<typeof getEmployee>>;

export default function EmployeeDetailPage() {
  const params = useParams<{ id: string }>();
  const employeeId = params.id;
  const [data, setData] = useState<EmployeeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [grantError, setGrantError] = useState<string>("");
  const [busyApp, setBusyApp] = useState<string | null>(null);
  const [grantState, setGrantState] = useState<"idle" | "pending" | "success" | "error">(
    "idle"
  );
  const [grantSeq, setGrantSeq] = useState(0);

  async function reload() {
    const detail = await getEmployee(employeeId);
    setData(detail);
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message));
  }, [employeeId]);

  async function onGrant(applicationId: string) {
    setBusyApp(applicationId);
    setGrantError("");
    setGrantState("pending");
    const nextSeq = grantSeq + 1;
    setGrantSeq(nextSeq);
    try {
      const result = await grantApplication(employeeId, applicationId);
      if (!result.success) {
        setGrantError(result.error || "Grant failed");
        setGrantState("error");
      } else {
        setGrantState("success");
      }
      await reload();
    } catch (e) {
      setGrantError(e instanceof Error ? e.message : "Grant failed");
      setGrantState("error");
    } finally {
      setBusyApp(null);
    }
  }

  if (error) return <p className="text-danger">{error}</p>;
  if (!data) return <p>Loading…</p>;

  const granted = new Set(
    data.permissions.filter((p) => p.status === "granted").map((p) => p.application_id)
  );

  return (
    <div data-testid={`employee-detail-${employeeId}`} className="space-y-6">
      <div>
        <h1 className="font-display text-3xl">{data.name}</h1>
        <p className="text-slate-600">
          Role: <span data-testid="employee-role">{data.role_name}</span>
        </p>
      </div>

      <div
        data-testid="grant-state"
        data-state={grantState}
        data-seq={grantSeq}
        className="hidden"
      />

      {grantError && (
        <div
          data-testid="grant-error"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger"
        >
          {grantError}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Applications</h2>
        <div className="space-y-2">
          {data.applications.map((app) => {
            const isGranted = granted.has(app.id);
            return (
              <div
                key={app.id}
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white/80 px-4 py-3"
              >
                <div>
                  <p className="font-medium">
                    {app.name}{" "}
                    {app.privileged && (
                      <span className="ml-2 text-xs uppercase text-warn">
                        Privileged
                      </span>
                    )}
                  </p>
                  <p
                    data-testid={`permission-status-${app.id}`}
                    data-granted={isGranted ? "true" : "false"}
                    className="text-sm text-slate-600"
                  >
                    {isGranted ? "Granted" : "Not granted"}
                  </p>
                </div>
                {!isGranted && (
                  <button
                    type="button"
                    data-testid={`grant-btn-${app.id}`}
                    disabled={busyApp === app.id}
                    onClick={() => onGrant(app.id)}
                    className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50"
                  >
                    {busyApp === app.id ? "Granting…" : "Grant"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
