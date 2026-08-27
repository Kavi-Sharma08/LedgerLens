import { cookies } from "next/headers";

import { auth } from "@/lib/auth";
import { serverApi } from "@/lib/api/client";
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
 */
export default async function SettingsPage() {
  const session = await auth();
  const cookieStore = await cookies();
  const workspaceId = cookieStore.get("ll-active-workspace")?.value;

  let workspace = null;
  let currentUserRole = null;
  try {
    workspace = await serverApi.get("/api/workspaces/current", { session, workspaceId });
  } catch {
    // Workspace API unreachable: show account info without it.
  }

  if (workspace?.id && session?.user?.id) {
    try {
      const members = await serverApi.get(`/api/workspaces/${workspace.id}/members`, { session, workspaceId });
      const current = members.find((m) => m.userId === session.user.id);
      if (current) currentUserRole = current.role;
    } catch {
      // Could not fetch role — member section will work without invite button
    }
  }

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
          <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            <DetailField label="Name">
              {workspace?.id ? (
                <WorkspaceNameEditor workspaceId={workspace.id} initialName={workspace.name} />
              ) : (
                "—"
              )}
            </DetailField>
            <DetailField label="Slug">
              {workspace?.slug ? <span className="font-mono text-xs">{workspace.slug}</span> : "—"}
            </DetailField>
          </dl>
        </DrawerSection>
      </div>

      {/* Members */}
      {workspace?.id && (
        <WorkspaceMembersSection
          workspaceId={workspace.id}
          currentUserRole={currentUserRole}
          currentUserId={session?.user?.id}
          rolePermissions={workspace.rolePermissions}
        />
      )}

      {/* Role permissions (owner-controlled) */}
      {workspace?.id && (
        <WorkspacePermissionsSection
          workspaceId={workspace.id}
          currentUserRole={currentUserRole}
          rolePermissions={workspace.rolePermissions}
        />
      )}

      <SettingsForm />
    </div>
  );
}
