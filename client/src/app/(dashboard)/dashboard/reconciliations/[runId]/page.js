import { AccessGate } from "@/components/common/access-gate";
import { AccessRestricted } from "@/components/common/access-restricted";
import { ReconciliationDetail } from "@/components/domain/reconciliation-detail";

export const metadata = { title: "Reconciliation detail" };

export default async function ReconciliationDetailPage({ params }) {
  const { runId } = await params;
  const decodedRunId = decodeURIComponent(runId);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <AccessGate capability="viewData" fallback={<AccessRestricted />}>
        <ReconciliationDetail runId={decodedRunId} />
      </AccessGate>
    </div>
  );
}
