import { cn } from "@/lib/utils";

/**
 * Reusable empty state: explains the situation and offers the next action.
 * Used across dashboard widgets until real data flows from FastAPI.
 */
function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center",
        className
      )}
    >
      {Icon && (
        <span className="flex size-10 items-center justify-center rounded-full bg-accent">
          <Icon className="size-5 text-primary" aria-hidden="true" />
        </span>
      )}
      <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export { EmptyState };
