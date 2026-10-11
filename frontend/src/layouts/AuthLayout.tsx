import type { ReactNode } from "react";

/** A centred box for the login and sign-up pages. No sidebar and no banner -
 *  nobody is logged in yet, so there's nowhere to go. */
export default function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-panel px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6">
          <h1 className="text-title font-semibold text-balance">
            Pre-Dispatch Returns Risk Engine
          </h1>
          <p className="font-condensed text-meta text-ink-muted">Ops dashboard prototype</p>
        </div>
        <main className="rounded-[4px] border border-rule bg-paper p-6">
          <h2 className="text-head font-semibold text-balance">{title}</h2>
          <p className="mt-1 text-meta text-ink-muted">{subtitle}</p>
          <div className="mt-5">{children}</div>
        </main>
      </div>
    </div>
  );
}
