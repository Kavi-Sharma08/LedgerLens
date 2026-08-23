import { ArrowLeftRight } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Reconciliations" };

export default function ReconciliationsPage() {
  return (
    <ComingSoon
      icon={ArrowLeftRight}
      title="No reconciliations yet"
      description="Once sources are connected, LedgerLens will continuously reconcile your ledgers and report status here."
    />
  );
}
