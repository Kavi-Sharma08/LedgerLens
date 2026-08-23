import Link from "next/link";

import { Check } from "lucide-react";

import { Logo, LogoMark } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

const highlights = [
  "Reconcile every ledger automatically",
  "AI investigates the exceptions that matter",
  "Full audit trail, ready for review",
];

/**
 * Shared layout for all authentication screens (login, signup, forgot password).
 * Two-pane layout: focused form on the left, quiet product narrative on the right.
 */
function AuthShell({ title, subtitle, footer, children }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,34rem)_1fr]">
      <div className="flex flex-col px-6 py-6 sm:px-10 lg:px-14">
        <header className="flex items-center justify-between">
          <Logo />
          <Button variant="ghost" size="sm" render={<Link href="/" />}>
            Back to site
          </Button>
        </header>

        <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          {subtitle && (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{subtitle}</p>
          )}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-8 text-sm text-muted-foreground">{footer}</div>}
        </main>

        <footer className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} LedgerLens, Inc.
        </footer>
      </div>

      <aside className="relative hidden overflow-hidden bg-navy lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_40rem_at_120%_-10%,rgba(79,70,229,0.35),transparent_60%)]"
        />
        <LogoMark className="size-9 text-white/90" />

        <div className="relative space-y-8">
          <blockquote className="max-w-md text-xl leading-relaxed font-medium tracking-tight text-slate-200">
            &ldquo;Our close went from five days of spreadsheet archaeology to an afternoon of
            reviewing exceptions.&rdquo;
          </blockquote>
          <figcaption className="flex items-center gap-3 text-sm">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-full bg-primary/30 text-xs font-semibold text-white"
            >
              MK
            </span>
            <span className="text-slate-400">
              Maya K., Controller at Northwind Systems
            </span>
          </figcaption>

          <ul className="space-y-3 border-t border-white/10 pt-6">
            {highlights.map((item) => (
              <li key={item} className="flex items-center gap-3 text-sm text-slate-300">
                <span className="flex size-5 items-center justify-center rounded-full bg-primary/25">
                  <Check className="size-3 text-indigo-300" aria-hidden="true" />
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">
          SOC 2 controls · Encryption at rest · Human-in-the-loop AI
        </p>
      </aside>
    </div>
  );
}

export { AuthShell };
