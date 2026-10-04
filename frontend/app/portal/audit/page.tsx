"use client";

import { useEffect, useState } from "react";
import { getAudit } from "@/lib/api";

export default function AuditPage() {
  const [rows, setRows] = useState<
    {
      id: string;
      run_id: string | null;
      employee_id: string | null;
      action: string;
      status: string;
      timestamp: string;
      details: string | null;
    }[]
  >([]);

  useEffect(() => {
    getAudit().then(setRows).catch(console.error);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Audit History</h1>
      <div className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.id}
            data-testid={`audit-row-${row.id}`}
            className="rounded-lg border border-slate-200 bg-white/80 px-4 py-3 text-sm"
          >
            <div className="flex justify-between gap-4">
              <p className="font-medium">{row.action}</p>
              <p className="text-slate-500">{row.timestamp}</p>
            </div>
            <p className="text-slate-600">
              Status: {row.status}
              {row.run_id ? ` · Run: ${row.run_id}` : ""}
              {row.employee_id ? ` · Employee: ${row.employee_id}` : ""}
            </p>
          </div>
        ))}
        {rows.length === 0 && <p className="text-slate-500">No audit records yet.</p>}
      </div>
    </div>
  );
}
