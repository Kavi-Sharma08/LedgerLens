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
 * If the user has zero workspaces, we redirect to /onboarding (which lives
 * outside this route group, avoiding an infinite loop). The WorkspaceProvider
 * client component handles cookie establishment when a cookie is missing
 * but workspaces exist.
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

  try {
    // Fetch all workspaces the user belongs to
    allWorkspaces = await serverApi.get("/api/workspaces", { session });

    // Ensure it's an array (serverApi returns parsed JSON)
    if (!Array.isArray(allWorkspaces)) {
      allWorkspaces = [];
    }

    if (activeWorkspaceId && allWorkspaces.length > 0) {
      // Use the cookie-specified workspace if it's in the user's list
      workspace = allWorkspaces.find((ws) => ws.id === activeWorkspaceId) || null;
    }

    // Fall back to /current workspace if no valid cookie
    if (!workspace && allWorkspaces.length > 0) {
      try {
        workspace = await serverApi.get("/api/workspaces/current", { session });
      } catch {
        // /current may 404 if no membership — not fatal, provider handles it.
      }
    }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    // API unreachable: render without workspace data.
  }

  // Redirect to onboarding if the user has zero workspaces.
  // Onboarding lives outside this route group (/onboarding, not /dashboard/onboarding)
  // so this redirect cannot create a loop.
  if (allWorkspaces.length === 0) {
    redirect("/onboarding");
  }

  return (
    <WorkspaceProvider>
      <AppShell user={user} workspace={workspace} allWorkspaces={allWorkspaces}>
        {children}
      </AppShell>
    </WorkspaceProvider>
  );
}
