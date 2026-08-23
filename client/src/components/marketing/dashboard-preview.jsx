import { Badge } from "@/components/ui/badge";
import { LogoMark } from "@/components/common/logo";

const stats = [
  { label: "Transactions", value: "12,847" },
  { label: "Matched", value: "94.2%" },
  { label: "Needs review", value: "312" },
  { label: "Unresolved", value: "48" },
];

const chartBars = [42, 58, 45, 66, 52, 74, 61, 83, 69, 91, 78, 96];

const exceptions = [
  { title: "Amount mismatch · $1,240.00", meta: "Stripe payout vs bank ledger", tone: "warning" },
  { title: "Missing entry · $86.40", meta: "Wire fee not recorded in ERP", tone: "destructive" },
  { title: "Duplicate candidate · $412.10", meta: "Two invoices flagged as identical", tone: "info" },
];

function PreviewRow({ className }) {
  return <div className={className} aria-hidden="true" />;
}

/**
 * Static, hand-built preview of the LedgerLens dashboard used on the landing page.
 * Intentionally non-interactive; represents the real product shell.
 */
function DashboardPreview() {
  return (
    <div
      role="img"
      aria-label="Preview of the LedgerLens reconciliation dashboard"
      className="overflow-hidden rounded-xl border border-border bg-card shadow-2xl shadow-slate-900/10"
    >
      {/* Window chrome */}
      <div className="flex items-center gap-1.5 border-b border-border bg-muted/60 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
        <div className="mx-auto flex h-5 w-56 items-center justify-center rounded-md border border-border bg-background text-[10px] text-muted-foreground">
          app.ledgerlens.io/dashboard
        </div>
        <div className="w-12" />
      </div>

      <div className="flex text-left">
        {/* Mini sidebar */}
        <aside className="hidden w-40 shrink-0 flex-col gap-0.5 border-r border-border p-3 sm:flex">
          <div className="mb-3 flex items-center gap-1.5 px-1">
            <LogoMark className="size-5 text-white" />
            <span className="text-xs font-semibold text-foreground">LedgerLens</span>
          </div>
          {["Overview", "Reconciliations", "Transactions", "Exceptions", "Sources"].map(
            (item, i) => (
              <div
                key={item}
                className={`flex h-6 items-center gap-2 rounded-md px-2 text-[11px] ${
                  i === 0 ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground"
                }`}
              >
                <PreviewRow className="size-2 rounded-[3px] bg-current opacity-50" />
                {item}
              </div>
            )
          )}
          <div className="mt-auto flex items-center gap-2 rounded-md px-2 py-1.5">
            <PreviewRow className="size-5 rounded-full bg-primary/15" />
            <div className="space-y-1">
              <PreviewRow className="h-1.5 w-14 rounded-full bg-slate-300" />
              <PreviewRow className="h-1.5 w-9 rounded-full bg-slate-200" />
            </div>
          </div>
        </aside>

        {/* Main panel */}
        <div className="min-w-0 flex-1 space-y-4 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">Good morning, Alex</p>
              <p className="text-[11px] text-muted-foreground">
                Here&rsquo;s what&rsquo;s happening with your financial data.
              </p>
            </div>
            <Badge variant="primary" className="gap-1 text-[10px]">
              AI investigating 3
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-lg border border-border p-2.5">
                <p className="text-[10px] text-muted-foreground">{stat.label}</p>
                <p className="mt-1 text-base font-semibold tracking-tight text-foreground">
                  {stat.value}
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-border p-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[11px] font-medium text-foreground">
                Reconciliation activity
              </p>
              <p className="text-[10px] text-muted-foreground">Last 12 weeks</p>
            </div>
            <div className="flex h-20 items-end gap-1.5">
              {chartBars.map((height, i) => (
                <div key={i} className="flex-1 rounded-t-[3px] bg-primary/80" style={{ height: `${height}%`, opacity: 0.35 + (i / chartBars.length) * 0.65 }} />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border">
            <div className="border-b border-border px-3 py-2">
              <p className="text-[11px] font-medium text-foreground">Recent exceptions</p>
            </div>
            <ul className="divide-y divide-border">
              {exceptions.map((item) => (
                <li key={item.title} className="flex items-center justify-between gap-2 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-[11px] font-medium text-foreground">{item.title}</p>
                    <p className="truncate text-[10px] text-muted-foreground">{item.meta}</p>
                  </div>
                  <Badge variant={item.tone} className="shrink-0 text-[9px] uppercase">
                    open
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export { DashboardPreview };
