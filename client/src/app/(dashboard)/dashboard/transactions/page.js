import { List } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <ComingSoon
      icon={List}
      title="No transactions yet"
      description="Normalized transactions from every connected source will be searchable and filterable here."
    />
  );
}
