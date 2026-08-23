export const siteConfig = {
  name: "LedgerLens",
  tagline: "Financial reconciliation, without the manual investigation.",
  description:
    "LedgerLens automatically reconciles financial records and uses AI to investigate the exceptions that matter.",
  appUrl: process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
};

export const apiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
};

export const marketingNav = [
  { title: "How it works", href: "/#how-it-works" },
  { title: "Features", href: "/#features" },
  { title: "Pricing", href: "/#pricing" },
];

export const dashboardNav = [
  { title: "Overview", href: "/dashboard", icon: "layout-dashboard", exact: true },
  { title: "Reconciliations", href: "/dashboard/reconciliations", icon: "arrow-left-right" },
  { title: "Transactions", href: "/dashboard/transactions", icon: "list" },
  { title: "Exceptions", href: "/dashboard/exceptions", icon: "triangle-alert" },
  { title: "Sources", href: "/dashboard/sources", icon: "plug" },
];

export const dashboardSecondaryNav = [{ title: "Settings", href: "/dashboard/settings", icon: "settings" }];
