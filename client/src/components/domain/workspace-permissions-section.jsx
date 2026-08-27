"use client";

import { useMemo, useState } from "react";
import { Check, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DrawerSection } from "@/components/common/drawer";
import {
  ALL_PERMISSIONS,
  DEFAULT_ROLE_PERMISSIONS,
  PERMISSION_LABELS,
} from "@/lib/permissions";
import { updateWorkspacePermissions } from "@/lib/api/workspaces";

const ROLE_OPTIONS = [
  { value: "ADMIN", label: "Admin" },
  { value: "MEMBER", label: "Member" },
  { value: "VIEWER", label: "Viewer" },
];

/**
 * Owner-only control for the per-role capability grants. These grants are
 * enforced server-side (require_permission); this UI just edits the same
 * role_permissions document the backend trusts.
 */
export function WorkspacePermissionsSection({
  workspaceId,
  rolePermissions,
  currentUserRole,
}) {
  const [role, setRole] = useState("ADMIN");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const base = useMemo(() => {
    const configured = rolePermissions && Object.keys(rolePermissions).length > 0;
    const source = configured ? rolePermissions : DEFAULT_ROLE_PERMISSIONS;
    const drafts = {};
    for (const r of ["ADMIN", "MEMBER", "VIEWER"]) {
      drafts[r] = new Set(source[r] || []);
    }
    return drafts;
  }, [rolePermissions]);

  const [drafts, setDrafts] = useState(() => new Map());

  function toggle(permission) {
    setDrafts((prev) => {
      const next = new Map(prev);
      const current = next.get(role) || new Set(base[role] || []);
      const updated = new Set(current);
      if (updated.has(permission)) updated.delete(permission);
      else updated.add(permission);
      next.set(role, updated);
      return next;
    });
  }

  function currentSet() {
    const draft = drafts.get(role);
    return draft || new Set(base[role] || []);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateWorkspacePermissions(workspaceId, {
        role,
        permissions: [...currentSet()],
      });
      // Commit the draft as the new baseline so the UI stays in sync.
      setDrafts((prev) => {
        const next = new Map(prev);
        next.set(role, new Set(currentSet()));
        return next;
      });
    } catch (err) {
      setError(err?.message || "Failed to save permissions.");
    } finally {
      setSaving(false);
    }
  }

  if (currentUserRole !== "OWNER") {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <DrawerSection title="Role permissions">
        <p className="mb-4 text-sm text-muted-foreground">
          Choose what each role can do. The owner always has every permission.
          Changes apply immediately and are enforced by the server.
        </p>

        <div className="mb-4 max-w-xs space-y-2">
          <Label htmlFor="perm-role">Role</Label>
          <Select
            id="perm-role"
            value={role}
            onValueChange={(next) => next && setRole(next)}
            items={ROLE_OPTIONS}
            placeholder="Select a role"
          />
        </div>

        <ul role="list" className="divide-y divide-border rounded-lg border border-border">
          {ALL_PERMISSIONS.map((permission) => {
            const granted = currentSet().has(permission);
            return (
              <li key={permission}>
                <button
                  type="button"
                  onClick={() => toggle(permission)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50"
                  disabled={saving}
                >
                  <span className="text-foreground">
                    {PERMISSION_LABELS[permission] || permission}
                  </span>
                  <span
                    className={
                      granted
                        ? "flex size-5 items-center justify-center rounded-md bg-primary text-primary-foreground"
                        : "flex size-5 items-center justify-center rounded-md border border-border text-transparent"
                    }
                  >
                    <Check className="size-3.5" aria-hidden="true" />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

        <div className="mt-4 flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <LoaderCircle className="mr-2 size-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save permissions for " + ROLE_OPTIONS.find((r) => r.value === role)?.label
            )}
          </Button>
        </div>
      </DrawerSection>
    </div>
  );
}
