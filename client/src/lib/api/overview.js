import { api } from "@/lib/api/client";

/**
 * Overview KPI summary for the dashboard.
 */
export function getOverview({ signal } = {}) {
  return api.get("/api/overview", { signal });
}
