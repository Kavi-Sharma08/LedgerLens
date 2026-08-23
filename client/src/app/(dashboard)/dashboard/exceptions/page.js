import { TriangleAlert } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Exceptions" };

export default function ExceptionsPage() {
  return (
    <ComingSoon
      icon={TriangleAlert}
      title="Exceptions appear once reconciliation runs"
      description="Unmatched records will be ranked by materiality, with AI-prepared evidence for each one."
    />
  );
}
