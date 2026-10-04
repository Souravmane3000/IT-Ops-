"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  approveRun,
  evidenceFileUrl,
  getApiUrl,
  getEvidence,
  getRun,
  rejectRun,
} from "@/lib/api";

type TimelineEvent = {
  run_id: string;
  event_type: string;
  message: string;
  status: string;
  action_id?: string | null;
  timestamp: string;
  details?: Record<string, unknown>;
};

type ActionRow = {
  id: string;
  application_id: string;
  application_name?: string;
  status: string;
  requires_approval?: boolean;
  approval_decision?: string | null;
  recovery_attempts?: number;
};

type Milestone = {
  key: string;
  marker: string;
  text: string;
};

function friendlyStatus(
  status: string | undefined,
  actions: ActionRow[] = []
): string {
  switch (status) {
    case "running":
      return "Running";
    case "awaiting_approval":
      return "Waiting for approval";
    case "complete":
      if (actions.some((a) => a.approval_decision === "rejected")) {
        return "Complete — privileged access denied";
      }
      return "Complete";
    case "failed":
      return "Failed";
    case "blocked":
      return "Blocked";
    default:
      return status || "Loading";
  }
}

function accessLabel(action: ActionRow): string {
  if (action.status === "succeeded") {
    if (action.recovery_attempts && action.recovery_attempts > 0) {
      return "Recovered";
    }
    return "Granted";
  }
  if (action.status === "awaiting_approval") return "Awaiting approval";
  if (action.status === "rejected" || action.status === "skipped") {
    return action.approval_decision === "rejected" ? "Rejected" : "Skipped";
  }
  if (action.status === "failed") return "Failed";
  if (action.status === "running") return "Granting…";
  if (action.status === "pending") return "Pending";
  return action.status;
}

function checkLabel(check: string): string {
  if (check.startsWith("employee_exists")) return "Employee verified";
  if (check.startsWith("correct_role")) return "Role verified";
  if (check.startsWith("required_granted")) return "Required access verified";
  if (check.startsWith("privileged_approved")) return "Privileged approval verified";
  if (check.startsWith("privileged_rejected")) return "Privileged rejection verified";
  if (check.startsWith("skipped_not_granted")) return "Skipped access not granted";
  if (check.startsWith("audit_records")) return "Audit records present";
  if (check.startsWith("evidence_available")) return "Evidence available";
  if (check === "final" || check.includes("final")) return "Final state verified";
  return check.replace(/_/g, " ");
}

function buildMilestones(
  events: TimelineEvent[],
  actions: ActionRow[],
  employeeName: string | undefined,
  roleName: string | undefined,
  runStatus: string | undefined,
  verificationPassed: boolean | undefined
): Milestone[] {
  const milestones: Milestone[] = [];

  if (employeeName && roleName) {
    milestones.push({
      key: "identity",
      marker: "✓",
      text: `Identified ${employeeName} — ${roleName}`,
    });
  } else {
    const identified = events.find(
      (e) =>
        e.event_type === "decision" && e.message.startsWith("Identified ")
    );
    if (identified) {
      milestones.push({
        key: "identity",
        marker: "✓",
        text: identified.message,
      });
    }
  }

  const policyLoaded = events.some(
    (e) =>
      e.event_type === "decision" &&
      e.message.toLowerCase().includes("access policy")
  );
  if (policyLoaded) {
    milestones.push({
      key: "policy",
      marker: "✓",
      text: "Loaded access policy",
    });
  }

  for (const action of actions) {
    const name = action.application_name || action.application_id;
    if (action.status === "pending") continue;

    if (action.status === "awaiting_approval") {
      milestones.push({
        key: `action-${action.id}`,
        marker: "⚠",
        text: `${name} — approval required`,
      });
      continue;
    }

    if (action.status === "rejected" || action.status === "skipped") {
      milestones.push({
        key: `action-${action.id}`,
        marker: action.approval_decision === "rejected" ? "○" : "✓",
        text:
          action.approval_decision === "rejected"
            ? `${name} — not granted (rejected)`
            : `${name} — skipped`,
      });
      continue;
    }

    if (action.status === "failed") {
      milestones.push({
        key: `action-${action.id}`,
        marker: "⚠",
        text: `${name} — failed`,
      });
      continue;
    }

    if (action.status === "running") {
      milestones.push({
        key: `action-${action.id}`,
        marker: "↻",
        text: `${name} — granting…`,
      });
      continue;
    }

    if (action.status === "succeeded") {
      const recovered = (action.recovery_attempts || 0) > 0;
      milestones.push({
        key: `action-${action.id}`,
        marker: "✓",
        text: recovered ? `${name} — recovered` : `${name} — granted`,
      });
    }
  }

  const approvedPrivileged = actions.some(
    (a) => a.requires_approval && a.approval_decision === "approved"
  );
  if (approvedPrivileged) {
    milestones.push({
      key: "approval-received",
      marker: "👤",
      text: "Approval received",
    });
  }

  if (runStatus === "complete" || verificationPassed === true) {
    milestones.push({
      key: "verified",
      marker: "✓",
      text: "Final state verified",
    });
  } else if (runStatus === "failed" || runStatus === "blocked") {
    milestones.push({
      key: "failed",
      marker: "⚠",
      text: runStatus === "blocked" ? "Run blocked" : "Run failed",
    });
  }

  return milestones;
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [run, setRun] = useState<any>(null);
  const [evidence, setEvidence] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  const approvalEvent = useMemo(
    () =>
      [...events]
        .reverse()
        .find((e) => e.event_type === "approval_required"),
    [events]
  );

  const awaitingApproval =
    run?.status === "awaiting_approval" ||
    Boolean(run?.awaiting_approval) ||
    (approvalEvent &&
      !events.some(
        (e) =>
          e.event_type === "approval_received" &&
          e.timestamp >= approvalEvent.timestamp
      ) &&
      run?.status !== "complete" &&
      run?.status !== "failed");

  const isTerminal =
    run?.status === "complete" ||
    run?.status === "failed" ||
    run?.status === "blocked";

  async function refresh() {
    try {
      const data = await getRun(runId);
      setRun(data);
      if (
        data.status === "complete" ||
        data.status === "failed" ||
        data.status === "blocked"
      ) {
        const ev = await getEvidence(runId);
        setEvidence(ev);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run");
    }
  }

  useEffect(() => {
    refresh();
    const api = getApiUrl();
    const source = new EventSource(`${api}/runs/${runId}/events`);
    source.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as TimelineEvent;
        if (data.event_type) {
          setEvents((prev) => [...prev, data]);
        }
      } catch {
        /* ignore malformed */
      }
    };
    source.addEventListener("ping", () => {
      refresh();
    });
    const types = [
      "run_started",
      "step_started",
      "decision",
      "action_started",
      "action_succeeded",
      "action_failed",
      "approval_required",
      "approval_received",
      "recovery_started",
      "recovery_completed",
      "verification_started",
      "verification_completed",
      "run_completed",
      "run_failed",
    ];
    for (const type of types) {
      source.addEventListener(type, (msg) => {
        try {
          const data = JSON.parse((msg as MessageEvent).data) as TimelineEvent;
          setEvents((prev) => [...prev, data]);
          if (
            type === "approval_required" ||
            type === "approval_received" ||
            type === "run_completed" ||
            type === "run_failed" ||
            type === "verification_completed"
          ) {
            refresh();
          }
        } catch {
          /* ignore */
        }
      });
    }
    const interval = setInterval(refresh, 3000);
    return () => {
      source.close();
      clearInterval(interval);
    };
  }, [runId]);

  async function onApprove() {
    setBusy(true);
    try {
      await approveRun(runId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function onReject() {
    setBusy(true);
    try {
      await rejectRun(runId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }

  const actions: ActionRow[] = run?.actions || [];
  const employeeName = run?.employee?.name || run?.employee_name;
  const roleName = run?.employee?.role_name || run?.role_name;
  const title =
    employeeName && roleName
      ? `${employeeName} — ${roleName}`
      : employeeName || "Employee onboarding";

  const privilegedAppName = String(
    approvalEvent?.details?.application ||
      run?.awaiting_approval?.application_name ||
      "Privileged app"
  );

  const verification = evidence?.result?.verification_result;
  const checks: { check: string; pass: boolean }[] =
    verification?.checks || [];
  const pngFiles = (evidence?.files || []).filter((f: { name: string }) =>
    f.name.endsWith(".png")
  );

  const milestones = useMemo(
    () =>
      buildMilestones(
        events,
        actions,
        employeeName,
        roleName,
        run?.status,
        verification?.passed
      ),
    [events, actions, employeeName, roleName, run?.status, verification?.passed]
  );

  const recoveredActions = actions.filter(
    (a) => a.status === "succeeded" && (a.recovery_attempts || 0) > 0
  );

  const statusTone =
    run?.status === "awaiting_approval"
      ? "bg-amber-100 text-amber-900"
      : run?.status === "complete"
        ? "bg-emerald-100 text-emerald-900"
        : run?.status === "failed" || run?.status === "blocked"
          ? "bg-red-100 text-red-900"
          : "bg-slate-100 text-slate-800";

  const verificationLine =
    run?.status === "complete" || verification?.passed
      ? "Final state verified"
      : run?.status === "failed"
        ? "Verification failed"
        : run?.status === "blocked"
          ? "Run blocked"
          : "Verification unavailable";

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-3xl text-ink">{title}</h1>
          {run?.goal && (
            <p className="mt-1 line-clamp-2 text-sm text-slate-600">{run.goal}</p>
          )}
          <p className="mt-2 text-xs text-slate-400" title={runId}>
            Run {runId.slice(0, 12)}…
          </p>
        </div>
        <span
          data-testid="run-status"
          className={`rounded-md px-3 py-1 text-xs font-medium tracking-wide ${statusTone}`}
        >
          {friendlyStatus(run?.status, actions)}
        </span>
      </header>

      {error && <p className="text-sm text-danger">{error}</p>}

      {awaitingApproval && approvalEvent && (
        <section
          data-testid="approval-panel"
          className="rounded-xl border-2 border-amber-400 bg-amber-50 p-5 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-amber-950">
            Privileged access requires approval
          </h2>
          <dl className="mt-3 space-y-1 text-sm text-amber-950">
            <div>
              <dt className="inline font-medium">Application: </dt>
              <dd className="inline">{privilegedAppName}</dd>
            </div>
            <div>
              <dt className="inline font-medium">Employee: </dt>
              <dd className="inline">
                {String(
                  approvalEvent.details?.employee || employeeName || "—"
                )}
              </dd>
            </div>
            <div>
              <dt className="inline font-medium">Reason: </dt>
              <dd className="inline">
                {String(
                  approvalEvent.details?.reason || "Required by access policy"
                )}
              </dd>
            </div>
            <div>
              <dt className="inline font-medium">Risk: </dt>
              <dd className="inline">Privileged access</dd>
            </div>
          </dl>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={onApprove}
              className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Approve {privilegedAppName}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onReject}
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium disabled:opacity-50"
            >
              Reject {privilegedAppName}
            </button>
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Progress
        </h2>
        <ul className="space-y-2 text-sm" data-testid="progress-list">
          {milestones.map((m) => (
            <li key={m.key} className="flex gap-2 text-slate-800">
              <span className="w-5 shrink-0 text-center" aria-hidden>
                {m.marker}
              </span>
              <span>{m.text}</span>
            </li>
          ))}
          {milestones.length === 0 && (
            <li className="text-slate-500">Starting…</li>
          )}
        </ul>
      </section>

      {actions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Access
          </h2>
          <ul className="divide-y divide-slate-200 border-y border-slate-200 text-sm">
            {actions.map((action) => (
              <li
                key={action.id}
                className="flex items-center justify-between gap-3 py-2.5"
              >
                <span className="font-medium text-slate-800">
                  {action.application_name || action.application_id}
                </span>
                <span className="text-slate-600">{accessLabel(action)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {isTerminal && (
        <section className="space-y-4" data-testid="final-summary">
          <h2 className="font-display text-2xl text-ink">
            {run?.status === "complete"
              ? actions.some((a) => a.approval_decision === "rejected")
                ? "Complete — privileged access denied"
                : "Run complete"
              : `Run ${friendlyStatus(run?.status, actions).toLowerCase()}`}
          </h2>

          <div className="space-y-1 text-sm text-slate-700">
            <p className="font-medium text-ink">{title}</p>
            <p>
              <span className="text-slate-500">Access granted: </span>
              {actions
                .filter((a) => a.status === "succeeded")
                .map((a) => a.application_name || a.application_id)
                .join(", ") || "None"}
            </p>
            {recoveredActions.length > 0 && (
              <p>
                <span className="text-slate-500">Recovery: </span>
                {recoveredActions
                  .map(
                    (a) =>
                      `${a.application_name || a.application_id} failure recovered`
                  )
                  .join("; ")}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Verification
            </h3>
            <p className="text-sm text-ink">
              <span aria-hidden>
                {run?.status === "complete" || verification?.passed ? "✓ " : "⚠ "}
              </span>
              {verificationLine}
            </p>
          </div>

          <div className="space-y-3" data-testid="evidence-panel">
            <button
              type="button"
              onClick={() => setShowEvidence((v) => !v)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:border-accent"
            >
              {showEvidence ? "Hide evidence" : "View Evidence"}
              {pngFiles.length > 0 && !showEvidence
                ? ` (${pngFiles.length} screenshots)`
                : ""}
            </button>

            {showEvidence && (
              <div className="space-y-4 rounded-lg border border-slate-200 bg-white/80 p-4">
                <p className="text-sm text-slate-600">
                  Execution screenshots, verification checks, and final result
                  for this run.
                </p>
                {checks.length > 0 && (
                  <ul className="space-y-1 text-sm">
                    {checks.map((c, i) => (
                      <li key={`${c.check}-${i}`} className="flex gap-2">
                        <span aria-hidden>{c.pass ? "✓" : "✗"}</span>
                        <span>{checkLabel(c.check)}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  {pngFiles.map((f: { name: string }) => (
                    <figure key={f.name} className="space-y-1">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={evidenceFileUrl(runId, f.name)}
                        alt={f.name}
                        className="w-full rounded border border-slate-200"
                      />
                      <figcaption className="text-xs text-slate-500">
                        {f.name}
                      </figcaption>
                    </figure>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setShowRawJson((v) => !v)}
                  className="text-xs text-slate-500 underline"
                >
                  {showRawJson ? "Hide raw result" : "Show raw result"}
                </button>
                {showRawJson && (
                  <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {JSON.stringify(evidence?.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
