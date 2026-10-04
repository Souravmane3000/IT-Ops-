"use client";

import { useEffect, useState } from "react";
import { getApplications } from "@/lib/api";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<
    { id: string; name: string; privileged: boolean; fails_on_grant: boolean }[]
  >([]);

  useEffect(() => {
    getApplications().then(setApps).catch(console.error);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Applications</h1>
      <ul className="space-y-2">
        {apps.map((app) => (
          <li
            key={app.id}
            data-testid={`application-${app.id}`}
            className="rounded-lg border border-slate-200 bg-white/80 px-4 py-3"
          >
            <p className="font-medium">{app.name}</p>
            <p className="text-sm text-slate-600">
              {app.privileged ? "Privileged" : "Standard"}
              {app.fails_on_grant ? " · Controlled failure enabled" : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
