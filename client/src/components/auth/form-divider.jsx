import { cn } from "@/lib/utils";

/** Horizontal rule with a centered label, used between OAuth and email forms. */
function FormDivider({ label, className }) {
  return (
    <div role="separator" aria-label={label} className={cn("flex items-center gap-3", className)}>
      <span className="h-px flex-1 bg-border" />
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

export { FormDivider };
