import { Plug } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Sources" };

export default function SourcesPage() {
  return (
    <ComingSoon
      icon={Plug}
      title="Connect your first financial source"
      description="Source connections (bank feeds, payment processors, ERP exports) arrive next — they unlock reconciliation."
      day="Next phase"
    />
  );
}
