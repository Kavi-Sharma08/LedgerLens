import { auth } from "@/lib/auth";
import { serverApi } from "@/lib/api/client";
import { PageHeader } from "@/components/common/page-header";
import { DetailField, DrawerSection } from "@/components/common/drawer";
import { SettingsForm } from "@/components/domain/settings-form";

export const metadata = { title: "Settings" };

/**
 * Account and workspace details. Both come from trusted sources: the Auth.js
 * session (identity) and FastAPI (workspace). No settings are editable yet —
 * the page shows exactly what the platform knows, with sign-out.
 */
export default async function SettingsPage() {
  const session = await auth();

  let workspace = null;
  try {
    workspace = await serverApi.get("/api/workspaces/current", { session });
  } catch {
    // Workspace API unreachable: show account info without it.
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Settings"
        description="Your account and workspace details."
      />

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <DrawerSection title="Account" className="border-t-0">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            <DetailField label="Name">{session?.user?.name || "—"}</DetailField>
            <DetailField label="Email">{session?.user?.email || "—"}</DetailField>
          </dl>
          <p className="mt-4 text-sm text-muted-foreground">
            Profile details and role management are managed by your authentication provider.
          </p>
        </DrawerSection>

        <DrawerSection title="Workspace">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            <DetailField label="Name">{workspace?.name || "—"}</DetailField>
            <DetailField label="Slug">
              {workspace?.slug ? <span className="font-mono text-xs">{workspace.slug}</span> : "—"}
            </DetailField>
            <div className="sm:col-span-2">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Workspace ID</dt>
              <dd className="mt-0.5 font-mono text-xs break-all text-muted-foreground">
                {workspace?.id || "—"}
              </dd>
            </div>
          </dl>
        </DrawerSection>
      </div>

      <SettingsForm />
    </div>
  );
}
