import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceProvider } from "@/components/common/workspace-provider";
import { serverApi, ApiError } from "@/lib/api/client";
import { auth } from "@/lib/auth";

/**
 * Protected route boundary for the entire authenticated area.
 *
 * Auth.js (server-side) validates the HttpOnly session cookie BEFORE any
 * dashboard content renders — an unauthenticated visitor is redirected without
 * ever seeing protected UI.
 *
 * Workspace data arrives from FastAPI via trusted server-to-server calls.
 * The active workspace is determined by the ll-active-workspace cookie, which
 * the backend verifies membership for.
 *
 * If the cookie workspace is invalid (deleted, user removed), we fall back
 * to the user's first available workspace and pass it to WorkspaceProvider,
 * which rewrites the cookie so subsequent API calls use the corrected workspace.
 * If the user has zero workspaces, we redirect to /onboarding.
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
  const activeWorkspaceId = cookieStore.get("ll-active-workspace")?.value;

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

  return (
    <WorkspaceProvider serverWorkspaceId={workspace?.id ?? null}>
      <AppShell user={user} workspace={workspace} allWorkspaces={allWorkspaces}>
        {children}
      </AppShell>
    </WorkspaceProvider>
  );
}
