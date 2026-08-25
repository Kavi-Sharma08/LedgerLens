"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { listWorkspaces } from "@/lib/api/workspaces";

/**
 * Resolves and persists the active workspace after login or page load.
 *
 * Runs once on mount inside the dashboard layout. If a valid cookie exists
 * the provider is a no-op. If not, it picks the first available workspace
 * and writes the cookie via the activate API route.
 *
 * If the user has zero workspaces, redirects to the onboarding page.
 *
 * This component renders nothing — it only performs side effects.
 */
export function WorkspaceProvider({ children }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function resolveWorkspace() {
      // Already have a cookie — nothing to do.
      if (getCookie("ll-active-workspace")) {
        setReady(true);
        return;
      }

      try {
        const workspaces = await listWorkspaces();

        if (cancelled) return;

        if (!workspaces || workspaces.length === 0) {
          // No workspaces at all — send to onboarding.
          window.location.replace("/onboarding");
          return;
        }

        // Activate the first workspace via the server route (sets cookie).
        const res = await fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: workspaces[0].id }),
        });

        if (cancelled) return;

        if (res.ok) {
          // Reload so server components re-render with the new cookie.
          window.location.reload();
        } else {
          setReady(true);
        }
      } catch {
        if (!cancelled) setReady(true);
      }
    }

    resolveWorkspace();
    return () => {
      cancelled = true;
    };
  }, []);

  // Render children immediately — the provider is non-blocking.
  // The first paint may use a null workspace, but API calls will resolve
  // once the cookie is established and the page reloads.
  return children;
}

function getCookie(name) {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}
