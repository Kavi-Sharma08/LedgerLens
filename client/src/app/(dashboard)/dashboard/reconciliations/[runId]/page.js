import { ReconciliationDetail } from "@/components/domain/reconciliation-detail";

export const metadata = { title: "Reconciliation detail" };

export default async function ReconciliationDetailPage({ params }) {
  const { runId } = await params;
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <ReconciliationDetail runId={decodeURIComponent(runId)} />
    </div>
  );
}
