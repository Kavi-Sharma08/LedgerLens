import { redirect } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { serverApi, ApiError } from "@/lib/api/client";
import { auth } from "@/lib/auth";

/**
 * Protected route boundary for the entire authenticated area.
 *
 * Auth.js (server-side) validates the HttpOnly session cookie BEFORE any
 * dashboard content renders — an unauthenticated visitor is redirected without
 * ever seeing protected UI.
 *
 * Workspace data remains business data owned by FastAPI: fetched server-to-
 * server with trusted identity headers. A backend outage degrades the switcher
 * label but never blocks the shell from rendering.
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

  let workspace = null;
  try {
    workspace = await serverApi.get("/api/workspaces/current", { session });
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    // API unreachable or workspace missing: render without it.
  }

  return (
    <AppShell user={user} workspace={workspace}>
      {children}
    </AppShell>
  );
}
