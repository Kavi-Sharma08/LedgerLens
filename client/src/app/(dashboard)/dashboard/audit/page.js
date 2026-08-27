import { PageHeader } from "@/components/common/page-header";
import { AccessGate } from "@/components/common/access-gate";
import { AccessRestricted } from "@/components/common/access-restricted";
import { AuditView } from "@/components/domain/audit-view";

export const metadata = { title: "Audit Log" };

export default function AuditPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Audit Log"
        description="History of important actions in this workspace."
      />
      <AccessGate capability="viewAudit" fallback={<AccessRestricted />}>
        <AuditView />
      </AccessGate>
    </div>
  );
}
