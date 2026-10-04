"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getEmployees } from "@/lib/api";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<
    { id: string; name: string; role_name: string }[]
  >([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEmployees()
      .then(setEmployees)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Employees</h1>
      {error && <p className="text-danger">{error}</p>}
      <table className="w-full overflow-hidden rounded-xl border border-slate-200 bg-white/80 text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-2">Name</th>
            <th className="px-4 py-2">Role</th>
            <th className="px-4 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {employees.map((emp) => (
            <tr
              key={emp.id}
              data-testid={`employee-row-${emp.id}`}
              className="border-t border-slate-100"
            >
              <td className="px-4 py-3">{emp.name}</td>
              <td className="px-4 py-3">{emp.role_name}</td>
              <td className="px-4 py-3">
                <Link
                  href={`/portal/employees/${emp.id}`}
                  className="text-accent underline"
                  data-testid={`employee-link-${emp.id}`}
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
