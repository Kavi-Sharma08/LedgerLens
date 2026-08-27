"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DrawerSection } from "@/components/common/drawer";
import {
  ALL_PERMISSIONS,
  CAPABILITIES,
  DEFAULT_ROLE_PERMISSIONS,
  PERMISSION_LABELS,
  expandCapabilities,
  getGrantedCapabilities,
} from "@/lib/permissions";
import { updateWorkspacePermissions } from "@/lib/api/workspaces";
import { cn } from "@/lib/utils";

const ROLE_OPTIONS = [
  { value: "ADMIN", label: "Admin" },
  { value: "MEMBER", label: "Member" },
  { value: "VIEWER", label: "Viewer" },
];

/**
 * Owner-only control for the per-role capability grants.
 *
 * The UI is grouped into a small set of higher-level capabilities (Financial
 * Data / Reconciliation / Exceptions / Workspace). Each capability maps to the
 * underlying granular permission keys that the backend actually enforces — so
 * this editor simply edits the same role_permissions document the server
 * trusts. Granular keys are hidden behind an optional "Advanced" section.
 */
export function WorkspacePermissionsSection({ workspaceId, rolePermissions }) {
  const [role, setRole] = useState("ADMIN");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Granular grants actually persisted for each role (from the server document
  // or the baseline defaults when unconfigured).
  const basePermissions = useMemo(() => {
    const configured = rolePermissions && Object.keys(rolePermissions).length > 0;
    const source = configured ? rolePermissions : DEFAULT_ROLE_PERMISSIONS;
    const result = {};
    for (const r of ["ADMIN", "MEMBER", "VIEWER"]) {
      result[r] = new Set(source[r] || []);
    }
    return result;
  }, [rolePermissions]);

  const [drafts, setDrafts] = useState(() => new Map());

  // The capability bundle currently selected for the active role.
  function currentCapabilities() {
    const draft = drafts.get(role);
    if (draft) {
      return CAPABILITIES.filter((c) =>
        c.permissions.every((p) => draft.has(p))
      ).map((c) => c.id);
    }
    return getGrantedCapabilities(role, rolePermissions);
  }

  function currentPermissionsSet() {
    const draft = drafts.get(role);
    return draft || new Set(basePermissions[role] || []);
  }

  function toggleCapability(capabilityId) {
    setDrafts((prev) => {
      const next = new Map(prev);
      const current = next.get(role) || new Set(basePermissions[role] || []);
      const updated = new Set(current);
      const capability = CAPABILITIES.find((c) => c.id === capabilityId);
      if (!capability) return prev;
      const allHeld = capability.permissions.every((p) => updated.has(p));
      if (allHeld) {
        capability.permissions.forEach((p) => updated.delete(p));
      } else {
        capability.permissions.forEach((p) => updated.add(p));
      }
      next.set(role, updated);
      return next;
    });
  }

  function togglePermission(permission) {
    setDrafts((prev) => {
      const next = new Map(prev);
      const current = next.get(role) || new Set(basePermissions[role] || []);
      const updated = new Set(current);
      if (updated.has(permission)) updated.delete(permission);
      else updated.add(permission);
      next.set(role, updated);
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateWorkspacePermissions(workspaceId, {
        role,
        permissions: [...currentPermissionsSet()],
      });
      // Commit the draft as the new baseline so the UI stays in sync.
      setDrafts((prev) => {
        const next = new Map(prev);
        next.set(role, new Set(currentPermissionsSet()));
        return next;
      });
      setShowAdvanced(false);
    } catch (err) {
      setError(err?.message || "Failed to save permissions.");
    } finally {
      setSaving(false);
    }
  }

  const grantedCapabilities = currentCapabilities();
  const selectedLabel = ROLE_OPTIONS.find((r) => r.value === role)?.label;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <DrawerSection title="Role permissions">
        <p className="mb-4 text-sm text-muted-foreground">
          Choose what each role can do. The owner always has full access.
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

        <div className="space-y-4">
          {CAPABILITIES.map((capability) => (
            <div key={capability.id} className="rounded-lg border border-border">
              <button
                type="button"
                onClick={() => toggleCapability(capability.id)}
                className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50"
                disabled={saving}
              >
                <span className="min-w-0">
                  <span className="block font-medium text-foreground">
                    {capability.name}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                    {capability.description}
                  </span>
                </span>
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-md",
                    grantedCapabilities.includes(capability.id)
                      ? "bg-primary text-primary-foreground"
                      : "border border-border bg-transparent text-transparent"
                  )}
                >
                  <Check className="size-3.5" aria-hidden="true" />
                </span>
              </button>
            </div>
          ))}
        </div>

        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowAdvanced((value) => !value)}
            className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
            aria-expanded={showAdvanced}
          >
            Advanced
            <ChevronDown
              className={cn("size-3.5 transition-transform", showAdvanced && "rotate-180")}
              aria-hidden="true"
            />
          </button>
          {showAdvanced && (
            <div className="mt-3">
              <p className="mb-2 text-xs text-muted-foreground">
                Fine-grained permissions for this role. These map directly to the server&rsquo;s
                enforced capabilities.
              </p>
              <ul role="list" className="divide-y divide-border rounded-lg border border-border">
                {ALL_PERMISSIONS.map((permission) => {
                  const granted = currentPermissionsSet().has(permission);
                  return (
                    <li key={permission}>
                      <button
                        type="button"
                        onClick={() => togglePermission(permission)}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50"
                        disabled={saving}
                      >
                        <span className="text-foreground">
                          {PERMISSION_LABELS[permission] || permission}
                        </span>
                        <span
                          className={cn(
                            "flex size-5 items-center justify-center rounded-md",
                            granted
                              ? "bg-primary text-primary-foreground"
                              : "border border-border bg-transparent text-transparent"
                          )}
                        >
                          <Check className="size-3.5" aria-hidden="true" />
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>

        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

        <div className="mt-4 flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <LoaderCircle className="mr-2 size-4 animate-spin" />
                Saving...
              </>
            ) : (
              `Save ${selectedLabel} permissions`
            )}
          </Button>
        </div>
      </DrawerSection>
    </div>
  );
}
