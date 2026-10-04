import Link from "next/link";

const links = [
  { href: "/portal/employees", label: "Employees", desc: "Find and manage employees" },
  { href: "/portal/applications", label: "Applications", desc: "Company applications catalog" },
  { href: "/portal/policies", label: "Policies", desc: "Role-based access policies" },
  { href: "/portal/audit", label: "Audit", desc: "Audit history" },
];

export default function PortalHomePage() {
  return (
    <div data-testid="portal-home" className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
          Synthetic IT Administration
        </p>
        <h1 className="font-display text-3xl">IT Portal</h1>
        <p className="mt-2 text-slate-600">
          Internal portal used by the AI computer operator via Playwright.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-sm hover:border-accent"
          >
            <h2 className="font-medium">{link.label}</h2>
            <p className="mt-1 text-sm text-slate-600">{link.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
