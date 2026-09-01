"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";

import { LogoMark } from "@/components/common/logo";
import { ApiStatusBadge } from "@/components/common/api-status-badge";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { TopbarActions } from "@/components/layout/topbar-actions";
import { AskLedgerLens } from "@/components/domain/ask-ledgerlens";
import { AiContextProvider, useAiContext } from "@/components/common/ai-context";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

/**
 * Authenticated application shell: fixed sidebar on desktop, slide-in drawer
 * on smaller screens. Session data arrives pre-validated from the server layout.
 */
export function AppShell({ user, workspace, allWorkspaces, primaryNav, secondaryNav, children }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Escape closes the drawer; scroll is locked while open.
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Escape") setDrawerOpen(false);
    }
    if (drawerOpen) {
      document.addEventListener("keydown", onKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [drawerOpen]);

  const sidebarBody = (
    <>
      <div className="flex h-14 items-center px-4">
        <Link href="/dashboard" className="flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
          <LogoMark className="size-6 text-white" />
          <span className="text-[15px] font-semibold tracking-tight">LedgerLens</span>
        </Link>
      </div>
      <Separator />
      <div className="flex-1 overflow-y-auto p-3">
        <SidebarNav primary={primaryNav} secondary={secondaryNav} onNavigate={() => setDrawerOpen(false)} />
      </div>
      <Separator />
      <div className="p-3">
        <ApiStatusBadge className="px-1 pb-2" />
      </div>
    </>
  );

  return (
    <AiContextProvider>
      <div className="min-h-screen bg-background">
        {/* Desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
          {sidebarBody}
        </aside>

        {/* Mobile drawer */}
        <div
          className={cn(
            "fixed inset-0 z-50 lg:hidden",
            drawerOpen ? "pointer-events-auto" : "pointer-events-none"
          )}
          aria-hidden={!drawerOpen}
        >
          <div
            className={cn(
              "absolute inset-0 bg-navy/40 backdrop-blur-[2px] transition-opacity duration-200",
              drawerOpen ? "opacity-100" : "opacity-0"
            )}
            onClick={() => setDrawerOpen(false)}
          />
          <aside
            role="dialog"
            aria-label="Navigation menu"
            className={cn(
              "absolute inset-y-0 left-0 flex w-64 flex-col border-r border-sidebar-border bg-sidebar shadow-xl transition-transform duration-200",
              drawerOpen ? "translate-x-0" : "-translate-x-full"
            )}
          >
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close navigation menu"
              className="absolute right-2 top-3 flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
            {sidebarBody}
          </aside>
        </div>

        {/* Main column */}
        <div className="flex min-h-screen flex-col lg:pl-60">
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-md sm:px-6">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setDrawerOpen(true)}
                aria-label="Open navigation menu"
                className="-ml-1.5 flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 lg:hidden"
              >
                <Menu className="size-5" aria-hidden="true" />
              </button>
            </div>
            <TopbarActions user={user} workspace={workspace} allWorkspaces={allWorkspaces} />
          </header>

          {/* keyed by workspace so data views remount when the active workspace changes */}
          <main key={workspace?.id ?? "no-workspace"} className="flex-1">{children}</main>
        </div>

        {/* Workspace-scoped AI Reconciliation Copilot */}
        <AskLedgerLens />
        <NavigationTargetHandler />
      </div>
    </AiContextProvider>
  );
}

/**
 * Consumes the AI panel's "View {entity}" evidence actions (`navigationTarget`)
 * and routes the app to the referenced record.
 *
 * The backend emits four entity types for evidence — transaction, match,
 * exception, reconciliation — but only reconciliation runs have a dedicated
 * deep-linkable page (all other records are opened via drawers rooted on a
 * run). So the mapping is:
 *   - reconciliation        -> /dashboard/reconciliations/{id}
 *   - transaction / match   -> the run detail page (drawer entry point) when a
 *                              run is in context, else the run list / transactions.
 *   - exception             -> /dashboard/exceptions
 *
 * The copilot is closed on navigation so the journey continues on the target
 * page rather than behind the chat panel.
 */
function NavigationTargetHandler() {
  const router = useRouter();
  const { aiContext, navigationTarget, setNavigationTarget, setCopilotOpen } = useAiContext();

  useEffect(() => {
    if (!navigationTarget) return;

    const type = String(navigationTarget.type || "").toLowerCase();
    const id = navigationTarget.id;

    if (type === "reconciliation" || type === "reconciliation_run") {
      if (id) router.push(`/dashboard/reconciliations/${id}`);
    } else if (type === "exception") {
      router.push("/dashboard/exceptions");
    } else if (type === "transaction" || type === "match") {
      if (aiContext.reconciliationRunId) {
        router.push(`/dashboard/reconciliations/${aiContext.reconciliationRunId}`);
      } else if (type === "transaction") {
        router.push("/dashboard/transactions");
      } else {
        router.push("/dashboard/reconciliations");
      }
    }

    setCopilotOpen(false);
    setNavigationTarget(null);
  }, [
    navigationTarget,
    aiContext.reconciliationRunId,
    router,
    setCopilotOpen,
    setNavigationTarget,
  ]);

  return null;
}

