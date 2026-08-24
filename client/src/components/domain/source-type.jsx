import { Banknote, CreditCard, Landmark, Layers, FileText, Settings2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { humanize } from "@/components/domain/status-badge";

const TYPE_ICONS = {
  BANK: { icon: Landmark, label: "Bank" },
  PAYMENT_PROCESSOR: { icon: CreditCard, label: "Payment gateway" },
  ACCOUNTING: { icon: FileText, label: "Accounting" },
  CARD: { icon: CreditCard, label: "Card processor" },
  ERP: { icon: Layers, label: "ERP" },
  MANUAL: { icon: Settings2, label: "Manual" },
};

export function SourceTypeIcon({ type, className }) {
  const config = TYPE_ICONS[type] ?? { icon: Banknote };
  const Icon = config.icon;
  return <Icon className={cn("size-4", className)} aria-hidden="true" />;
}

export function sourceTypeLabel(type) {
  return TYPE_ICONS[type]?.label ?? humanize(type);
}
