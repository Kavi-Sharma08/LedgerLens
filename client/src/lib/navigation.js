import { dashboardNav, dashboardSecondaryNav } from "@/config/site";

/**
 * Filter the dashboard navigation to only the items the member is permitted
 * to access. This is a UI improvement only — the backend still enforces every
 * permission. `can` is the resolved permission-flag object from
 * buildDashboardProfile (server data).
 */
export function filterDashboardNav(can) {
  if (!can) return { primary: dashboardNav, secondary: dashboardSecondaryNav };

  const primary = dashboardNav.filter((item) => {
    // Overview is always available so members always have a landing page.
    if (item.exact) return true;
    // Transactions, Reconciliations, Exceptions and Sources all depend on
    // the ability to view financial data.
    return can.viewData;
  });

  const secondary = dashboardSecondaryNav.filter((item) => {
    if (item.href.endsWith("/audit")) return can.viewAudit;
    // Settings is always listed (account info is visible to everyone); the
    // management controls inside are gated separately.
    return true;
  });

  return { primary, secondary };
}
