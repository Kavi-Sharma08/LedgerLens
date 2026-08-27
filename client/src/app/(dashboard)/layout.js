import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceProvider } from "@/components/common/workspace-provider";
import { DashboardProvider } from "@/components/common/dashboard-context";
import { buildDashboardProfile } from "@/lib/permissions";
import { serverApi, ApiError } from "@/lib/api/client";
import { auth } from "@/lib/auth";
import { filterDashboardNav } from "@/lib/navigation";

const ACTIVE_WORKSPACE_COOKIE = "ll-active-workspace";

/**
 * Protected route boundary for the entire authenticated area.
 *
 * Auth.js (server-side) validates the HttpOnly session cookie BEFORE any
 * dashboard content renders — an unauthenticated visitor is redirected without
 * ever seeing protected UI.
 *
 * Workspace data arrives from FastAPI via trusted server-to-server calls.
 * The active workspace is determined by the ll-active-workspace cookie, which
 * the backend verifies membership for. When the cookie is missing or stale we
 * resolve the correct workspace server-side and persist it to the cookie so
 * every subsequent browser->backend call carries the same workspace the server
 * rendered with — no stale/previous-workspace state leaks into data fetches.
 *
 * The signed-in member's role for the active workspace is resolved from the
 * server member list and exposed through DashboardProvider so pages and the
 * navigation render from server-authoritative permissions.
 */
export default async function DashboardLayout({ children }) {
  const session = await auth();
  if (!session?.user?.id) {
    redirect("/login");
  }

  const user = {
    id: session.user.id,
    name: session.user.name,
    email: session.user.email,
    avatar: session.user.image,
  };

  // Read active workspace from cookie
  const cookieStore = await cookies();
  const activeWorkspaceId = cookieStore.get(ACTIVE_WORKSPACE_COOKIE)?.value;

  let workspace = null;
  let allWorkspaces = [];
  let workspacesLoaded = false;

  try {
    // Fetch all workspaces the user belongs to
    allWorkspaces = await serverApi.get("/api/workspaces", { session });

    // Ensure it's an array (serverApi returns parsed JSON)
    if (!Array.isArray(allWorkspaces)) {
      allWorkspaces = [];
    }

    workspacesLoaded = true;

    if (activeWorkspaceId && allWorkspaces.length > 0) {
      // Use the cookie-specified workspace if it's in the user's list
      workspace = allWorkspaces.find((ws) => ws.id === activeWorkspaceId) || null;
    }

    // If the cookie workspace was invalid or missing, pick the first available
    if (!workspace && allWorkspaces.length > 0) {
      workspace = allWorkspaces[0];
    }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    // API unreachable: render without workspace data.
    // WorkspaceProvider client component will handle resolution.
  }

  // Only redirect to onboarding if the API succeeded and returned zero workspaces.
  // If the API failed, allWorkspaces stays [] but we should NOT redirect —
  // the user may have workspaces and the API was just temporarily down.
  if (allWorkspaces.length === 0 && workspacesLoaded) {
    redirect("/onboarding");
  }

  // Persist the resolved workspace to the cookie so the server-rendered page
  // and every browser->backend data fetch agree on the active workspace. The
  // cookie itself cannot be written from this Server Component (Next.js
  // restricts it to Server Actions/Route Handlers), so we hand the resolved
  // id to WorkspaceProvider, which writes it on the client before data views
  // fetch. This prevents "No workspace selected" / stale-workspace data even on
  // first load when the cookie hasn't been written yet.
  let profile = { role: null, rolePermissions: null, workspaceId: workspace?.id ?? null, can: {} };
  let primaryNav = null;
  let secondaryNav = null;

  if (workspace?.id && session.user.id) {
    let role = null;
    try {
      const members = await serverApi.get(`/api/workspaces/${workspace.id}/members`, {
        session,
        workspaceId: workspace.id,
      });
      const current = (members || []).find((m) => m.userId === session.user.id);
      role = current?.role ?? null;
    } catch {
      // Could not resolve role (members API unreachable). Navigation renders
      // conservatively and pages rely on their own server-side gating.
    }

    profile = buildDashboardProfile({
      role,
      rolePermissions: workspace.rolePermissions,
      workspaceId: workspace.id,
    });
    const filtered = filterDashboardNav(profile.can);
    primaryNav = filtered.primary;
    secondaryNav = filtered.secondary;
  }

  return (
    <WorkspaceProvider serverWorkspaceId={workspace?.id ?? null}>
      <DashboardProvider value={profile}>
        <AppShell
          user={user}
          workspace={workspace}
          allWorkspaces={allWorkspaces}
          primaryNav={primaryNav}
          secondaryNav={secondaryNav}
        >
          {children}
        </AppShell>
      </DashboardProvider>
    </WorkspaceProvider>
  );
}
