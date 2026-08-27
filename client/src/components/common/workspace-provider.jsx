"use client";

import { useEffect, useLayoutEffect, useRef } from "react";

import { listWorkspaces } from "@/lib/api/workspaces";

const COOKIE_NAME = "ll-active-workspace";
const MAX_AGE = 31536000; // 1 year

/**
 * Keeps the browser's ll-active-workspace cookie in sync with the workspace the
 * server layout resolved (serverWorkspaceId).
 *
 * When the layout resolves a workspace it hands the id down here. That id is
 * authoritative (the layout verified membership against the server member
 * list), so we write it to the cookie immediately on the client via
 * useLayoutEffect. Layout effects run BEFORE the data views' passive effects,
 * so every browser->backend fetch through /api/backend reads the correct
 * workspace even on first load when the cookie was missing or stale — no flash
 * of "No workspace selected" and no reliance on a full-page reload.
 *
 * If the layout could not resolve a workspace (e.g. the API was down), we fall
 * back to listing workspaces and reconciling through /api/workspace/activate,
 * or redirect to onboarding when the user has no workspaces.
 */
export function WorkspaceProvider({ serverWorkspaceId, children }) {
  const syncedRef = useRef(false);

  // Runs during commit, before any child passive effect that fetches data.
  useLayoutEffect(() => {
    if (!serverWorkspaceId || syncedRef.current) return;
    syncedRef.current = true;
    if (getCookie(COOKIE_NAME) !== serverWorkspaceId) {
      document.cookie = `${COOKIE_NAME}=${serverWorkspaceId}; path=/; samesite=lax; max-age=${MAX_AGE}`;
    }
  }, [serverWorkspaceId]);

  // Fallback only: the layout couldn't resolve a workspace (API unreachable).
  useEffect(() => {
    if (serverWorkspaceId) return;
    let cancelled = false;

    listWorkspaces()
      .then((workspaces) => {
        if (cancelled) return;
        if (!workspaces || workspaces.length === 0) {
          window.location.replace("/onboarding");
          return;
        }
        fetch("/api/workspace/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspaceId: workspaces[0].id }),
        }).then((res) => {
          if (cancelled) return;
          if (res.ok) window.location.reload();
        });
      })
      .catch(() => {
        // Leave things as-is; transient API failures shouldn't redirect.
      });

    return () => {
      cancelled = true;
    };
  }, [serverWorkspaceId]);

  return children;
}

function getCookie(name) {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}
