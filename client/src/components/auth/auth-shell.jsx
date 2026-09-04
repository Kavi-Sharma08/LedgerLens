import Link from "next/link";

import { Logo, LogoMark } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

/**
 * Shared layout for the signed-out authentication screens (login, signup,
 * forgot password). Provides a refined layout: a centered auth form column
 * with a compact product-context card that sits beside it on large screens
 * and stacks below it on smaller ones.
 *
 * The supporting card is intentionally small — it supports the form rather
 * than dominating the screen.
 */
function AuthShell({
  title,
  subtitle,
  footer,
  children,
  panel,
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <header className="flex items-center justify-between gap-4 border-b border-border/80 px-5 py-4 sm:px-10">
        <Logo />
        <Button variant="ghost" size="sm" render={<Link href="/" />}>
          Back to site
        </Button>
      </header>

      {/* Body */}
      <div className="flex flex-1 items-center justify-center px-5 py-10 sm:px-10">
        <div className="grid w-full max-w-3xl items-center gap-10 lg:grid-cols-[minmax(0,26rem)_minmax(0,19rem)] lg:justify-between lg:gap-16">
          {/* Form column */}
          <main className="mx-auto w-full max-w-md lg:mx-0">
            <h1 className="text-[26px] font-semibold tracking-tight text-foreground sm:text-[28px]">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
                {subtitle}
              </p>
            )}
            <div className="mt-8">{children}</div>
            {footer && (
              <p className="mt-8 text-sm text-muted-foreground">{footer}</p>
            )}
          </main>

          {/* Supporting panel */}
          {panel && (
            <aside className="mx-auto w-full max-w-md lg:mx-0" aria-label="About LedgerLens">
              <div className="relative overflow-hidden rounded-2xl border border-border bg-navy p-6">
                <LogoMark className="size-8 text-white/90" />
                <p className="mt-5 text-lg font-semibold tracking-tight text-white">
                  {panel.headline}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">
                  {panel.text}
                </p>
                <ul className="mt-6 space-y-2.5 border-t border-white/10 pt-5">
                  {panel.points.map((point) => (
                    <li
                      key={point}
                      className="flex items-center gap-2.5 text-sm text-slate-300"
                    >
                      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/25">
                        <svg
                          className="size-3 text-indigo-300"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </span>
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            </aside>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border/60 px-5 py-4 text-center text-xs text-muted-foreground sm:px-10">
        &copy; {new Date().getFullYear()} LedgerLens, Inc.
      </footer>
    </div>
  );
}

export { AuthShell };
