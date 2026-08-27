"use client";

import { createContext, useContext } from "react";

/**
 * Client context that supplies the signed-in member's resolved role and the
 * workspace's owner-controlled rolePermissions to every page under the
 * (dashboard) layout.
 *
 * The backend remains authoritative: `role` and `rolePermissions` come from
 * FastAPI membership/workspace payloads resolved by the server layout and
 * relayed through DashboardProvider. Client components read these via
 * useDashboard() so navigation, sheets, and client-rendered views adapt to
 * permissions instead of relying on stale cookies or browser-only gating.
 *
 * NOTE: This is a Client Component context — it can only be read from client
 * components. Server pages that need permission data must render a client
 * component (e.g. AccessGate) or resolve authorization server-side.
 */

const DashboardContext = createContext({
  role: null,
  rolePermissions: null,
  workspaceId: null,
  can: {},
});

export function DashboardProvider({ value, children }) {
  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}

export function useDashboard() {
  return useContext(DashboardContext);
}
