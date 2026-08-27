import { cookies } from "next/headers";

import { auth } from "@/lib/auth";
import { serverApi } from "@/lib/api/client";
import { hasPermission } from "@/lib/permissions";
import { PageHeader } from "@/components/common/page-header";
import { DetailField, DrawerSection } from "@/components/common/drawer";
import { SettingsForm } from "@/components/domain/settings-form";
import { WorkspaceMembersSection } from "@/components/domain/workspace-members-section";
import { WorkspacePermissionsSection } from "@/components/domain/workspace-permissions-section";
import { WorkspaceNameEditor } from "@/components/domain/workspace-name-editor";
import { PasswordSection } from "@/components/domain/password-section";

export const metadata = { title: "Settings" };

/**
 * Account and workspace details.
 * Shows account info, password management, workspace settings, and member management.
 * Workspace-management controls are only shown to members with the matching
 * grants; the member list adapts to the member's manage/invite grants. The
 * backend remains the enforcement authority — this page only adapts what is
 * shown using server-resolved role/grants.
 */
export default async function SettingsPage() {
  const session = await auth();
  const cookieStore = await cookies();
  const workspaceId = cookieStore.get("ll-active-workspace")?.value;

  let workspace = null;
  let role = null;
  try {
    workspace = await serverApi.get("/api/workspaces/current", { session, workspaceId });
    if (workspace?.id) {
      const members = await serverApi.get(`/api/workspaces/${workspace.id}/members`, {
        session,
        workspaceId: workspace.id,
      });
      const current = (members || []).find((m) => m.userId === session?.user?.id);
      role = current?.role ?? null;
    }
  } catch {
    // Workspace API unreachable: show account info without workspace controls.
  }

  const rolePermissions = workspace?.rolePermissions ?? null;

  const can = {
    manageSettings: hasPermission(role, rolePermissions, "manage_workspace_settings"),
    manageMembers: hasPermission(role, rolePermissions, "manage_members"),
    inviteMembers: hasPermission(role, rolePermissions, "invite_members"),
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Settings"
        description="Your account, workspace, and team management."
      />

      {/* Account */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <DrawerSection title="Account" className="border-t-0">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            <DetailField label="Name">{session?.user?.name || "—"}</DetailField>
            <DetailField label="Email">{session?.user?.email || "—"}</DetailField>
          </dl>
        </DrawerSection>
      </div>

      {/* Password */}
      <PasswordSection />

      {/* Workspace */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <DrawerSection title="Workspace" className="border-t-0">
          {can.manageSettings && workspace?.id ? (
            <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
              <DetailField label="Name">
                <WorkspaceNameEditor workspaceId={workspace.id} initialName={workspace.name} />
              </DetailField>
              <DetailField label="Slug">
                {workspace?.slug ? <span className="font-mono text-xs">{workspace.slug}</span> : "—"}
              </DetailField>
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">
              You don&rsquo;t have permission to manage this workspace&rsquo;s settings. Ask your
              workspace owner or administrator for access.
            </p>
          )}
        </DrawerSection>
      </div>

      {/* Members */}
      {workspace?.id && (can.manageMembers || can.inviteMembers) && (
        <WorkspaceMembersSection
          workspaceId={workspace.id}
          currentUserRole={role}
          currentUserId={session?.user?.id}
          rolePermissions={rolePermissions}
        />
      )}

      {/* Role permissions (owner-controlled) */}
      {workspace?.id && role === "OWNER" && (
        <WorkspacePermissionsSection
          workspaceId={workspace.id}
          rolePermissions={workspace.rolePermissions}
        />
      )}

      <SettingsForm />
    </div>
  );
}
