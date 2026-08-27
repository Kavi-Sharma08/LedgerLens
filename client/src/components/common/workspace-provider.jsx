"use client";

import { useEffect, useRef } from "react";

import { listWorkspaces } from "@/lib/api/workspaces";

/**
 * Ensures the ll-active-workspace cookie matches the workspace the server
 * layout resolved (serverWorkspaceId).
 *
 * Runs once on mount inside the dashboard layout:
 *   - Cookie already equals the server-resolved workspace -> no-op.
 *   - Cookie missing or stale -> activate the correct workspace through
 *     /api/workspace/activate and reload so server components re-render with
 *     the corrected cookie (which also fixes a stale cookie left behind when
 *     a membership was removed).
 *   - No workspaces at all -> redirect to onboarding.
 *
 * This component renders nothing — it only performs side effects.
 */
export function WorkspaceProvider({ serverWorkspaceId, children }) {
  const attemptedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function resolveWorkspace() {
      const cookie = getCookie("ll-active-workspace");

      // Cookie already matches the workspace the server rendered with.
      if (cookie === serverWorkspaceId) return;

      // Don't spin if activation keeps failing (e.g. API is down).
      if (attemptedRef.current) return;
      attemptedRef.current = true;

      try {
        const workspaces = await listWorkspaces();
        if (cancelled) return;

        if (!workspaces || workspaces.length === 0) {
          // No workspaces at all — send to onboarding.
          window.location.replace("/onboarding");
          return;
        }

        // Prefer the server-resolved workspace; otherwise the first available.
        const target =
          workspaces.find((ws) => ws.id === serverWorkspaceId) ?? workspaces[0];

        if (cookie === target.id) return;

        const res = await fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: target.id }),
        });

        if (cancelled) return;

        if (res.ok && cookie !== target.id) {
          // Reload so server components re-render with the new cookie.
          window.location.reload();
        }
      } catch {
        // Leave the cookie as-is; transient API failures shouldn't redirect.
      }
    }

    resolveWorkspace();
    return () => {
      cancelled = true;
    };
  }, [serverWorkspaceId]);

  // Render children immediately — the provider is non-blocking.
  return children;
}

function getCookie(name) {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}