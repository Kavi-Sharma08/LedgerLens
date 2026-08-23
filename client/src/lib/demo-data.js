/**
 * Day 1 placeholder dataset for the dashboard.
 *
 * These values intentionally live in ONE module so they can be replaced with
 * FastAPI responses (GET /api/dashboard/summary) without touching components.
 */

export const dashboardSummary = {
  rangeLabel: "Last 30 days",
  totals: {
    transactions: { value: 12480, delta: "+6.2% vs prior period", direction: "up" },
    matched: { value: 11763, delta: "94.2% match rate", direction: "up" },
    needsReview: { value: 469, delta: "31 new this week", direction: "down" },
    unresolved: { value: 48, delta: "12 aging past 7 days", direction: "down" },
  },
  activity: [
    { label: "Jan", matched: 62, exceptions: 14 },
    { label: "Feb", matched: 58, exceptions: 18 },
    { label: "Mar", matched: 66, exceptions: 11 },
    { label: "Apr", matched: 71, exceptions: 13 },
    { label: "May", matched: 69, exceptions: 9 },
    { label: "Jun", matched: 74, exceptions: 10 },
    { label: "Jul", matched: 78, exceptions: 8 },
    { label: "Aug", matched: 82, exceptions: 7 },
  ],
  recentExceptions: [
    {
      id: "exc_001",
      title: "Amount mismatch",
      amount: "$1,240.00",
      detail: "Stripe payout #8841 vs bank ledger entry",
      severity: "warning",
      status: "Investigating",
      age: "2h ago",
    },
    {
      id: "exc_002",
      title: "Missing ledger entry",
      amount: "$86.40",
      detail: "Wire fee not recorded in ERP",
      severity: "danger",
      status: "Needs review",
      age: "5h ago",
    },
    {
      id: "exc_003",
      title: "Duplicate candidate",
      amount: "$412.10",
      detail: "INV-2091 appears twice in payables",
      severity: "info",
      status: "AI investigated",
      age: "1d ago",
    },
    {
      id: "exc_004",
      title: "Timing difference",
      amount: "$9,300.00",
      detail: "Settlement date crosses period boundary",
      severity: "info",
      status: "Resolved",
      age: "2d ago",
    },
  ],
  aiInvestigation: {
    headline: "3 exceptions investigated automatically this week",
    summary:
      "LedgerLens traced open mismatches across your connected ledgers and prepared two recommendations for review.",
    findings: [
      "Stripe payout gap likely caused by a partial refund posted after settlement.",
      "Recurring $86.40 wire fee missing from ERP suggests a mapping rule change.",
    ],
  },
};
