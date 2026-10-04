"use client";

import { useEffect, useState } from "react";
import { getPolicies } from "@/lib/api";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<
    {
      id: string;
      role_name: string;
      application_name: string;
      required: boolean;
      privileged: boolean;
    }[]
  >([]);

  useEffect(() => {
    getPolicies().then(setPolicies).catch(console.error);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Access Policies</h1>
      <table className="w-full rounded-xl border border-slate-200 bg-white/80 text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-2">Role</th>
            <th className="px-4 py-2">Application</th>
            <th className="px-4 py-2">Required</th>
            <th className="px-4 py-2">Privileged</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.id} className="border-t border-slate-100">
              <td className="px-4 py-3">{p.role_name}</td>
              <td className="px-4 py-3">{p.application_name}</td>
              <td className="px-4 py-3">{p.required ? "Yes" : "No"}</td>
              <td className="px-4 py-3">{p.privileged ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
