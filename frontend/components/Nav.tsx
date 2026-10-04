import Link from "next/link";

export function Nav() {
  return (
    <header className="border-b border-slate-200/80 bg-white/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-display text-xl tracking-tight text-ink">
          IT Ops
        </Link>
        <nav className="flex gap-4 text-sm text-slate-700">
          <Link href="/" className="hover:text-accent">
            Dashboard
          </Link>
          <Link href="/portal" className="hover:text-accent">
            Portal
          </Link>
        </nav>
      </div>
    </header>
  );
}
