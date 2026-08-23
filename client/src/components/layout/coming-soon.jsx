import { EmptyState } from "@/components/common/empty-state";

/**
 * Shared placeholder for dashboard areas arriving in later development days.
 * Keeps navigation honest without stubbing fake functionality.
 */
export function ComingSoon({ icon, title, description, day }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <EmptyState
        icon={icon}
        className="border-border bg-card py-16"
        title={title}
        description={description}
        action={
          <span className="rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            Arrives in a later development phase{day ? ` · ${day}` : ""}
          </span>
        }
      />
    </div>
  );
}
