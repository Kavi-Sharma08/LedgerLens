"use client";

import { useDashboard } from "@/components/common/dashboard-context";

/**
 * Permission-aware gate for server (or client) pages.
 *
 * Reads the signed-in member's resolved capability map from DashboardContext
 * and renders `children` only when the member holds the named capability;
 * otherwise it renders `fallback` (typically an <AccessRestricted /> state).
 *
 * Authorization is still enforced by the backend — this only adapts the UI,
 * and it lets Server Components keep their metadata/async work while the
 * context read happens in this small client component.
 */
export function AccessGate({ capability, fallback = null, children }) {
  const { can } = useDashboard();
  return can[capability] ? children : fallback;
}
