const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getApiUrl() {
  return API_URL;
}

export function createRun(goal: string) {
  return request<{ run_id: string; status: string }>("/runs", {
    method: "POST",
    body: JSON.stringify({ goal }),
  });
}

export function getRun(runId: string) {
  return request<Record<string, unknown>>(`/runs/${runId}`);
}

export function approveRun(runId: string) {
  return request<{ status: string; decision: string }>(`/runs/${runId}/approve`, {
    method: "POST",
  });
}

export function rejectRun(runId: string) {
  return request<{ status: string; decision: string }>(`/runs/${runId}/reject`, {
    method: "POST",
  });
}

export function getEvidence(runId: string) {
  return request<{
    run_id: string;
    files: { name: string; path: string }[];
    result: Record<string, unknown> | null;
  }>(`/runs/${runId}/evidence`);
}

export function evidenceFileUrl(runId: string, filename: string) {
  return `${API_URL}/runs/${runId}/evidence/${filename}`;
}

export function getEmployees() {
  return request<
    { id: string; name: string; role_id: string; role_name: string }[]
  >("/portal/employees");
}

export function getEmployee(id: string) {
  return request<{
    id: string;
    name: string;
    role_id: string;
    role_name: string;
    permissions: {
      application_id: string;
      application_name: string;
      status: string;
      privileged: boolean;
    }[];
    applications: {
      id: string;
      name: string;
      privileged: boolean;
      fails_on_grant: boolean;
    }[];
    policy_applications: {
      application_id: string;
      application_name: string;
      privileged: boolean;
    }[];
  }>(`/portal/employees/${id}`);
}

export function getApplications() {
  return request<
    {
      id: string;
      name: string;
      privileged: boolean;
      fails_on_grant: boolean;
    }[]
  >("/portal/applications");
}

export function getPolicies() {
  return request<
    {
      id: string;
      role_name: string;
      application_name: string;
      required: boolean;
      privileged: boolean;
    }[]
  >("/portal/policies");
}

export function getAudit() {
  return request<
    {
      id: string;
      run_id: string | null;
      employee_id: string | null;
      action: string;
      status: string;
      timestamp: string;
      details: string | null;
    }[]
  >("/portal/audit");
}

export function grantApplication(employeeId: string, applicationId: string) {
  return request<{
    success: boolean;
    employee_id?: string;
    application_id?: string;
    status?: string;
    error?: string;
    already_granted?: boolean;
  }>(`/portal/employees/${employeeId}/applications/${applicationId}/grant`, {
    method: "POST",
  });
}
