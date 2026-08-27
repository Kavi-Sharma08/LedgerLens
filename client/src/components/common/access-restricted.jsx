import { LockKeyhole } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Reusable "Access restricted" state shown when a signed-in member lacks
 * permission to view a feature in the current workspace.
 *
 * It intentionally does NOT expose internal permission keys (e.g.
 * `view_audit_log`) or claim the app is broken. The user is signed in, the
 * workspace exists, the feature exists — their role simply lacks access.
 */
export function AccessRestricted({ className, title, message }) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-border bg-card px-6 py-16 text-center",
        className
      )}
    >
      <span className="flex size-12 items-center justify-center rounded-full bg-muted">
        <LockKeyhole className="size-6 text-muted-foreground" aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-base font-semibold text-foreground">
        {title || "Access restricted"}
      </h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        {message ||
          "You don't have permission to view this area in this workspace. Ask your workspace owner or administrator to grant you access."}
      </p>
    </div>
  );
}
