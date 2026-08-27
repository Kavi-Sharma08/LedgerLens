import { Suspense } from "react";

import { PageHeader } from "@/components/common/page-header";
import { AccessGate } from "@/components/common/access-gate";
import { AccessRestricted } from "@/components/common/access-restricted";
import { Skeleton } from "@/components/ui/skeleton";
import { TransactionsView } from "@/components/domain/transactions-view";

export const metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Transactions"
        description="Every normalized record across your financial sources."
      />
      <AccessGate capability="viewData" fallback={<AccessRestricted />}>
        <Suspense fallback={<TransactionsSkeleton />}>
          <TransactionsView />
        </Suspense>
      </AccessGate>
    </div>
  );
}

function TransactionsSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading transactions">
      <div className="flex flex-wrap gap-2">
        <Skeleton className="h-8 w-full max-w-xs" />
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-8 w-32" />
      </div>
      <Skeleton className="h-96 w-full rounded-xl" />
    </div>
  );
}
