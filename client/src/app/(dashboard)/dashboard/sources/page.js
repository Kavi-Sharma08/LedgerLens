import { PageHeader } from "@/components/common/page-header";
import { AccessGate } from "@/components/common/access-gate";
import { AccessRestricted } from "@/components/common/access-restricted";
import { SourcesView } from "@/components/domain/sources-view";

export const metadata = { title: "Sources" };

export default function SourcesPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Sources"
        description="The financial systems LedgerLens watches — connect them, then import their statements."
      />
      <AccessGate capability="viewData" fallback={<AccessRestricted />}>
        <SourcesView />
      </AccessGate>
    </div>
  );
}
