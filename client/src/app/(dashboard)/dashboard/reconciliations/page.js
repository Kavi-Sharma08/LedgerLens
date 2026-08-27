import { PageHeader } from "@/components/common/page-header";
import { AccessGate } from "@/components/common/access-gate";
import { AccessRestricted } from "@/components/common/access-restricted";
import { ReconciliationsView } from "@/components/domain/reconciliations-view";

export const metadata = { title: "Reconciliations" };

export default function ReconciliationsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Reconciliations"
        description="Run comparisons between your sources and review what the engine finds."
      />
      <AccessGate capability="viewData" fallback={<AccessRestricted />}>
        <ReconciliationsView />
      </AccessGate>
    </div>
  );
}
